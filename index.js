const makeWASocket = require('@whiskeysockets/baileys').default;
const { DisconnectReason, useMultiFileAuthState, downloadMediaMessage, fetchLatestBaileysVersion } = require('@whiskeysockets/baileys');
const { Boom } = require('@hapi/boom');
const P = require('pino');
const axios = require('axios');
const { Storage } = require('@google-cloud/storage');
const fs = require('fs');
const path = require('path');
const qrcode = require('qrcode-terminal');
const { v4: uuidv4 } = require('uuid');
const { fileTypeFromBuffer } = require('file-type');
const XLSX = require('xlsx');
const mammoth = require('mammoth');

// Load configuration
let config;
try {
    config = JSON.parse(fs.readFileSync(path.join(__dirname, 'config.json'), 'utf8'));
} catch (error) {
    console.error('Error loading config.json:', error.message);
    process.exit(1);
}

// Configuration from config file or environment variables
const ADK_URL = process.env.ADK_URL || config.adk.url;
const ADK_APP_NAME = process.env.ADK_APP_NAME || config.adk.appName;
const BUCKET_NAME = process.env.BUCKET_NAME || config.gcs.bucketName;
const ARTIFACTS_BUCKET_NAME = process.env.ARTIFACTS_BUCKET_NAME || config.gcs.artifactsBucketName;
const PROJECT_ID = process.env.PROJECT_ID || config.gcs.projectId;

// Initialize Google Cloud Storage
const storage = new Storage({ projectId: PROJECT_ID });
const bucket = storage.bucket(BUCKET_NAME);
const artifactsBucket = storage.bucket(ARTIFACTS_BUCKET_NAME);

// Logger configuration
const logger = P({
    level: process.env.LOG_LEVEL || config.bot.logLevel,
    transport: {
        target: 'pino-pretty',
        options: {
            colorize: true
        }
    }
});

/**
 * Custom auth state that stores data in Google Cloud Storage
 * Uses the built-in auth functions but stores files in GCS
 */
class GCSAuthState {
    constructor() {
        this.authFolder = config.gcs.authFolder;
    }

    async readData(file) {
        try {
            const filePath = `${this.authFolder}/${file}`;
            const [exists] = await bucket.file(filePath).exists();
            
            if (!exists) {
                return null;
            }

            const [data] = await bucket.file(filePath).download();
            const content = data.toString();
            return JSON.parse(content, this.bufferJSONReviver);
        } catch (error) {
            logger.error(`Error reading ${file}:`, error);
            return null;
        }
    }

    async writeData(data, file) {
        try {
            const filePath = `${this.authFolder}/${file}`;
            const jsonString = JSON.stringify(data, this.bufferJSONReplacer, 2);
            const fileBuffer = Buffer.from(jsonString);
            
            await bucket.file(filePath).save(fileBuffer, {
                metadata: {
                    contentType: 'application/json'
                }
            });
            
            logger.debug(`Saved ${file} to GCS`);
        } catch (error) {
            logger.error(`Error writing ${file}:`, error);
            throw error;
        }
    }

    async removeData(file) {
        try {
            const filePath = `${this.authFolder}/${file}`;
            await bucket.file(filePath).delete();
            logger.debug(`Removed ${file} from GCS`);
        } catch (error) {
            if (error.code !== 404) {
                logger.error(`Error removing ${file}:`, error);
            }
        }
    }

    // Buffer JSON handling for proper serialization
    bufferJSONReplacer(key, value) {
        if (value?.type === 'Buffer' && Array.isArray(value?.data)) {
            return { __buffer_type: true, data: value.data };
        }
        return value;
    }

    bufferJSONReviver(key, value) {
        if (value?.__buffer_type) {
            return Buffer.from(value.data);
        }
        return value;
    }

    fixFileName(file) {
        return file?.replace(/\//g, '__')?.replace(/:/g, '-');
    }

    async initAuthState() {
        // Import the required auth utilities
        const { initAuthCreds } = require('@whiskeysockets/baileys');
        const { proto } = require('@whiskeysockets/baileys');
        
        const creds = await this.readData('creds.json') || initAuthCreds();
        
        return {
            state: {
                creds,
                keys: {
                    get: async (type, ids) => {
                        const data = {};
                        await Promise.all(
                            ids.map(async id => {
                                let value = await this.readData(`${type}-${id}.json`);
                                if (type === 'app-state-sync-key' && value) {
                                    value = proto.Message.AppStateSyncKeyData.fromObject(value);
                                }
                                data[id] = value;
                            })
                        );
                        return data;
                    },
                    set: async data => {
                        const tasks = [];
                        for (const category in data) {
                            for (const id in data[category]) {
                                const value = data[category][id];
                                const file = `${category}-${id}.json`;
                                tasks.push(value ? this.writeData(value, file) : this.removeData(file));
                            }
                        }
                        await Promise.all(tasks);
                    }
                }
            },
            saveCreds: async () => {
                return this.writeData(creds, 'creds.json');
            }
        };
    }
}

/**
 * GCS Artifact Service for ADK artifact management
 * Implements artifact storage following ADK format requirements
 */
class GcsArtifactService {
    constructor() {
        this.bucketName = ARTIFACTS_BUCKET_NAME;
        this.artifactsFolder = config.gcs.artifactsFolder;
        this.storage = storage;
        this.bucket = artifactsBucket;
    }

    /**
     * Generate artifact path: {appName}/{userId}/{sessionId}/{filename}
     * This matches ADK Runner's expected path structure for cross-compatibility
     */
    getArtifactPath(appName, userId, filename, sessionId = 'shared') {
        // Use ADK-compatible path: app/userId/sessionId/filename
        return `${appName}/${userId}/${sessionId}/${filename}`;
    }

    /**
     * Save artifact to GCS and return version number
     */
    async saveArtifact(appName, userId, filename, part, sessionId = 'shared') {
        try {
            const artifactPath = this.getArtifactPath(appName, userId, filename, sessionId);
            
            // Convert Part object to storage format
            const artifactData = {
                mimeType: part.mimeType || part.inline_data?.mime_type || 'application/octet-stream',
                data: part.data || part.inline_data?.data,
                timestamp: new Date().toISOString(),
                filename: filename
            };

            // Get existing versions to determine next version number
            const versions = await this.listVersions(appName, userId, filename, sessionId);
            const nextVersion = versions.length > 0 ? Math.max(...versions) + 1 : 1;
            
            const versionedPath = `${artifactPath}/v${nextVersion}`;
            
            // Save artifact data as JSON
            const fileBuffer = Buffer.from(JSON.stringify(artifactData, this.bufferJSONReplacer, 2));
            
            await this.bucket.file(versionedPath).save(fileBuffer, {
                metadata: {
                    contentType: 'application/json',
                    customMetadata: {
                        artifactVersion: nextVersion.toString(),
                        originalMimeType: artifactData.mimeType,
                        filename: filename
                    }
                }
            });

            logger.info(`Saved artifact ${filename} v${nextVersion} for user ${userId}`);
            return nextVersion;
            
        } catch (error) {
            logger.error(`Error saving artifact ${filename}:`, error);
            throw error;
        }
    }

    /**
     * Load artifact from GCS (latest version if no version specified)
     */
    async loadArtifact(appName, userId, filename, version = null, sessionId = 'shared') {
        try {
            const artifactPath = this.getArtifactPath(appName, userId, filename, sessionId);
            
            let targetVersion = version;
            if (!targetVersion) {
                // Get latest version
                const versions = await this.listVersions(appName, userId, filename, sessionId);
                if (versions.length === 0) {
                    return null;
                }
                targetVersion = Math.max(...versions);
            }

            const versionedPath = `${artifactPath}/v${targetVersion}`;
            const file = this.bucket.file(versionedPath);
            
            const [exists] = await file.exists();
            if (!exists) {
                return null;
            }

            const [data] = await file.download();
            const artifactData = JSON.parse(data.toString(), this.bufferJSONReviver);
            
            // Return in ADK Part format
            return {
                inline_data: {
                    mime_type: artifactData.mimeType,
                    data: artifactData.data
                },
                mimeType: artifactData.mimeType,
                data: artifactData.data
            };
            
        } catch (error) {
            logger.error(`Error loading artifact ${filename}:`, error);
            return null;
        }
    }

    /**
     * Test GCS connectivity and authentication
     */
    async testGCSConnection() {
        try {
            logger.info('Testing GCS connection...');
            const [files] = await this.bucket.getFiles({ maxResults: 1 });
            logger.info(`GCS connection successful. Found ${files.length} files in bucket.`);
            return true;
        } catch (error) {
            logger.error('GCS connection failed:', error.message);
            logger.error('Error details:', error);
            return false;
        }
    }

    /**
     * Load artifact from GCS by session ID (ADK session-scoped artifacts)
     */
    async loadArtifactBySession(appName, userId, sessionId, filename, version = 0) {
        try {
            // First test GCS connectivity
            logger.info('Testing GCS connection before artifact loading...');
            const isConnected = await this.testGCSConnection();
            if (!isConnected) {
                logger.error('GCS connection test failed - aborting artifact load');
                return null;
            }
            
            // ADK stores artifacts in: app/userId/sessionId/filename/version
            const artifactPath = `${appName}/${userId}/${sessionId}/${filename}/${version}`;
            logger.info(`Loading artifact from path: ${artifactPath}`);
            
            const file = this.bucket.file(artifactPath);
            
            logger.info('Checking if artifact exists...');
            const [exists] = await Promise.race([
                file.exists(),
                new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout checking file existence')), 10000))
            ]);
            logger.info(`Artifact exists check: ${exists} for path: ${artifactPath}`);
            
            if (!exists) {
                logger.warn(`Artifact not found: ${artifactPath}`);
                return null;
            }

            logger.info(`Downloading artifact: ${artifactPath}`);
            // ADK stores raw image data, not JSON wrapped data
            const [imageBuffer] = await Promise.race([
                file.download(),
                new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout downloading file')), 30000))
            ]);
            logger.info(`Downloaded ${imageBuffer.length} bytes for artifact: ${filename}`);
            
            // Convert to base64 for WhatsApp/Baileys
            const base64Data = imageBuffer.toString('base64');
            logger.info(`Converted to base64, length: ${base64Data.length}`);
            
            // Determine MIME type from filename
            let mimeType = 'image/png';
            if (filename.includes('.jpg') || filename.includes('.jpeg')) {
                mimeType = 'image/jpeg';
            } else if (filename.includes('.webp')) {
                mimeType = 'image/webp';
            }
            
            logger.info(`Artifact loaded successfully: ${filename}, mimeType: ${mimeType}`);
            
            // Return in format expected by WhatsApp bot
            return {
                mimeType: mimeType,
                data: base64Data
            };
            
        } catch (error) {
            // Use console.error to avoid logger truncation
            console.error('=== ARTIFACT LOADING ERROR DETAILS ===');
            console.error(`Error loading session artifact ${filename}:`);
            console.error(`Error message: ${error.message}`);
            console.error(`Error name: ${error.name}`);
            console.error(`Error code: ${error.code}`);
            console.error(`Artifact path: ${artifactPath}`);
            console.error('Full error object:', error);
            console.error('Error stack trace:');
            console.error(error.stack);
            console.error('=== END ERROR DETAILS ===');
            
            // Also log to the regular logger
            logger.error(`Error loading session artifact ${filename}: ${error.message}`);
            
            return null;
        }
    }

    /**
     * List all versions for an artifact
     */
    async listVersions(appName, userId, filename, sessionId = 'shared') {
        try {
            const artifactPath = this.getArtifactPath(appName, userId, filename, sessionId);
            const [files] = await this.bucket.getFiles({
                prefix: `${artifactPath}/v`
            });

            const versions = files
                .map(file => {
                    const match = file.name.match(/\/v(\d+)$/);
                    return match ? parseInt(match[1]) : null;
                })
                .filter(v => v !== null)
                .sort((a, b) => a - b);

            return versions;
        } catch (error) {
            logger.error(`Error listing versions for ${filename}:`, error);
            return [];
        }
    }

    /**
     * List all artifact filenames for a user
     */
    async listArtifactKeys(appName, userId) {
        try {
            const userPath = `${this.artifactsFolder}/${appName}/${userId}/`;
            const [files] = await this.bucket.getFiles({
                prefix: userPath
            });

            const filenames = new Set();
            files.forEach(file => {
                // Extract filename from path: artifacts/app/userId/filename/v1 -> filename
                const relativePath = file.name.substring(userPath.length);
                const pathParts = relativePath.split('/');
                if (pathParts.length >= 2 && pathParts[1].startsWith('v')) {
                    filenames.add(pathParts[0]);
                }
            });

            return Array.from(filenames).sort();
        } catch (error) {
            logger.error(`Error listing artifacts for user ${userId}:`, error);
            return [];
        }
    }

    /**
     * Delete all versions of an artifact
     */
    async deleteArtifact(appName, userId, filename) {
        try {
            const artifactPath = this.getArtifactPath(appName, userId, filename);
            const [files] = await this.bucket.getFiles({
                prefix: `${artifactPath}/`
            });

            const deletePromises = files.map(file => file.delete());
            await Promise.all(deletePromises);
            
            logger.info(`Deleted artifact ${filename} for user ${userId}`);
        } catch (error) {
            logger.error(`Error deleting artifact ${filename}:`, error);
            throw error;
        }
    }

    // Buffer JSON handling for proper serialization (reuse from GCSAuthState)
    bufferJSONReplacer(key, value) {
        if (value?.type === 'Buffer' && Array.isArray(value?.data)) {
            return { __buffer_type: true, data: value.data };
        }
        return value;
    }

    bufferJSONReviver(key, value) {
        if (value?.__buffer_type) {
            return Buffer.from(value.data);
        }
        return value;
    }
}

/**
 * Media File Handler for WhatsApp messages
 */
class MediaHandler {
    constructor(artifactService) {
        this.artifactService = artifactService;
    }

    /**
     * Generate a random filename if not provided
     */
    generateRandomFilename(mimeType) {
        const uuid = uuidv4();
        const extension = this.getExtensionFromMimeType(mimeType);
        return `media_${uuid}${extension}`;
    }

    /**
     * Get file extension from MIME type
     */
    getExtensionFromMimeType(mimeType) {
        const mimeToExt = {
            'image/jpeg': '.jpg',
            'image/png': '.png',
            'image/gif': '.gif',
            'image/webp': '.webp',
            'audio/mpeg': '.mp3',
            'audio/ogg': '.ogg',
            'audio/wav': '.wav',
            'audio/mp4': '.m4a',
            'video/mp4': '.mp4',
            'video/quicktime': '.mov',
            'video/x-msvideo': '.avi',
            'application/pdf': '.pdf',
            'text/plain': '.txt',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx'
        };
        return mimeToExt[mimeType] || '.bin';
    }

    /**
     * Convert XLSX buffer to text format for Gemini compatibility
     */
    convertXlsxToText(buffer) {
        try {
            const workbook = XLSX.read(buffer, { type: 'buffer' });
            let textContent = '';
            
            // Process each worksheet
            workbook.SheetNames.forEach((sheetName, index) => {
                const worksheet = workbook.Sheets[sheetName];
                
                // Add sheet header
                textContent += `\n=== Sheet ${index + 1}: ${sheetName} ===\n`;
                
                // Convert sheet to CSV format (more readable than JSON)
                const csvData = XLSX.utils.sheet_to_csv(worksheet);
                textContent += csvData + '\n';
            });
            
            return textContent;
        } catch (error) {
            logger.error('Error converting XLSX to text:', error);
            throw new Error('Failed to process Excel file. Please ensure it\'s a valid XLSX file.');
        }
    }

    /**
     * Convert DOCX buffer to text format for Gemini compatibility
     */
    async convertDocxToText(buffer) {
        try {
            const result = await mammoth.extractRawText({ buffer });
            return result.value;
        } catch (error) {
            logger.error('Error converting DOCX to text:', error);
            throw new Error('Failed to process Word document. Please ensure it\'s a valid DOCX file.');
        }
    }

    /**
     * Process media message and convert to ADK Part format
     */
    async processMediaMessage(message, userId, sessionId = 'shared') {
        try {
            // Download media from WhatsApp
            const buffer = await downloadMediaMessage(message, 'buffer', {});
            
            // Detect file type if not provided
            let mimeType = message.message.imageMessage?.mimetype ||
                          message.message.videoMessage?.mimetype ||
                          message.message.audioMessage?.mimetype ||
                          message.message.documentMessage?.mimetype ||
                          message.message.documentWithCaptionMessage?.message?.documentMessage?.mimetype;
            
            if (!mimeType) {
                const fileTypeResult = await fileTypeFromBuffer(buffer);
                mimeType = fileTypeResult?.mime || 'application/octet-stream';
            }

            // Generate filename if not provided
            let filename = message.message.documentMessage?.fileName ||
                          message.message.documentWithCaptionMessage?.message?.documentMessage?.fileName;
            if (!filename) {
                filename = this.generateRandomFilename(mimeType);
            }

            // Handle unsupported Office formats - convert to text since Gemini doesn't support them
            if (mimeType === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet') {
                logger.info(`Converting XLSX file to text format: ${filename}`);
                
                const textContent = this.convertXlsxToText(buffer);
                
                // Create text-based part for Gemini
                const part = {
                    inline_data: {
                        mime_type: 'text/plain',
                        data: Buffer.from(textContent).toString('base64')
                    },
                    mimeType: 'text/plain',
                    data: Buffer.from(textContent)
                };

                // Save artifact with converted content
                const version = await this.artifactService.saveArtifact(
                    ADK_APP_NAME,
                    userId,
                    filename.replace('.xlsx', '.txt'), // Change extension to .txt
                    part,
                    sessionId
                );

                logger.info(`Processed XLSX file as text: ${filename} -> ${filename.replace('.xlsx', '.txt')} (text/plain) v${version} for user ${userId}`);
                
                return {
                    filename: filename.replace('.xlsx', '.txt'),
                    mimeType: 'text/plain',
                    version,
                    part,
                    converted: true,
                    originalFormat: 'XLSX'
                };
            }

            // Handle DOCX files - convert to text since Gemini doesn't support DOCX
            if (mimeType === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document') {
                logger.info(`Converting DOCX file to text format: ${filename}`);
                
                const textContent = await this.convertDocxToText(buffer);
                
                // Create text-based part for Gemini
                const part = {
                    inline_data: {
                        mime_type: 'text/plain',
                        data: Buffer.from(textContent).toString('base64')
                    },
                    mimeType: 'text/plain',
                    data: Buffer.from(textContent)
                };

                // Save artifact with converted content
                const version = await this.artifactService.saveArtifact(
                    ADK_APP_NAME,
                    userId,
                    filename.replace('.docx', '.txt'), // Change extension to .txt
                    part,
                    sessionId
                );

                logger.info(`Processed DOCX file as text: ${filename} -> ${filename.replace('.docx', '.txt')} (text/plain) v${version} for user ${userId}`);
                
                return {
                    filename: filename.replace('.docx', '.txt'),
                    mimeType: 'text/plain',
                    version,
                    part,
                    converted: true,
                    originalFormat: 'DOCX'
                };
            }

            // Create ADK Part object (convert buffer to base64 for ADK API)
            const part = {
                inline_data: {
                    mime_type: mimeType,
                    data: buffer.toString('base64')
                },
                mimeType: mimeType,
                data: buffer
            };

            // Save artifact
            const version = await this.artifactService.saveArtifact(
                ADK_APP_NAME,
                userId,
                filename,
                part,
                sessionId
            );

            logger.info(`Processed media file: ${filename} (${mimeType}) v${version} for user ${userId}`);
            
            return {
                filename,
                mimeType,
                version,
                part
            };

        } catch (error) {
            logger.error('Error processing media message:', error);
            throw error;
        }
    }

    /**
     * Check if message contains media
     */
    hasMedia(message) {
        return !!(
            message.message?.imageMessage ||
            message.message?.videoMessage ||
            message.message?.audioMessage ||
            message.message?.documentMessage ||
            message.message?.documentWithCaptionMessage
        );
    }

    /**
     * Get media type from message
     */
    getMediaType(message) {
        if (message.message?.imageMessage) return 'image';
        if (message.message?.videoMessage) return 'video';
        if (message.message?.audioMessage) return 'audio';
        if (message.message?.documentMessage) return 'document';
        if (message.message?.documentWithCaptionMessage) return 'document';
        return null;
    }
}

/**
 * User Session Manager for persistent session storage in GCS
 */
class UserSessionManager {
    constructor() {
        this.sessionBucket = storage.bucket('authstate');
        this.sessionFolder = 'user_sessions';
    }

    /**
     * Get session file path for a user
     */
    getSessionFilePath(userId) {
        // Clean userId for safe file naming
        const cleanUserId = userId.replace(/[^a-zA-Z0-9@.]/g, '_');
        return `${this.sessionFolder}/${cleanUserId}/session.json`;
    }

    /**
     * Check if user exists in storage and get their session ID
     */
    async getUserSession(userId) {
        try {
            const filePath = this.getSessionFilePath(userId);
            const file = this.sessionBucket.file(filePath);
            
            const [exists] = await file.exists();
            if (!exists) {
                logger.info(`New user detected: ${userId}`);
                return null; // New user
            }

            const [data] = await file.download();
            const sessionData = JSON.parse(data.toString());
            
            logger.info(`Existing user found: ${userId}, session: ${sessionData.sessionId}`);
            return sessionData;
            
        } catch (error) {
            logger.error(`Error checking user session for ${userId}:`, error);
            return null; // Treat as new user on error
        }
    }

    /**
     * Store user session data in GCS
     */
    async storeUserSession(userId, sessionId, sessionData = {}) {
        try {
            const filePath = this.getSessionFilePath(userId);
            const file = this.sessionBucket.file(filePath);
            
            const sessionInfo = {
                userId: userId,
                sessionId: sessionId,
                createdAt: new Date().toISOString(),
                lastActivity: new Date().toISOString(),
                ...sessionData
            };

            const jsonData = JSON.stringify(sessionInfo, null, 2);
            await file.save(Buffer.from(jsonData), {
                metadata: {
                    contentType: 'application/json'
                }
            });

            logger.info(`Stored session data for user ${userId}: ${sessionId}`);
            return true;
            
        } catch (error) {
            logger.error(`Error storing user session for ${userId}:`, error);
            return false;
        }
    }

    /**
     * Update last activity timestamp for existing session
     */
    async updateUserActivity(userId) {
        try {
            const sessionData = await this.getUserSession(userId);
            if (sessionData) {
                sessionData.lastActivity = new Date().toISOString();
                await this.storeUserSession(userId, sessionData.sessionId, sessionData);
                logger.debug(`Updated activity for user ${userId}`);
            }
        } catch (error) {
            logger.error(`Error updating user activity for ${userId}:`, error);
        }
    }

    /**
     * Test GCS connectivity for session storage
     */
    async testConnection() {
        try {
            logger.info('Testing session storage GCS connection...');
            const [files] = await this.sessionBucket.getFiles({ 
                prefix: this.sessionFolder,
                maxResults: 1 
            });
            logger.info(`Session storage GCS connection successful. Found ${files.length} session files.`);
            return true;
        } catch (error) {
            logger.error('Session storage GCS connection failed:', error.message);
            return false;
        }
    }
}

/**
 * WhatsApp Bot Class
 */
class WhatsAppBot {
    constructor() {
        this.sock = null;
        this.authState = new GCSAuthState();
        this.activeSessions = new Map(); // Store user sessions
        this.artifactService = new GcsArtifactService();
        this.mediaHandler = new MediaHandler(this.artifactService);
        this.sessionManager = new UserSessionManager();
    }

    async initialize() {
        try {
            // Test session storage connection
            logger.info('Testing session storage connection...');
            const sessionStorageOk = await this.sessionManager.testConnection();
            if (!sessionStorageOk) {
                logger.error('Session storage connection failed - bot may not work properly');
            }

            // Get latest WhatsApp Web version
            const { version, isLatest } = await fetchLatestBaileysVersion();
            logger.info(`Using WhatsApp v${version.join('.')}, isLatest: ${isLatest}`);

            // Initialize auth state from GCS
            const { state, saveCreds } = await this.authState.initAuthState();

            // Create socket connection
            this.sock = makeWASocket({
                version,
                logger: logger.child({ class: 'socket' }),
                auth: state,
                printQRInTerminal: false, // We handle QR code display manually
                browser: config.whatsapp.browser,
                markOnlineOnConnect: config.whatsapp.markOnlineOnConnect,
                generateHighQualityLinkPreview: config.whatsapp.generateHighQualityLinkPreview,
                syncFullHistory: config.whatsapp.syncFullHistory,
                shouldIgnoreJid: jid => jid.endsWith('@broadcast'),
                emitOwnEvents: false,
                defaultQueryTimeoutMs: config.whatsapp.defaultQueryTimeoutMs
            });

            // Handle credential updates
            this.sock.ev.on('creds.update', saveCreds);

            // Handle connection updates
            this.sock.ev.on('connection.update', this.handleConnectionUpdate.bind(this));

            // Handle incoming messages
            this.sock.ev.on('messages.upsert', this.handleIncomingMessages.bind(this));

            // Handle message receipts
            this.sock.ev.on('messages.update', this.handleMessageUpdates.bind(this));

            logger.info('WhatsApp Bot initialized successfully');

        } catch (error) {
            logger.error('Failed to initialize WhatsApp Bot:', error);
            throw error;
        }
    }

    handleConnectionUpdate(update) {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            console.log('\n📱 QR Code for WhatsApp Web:');
            console.log('=====================================');
            qrcode.generate(qr, { small: true });
            console.log('=====================================');
            console.log('📋 Scan this QR code with your WhatsApp mobile app');
            console.log('   1. Open WhatsApp on your phone');
            console.log('   2. Go to Settings > Linked Devices');
            console.log('   3. Tap "Link a Device"');
            console.log('   4. Scan the QR code above');
            console.log('=====================================\n');
            logger.info('QR Code displayed, waiting for scan...');
        }

        if (connection === 'close') {
            const shouldReconnect = (lastDisconnect?.error instanceof Boom) 
                ? lastDisconnect.error.output?.statusCode !== DisconnectReason.loggedOut
                : true;

            logger.info(`Connection closed due to ${lastDisconnect?.error}, reconnecting: ${shouldReconnect}`);

            if (shouldReconnect) {
                setTimeout(() => this.initialize(), config.bot.retryDelayMs);
            }
        } else if (connection === 'open') {
            console.log('\n🎉 WhatsApp Bot Connected Successfully!');
            console.log('=====================================');
            console.log('✅ Bot is now online and ready to receive messages');
            console.log('📱 Users can now send messages to this WhatsApp number');
            console.log('🤖 Messages will be processed by the ADK AI system');
            console.log('=====================================\n');
            logger.info('WhatsApp connection opened successfully');
        }
    }

    async handleIncomingMessages(m) {
        try {
            const message = m.messages[0];
            
            // Enhanced debugging for PDF uploads
            logger.info(`Raw message received - message exists: ${!!message}`);
            if (message) {
                logger.info(`Message keys: ${Object.keys(message)}`);
                if (message.message) {
                    logger.info(`Message.message keys: ${Object.keys(message.message)}`);
                    logger.info(`Full message structure:`, JSON.stringify(message, null, 2));
                } else {
                    logger.warn('Message.message is null/undefined');
                }
            }
            
            if (!message.message) {
                logger.warn('Message has no content, skipping');
                return;
            }

            const remoteJid = message.key.remoteJid;
            const userId = remoteJid; // Use remoteJid as userId for ADK session
            
            // Check if message contains media
            const hasMedia = this.mediaHandler.hasMedia(message);
            const messageText = this.extractMessageText(message);
            
            // Enhanced media detection logging
            logger.info(`Media detection:`, {
                hasMedia,
                messageText,
                imageMessage: !!message.message?.imageMessage,
                videoMessage: !!message.message?.videoMessage,
                audioMessage: !!message.message?.audioMessage,
                documentMessage: !!message.message?.documentMessage,
                documentWithCaptionMessage: !!message.message?.documentWithCaptionMessage,
                messageKeys: Object.keys(message.message || {})
            });
            
            // Skip if no text and no media
            if (!messageText && !hasMedia) {
                logger.warn('Message has no text and no media, skipping');
                return;
            }
            if (!remoteJid) {
                logger.warn('Message has no remoteJid, skipping');
                return;
            }

            logger.info(`Received message from ${remoteJid}${hasMedia ? ' with media' : ''}: ${messageText || '[media only]'}`);

            // Create or get session for this user using persistent storage
            let session = this.activeSessions.get(userId);
            if (!session) {
                // Check if user exists in Google Storage
                const existingSession = await this.sessionManager.getUserSession(userId);
                
                if (existingSession) {
                    // Existing user - use stored session ID
                    session = {
                        sessionId: existingSession.sessionId,
                        userId: userId,
                        createdAt: new Date(existingSession.createdAt),
                        lastActivity: new Date(),
                        isReturningUser: true
                    };
                    
                    // Update activity in storage
                    await this.sessionManager.updateUserActivity(userId);
                    
                    logger.info(`Restored existing session ${session.sessionId} for returning user ${userId}`);
                } else {
                    // New user - create new ADK session
                    const adkSessionId = await this.createADKSession(userId);
                    if (!adkSessionId) {
                        await this.sendMessage(remoteJid, 'Sorry, I\'m unable to create a new conversation session right now. Please try again later.');
                        return;
                    }
                    
                    session = {
                        sessionId: adkSessionId,
                        userId: userId,
                        createdAt: new Date(),
                        lastActivity: new Date(),
                        isReturningUser: false
                    };
                    
                    // Store new session in GCS
                    await this.sessionManager.storeUserSession(userId, adkSessionId, {
                        isNewUser: true,
                        firstMessage: messageText || '[media]'
                    });
                    
                    logger.info(`Created new session ${session.sessionId} for new user ${userId}`);
                }
                
                this.activeSessions.set(userId, session);
            } else {
                session.lastActivity = new Date();
                // Update activity in storage for existing in-memory session
                await this.sessionManager.updateUserActivity(userId);
            }

            // Process media if present
            let mediaParts = [];
            if (hasMedia) {
                try {
                    const mediaResult = await this.mediaHandler.processMediaMessage(message, userId, session.sessionId);
                    
                    // Create Part object for ADK (use base64 data)
                    mediaParts.push({
                        inline_data: {
                            mime_type: mediaResult.mimeType,
                            data: mediaResult.part.inline_data.data
                        }
                    });
                    
                    if (mediaResult.converted) {
                        if (mediaResult.originalFormat === 'XLSX') {
                            await this.sendMessage(remoteJid, `📊 Excel file converted to text format for analysis: ${mediaResult.filename}`);
                        } else if (mediaResult.originalFormat === 'DOCX') {
                            await this.sendMessage(remoteJid, `📄 Word document converted to text format for analysis: ${mediaResult.filename}`);
                        } else {
                            await this.sendMessage(remoteJid, `🔄 ${mediaResult.originalFormat} file converted to text format: ${mediaResult.filename}`);
                        }
                    } else {
                        await this.sendMessage(remoteJid, `✅ Uploaded ${mediaResult.filename} (${mediaResult.mimeType})`);
                    }
                    logger.info(`Media processed: ${mediaResult.filename} for ${userId}${mediaResult.converted ? ' [CONVERTED from ' + mediaResult.originalFormat + ']' : ''}`);
                } catch (error) {
                    logger.error('Error processing media:', error);
                    await this.sendMessage(remoteJid, '❌ Sorry, I had trouble processing your media file. Please try again.');
                    return;
                }
            }

            // Prepare message for ADK (combine text and media)
            let adkMessage = messageText || 'I\'ve uploaded a media file for you to analyze.';
            
            // Welcome message disabled - skip greeting
            // if (!session.hasGreeted) {
            //     await this.sendWelcomeMessage(remoteJid, userId, session.sessionId, session.isReturningUser);
            //     session.hasGreeted = true;
            // }

            // Send message to ADK with streaming (including media parts)
            const response = await this.sendToADK(adkMessage, session.sessionId, userId, remoteJid, mediaParts);
            
            if (response) {
                // Handle multimodal response (text + images)
                if (typeof response === 'object' && (response.text || response.images)) {
                    // Send text message if present
                    if (response.text) {
                        await this.sendMessage(remoteJid, response.text);
                    }
                    
                    // Send images if present
                    if (response.images && response.images.length > 0) {
                        for (const image of response.images) {
                            await this.sendImage(remoteJid, image);
                        }
                    }
                } else {
                    // Fallback for text-only responses
                    await this.sendMessage(remoteJid, response);
                }
            }

        } catch (error) {
            logger.error('Error handling incoming message:', error);
        }
    }

    /**
     * Save user preference that persists across sessions
     * This demonstrates the user: prefix pattern for persistent state
     */
    async saveUserPreference(userId, sessionId, preferenceKey, preferenceValue) {
        try {
            const payload = {
                appName: ADK_APP_NAME,
                userId: userId,
                sessionId: sessionId,
                newMessage: {
                    parts: [{
                        text: `SYSTEM: Save user preference ${preferenceKey} as ${preferenceValue}`
                    }],
                    role: "system"
                },
                streaming: false,
                state_updates: {
                    [`user:${preferenceKey}`]: preferenceValue,
                    'temp:preference_updated': true
                }
            };

            const response = await axios.post(`${ADK_URL}/run`, payload, {
                headers: {
                    'Content-Type': 'application/json'
                },
                timeout: config.adk.timeout
            });

            if (response.status === 200) {
                logger.info(`Saved user preference ${preferenceKey} for user ${userId}`);
                return true;
            }
            return false;

        } catch (error) {
            logger.error(`Error saving user preference: ${error.message}`);
            return false;
        }
    }

    extractMessageText(message) {
        if (message.message.conversation) {
            return message.message.conversation;
        }
        
        if (message.message.extendedTextMessage?.text) {
            return message.message.extendedTextMessage.text;
        }

        // Handle other message types if needed
        return null;
    }

    async createADKSession(userId) {
        try {
            // Initialize session with user-scoped state for persistence
            const initialState = {
                // User-scoped state - persists across sessions (logout/login)
                'user:first_interaction': new Date().toISOString(),
                'user:total_sessions': 1,
                'user:whatsapp_number': userId,
                'user:conversation_history_count': 0,
                
                // Session-scoped state - reset on new session
                'current_session_start': new Date().toISOString(),
                'session_message_count': 0,
                
                // App-scoped state (if needed)
                'app:bot_version': '1.0.0'
            };

            const payload = {
                appName: ADK_APP_NAME,
                userId: userId,
                state: initialState
            };

            logger.info(`Creating ADK session for user: ${userId} with persistent user state`);

            const response = await axios.post(`${ADK_URL}/apps/${ADK_APP_NAME}/users/${userId}/sessions`, payload, {
                headers: {
                    'Content-Type': 'application/json'
                },
                timeout: config.adk.timeout
            });

            if (response.status === 200 && response.data.id) {
                logger.info(`Created ADK session: ${response.data.id} for user: ${userId}`);
                
                // If this is a returning user, increment their session count
                await this.updateReturnUserState(response.data.id, userId);
                
                return response.data.id;
            } else {
                logger.error(`Failed to create ADK session: ${response.status}`);
                return null;
            }
        } catch (error) {
            logger.error('Error creating ADK session:', error.message);
            return null;
        }
    }

    async updateReturnUserState(sessionId, userId) {
        try {
            // Check if user has previous sessions by trying to get their user-scoped state
            // If they do, this updates user:total_sessions counter
            const payload = {
                appName: ADK_APP_NAME,
                userId: userId,
                sessionId: sessionId,
                newMessage: {
                    parts: [{
                        text: "SYSTEM: Update user session count"
                    }],
                    role: "system"
                },
                streaming: false,
                state_updates: {
                    // Increment user session count for returning users
                    'user:total_sessions': 'INCREMENT',
                    'user:last_login': new Date().toISOString(),
                    'temp:session_init': true
                }
            };

            // This is a system call to update state, not a user message
            logger.debug(`Updating return user state for session: ${sessionId}`);
            
            // Note: We won't send this as a regular message, but use it to establish persistent state
            // The actual state persistence happens automatically via ADK's user: prefix pattern
            
        } catch (error) {
            logger.warn('Could not update return user state:', error.message);
            // This is non-critical, session will still work
        }
    }

    async sendWelcomeMessage(remoteJid, userId, sessionId, isReturningUser = false) {
        try {
            let welcomeMessage;
            
            if (isReturningUser) {
                // Returning user - get their persistent state
                try {
                    const sessionResponse = await axios.get(`${ADK_URL}/apps/${ADK_APP_NAME}/users/${userId}/sessions/${sessionId}`, {
                        headers: { 'Content-Type': 'application/json' },
                        timeout: config.adk.timeout
                    });

                    if (sessionResponse.status === 200 && sessionResponse.data.state) {
                        const state = sessionResponse.data.state;
                        const userTotalSessions = state['user:total_sessions'] || 'multiple';
                        const userFirstInteraction = state['user:first_interaction'];
                        
                        if (userFirstInteraction) {
                            const firstDate = new Date(userFirstInteraction).toLocaleDateString();
                            welcomeMessage = `Welcome back! 🎉 Great to see you again! You first used this bot on ${firstDate}. I've restored your previous conversation context. How can I help you today?`;
                        } else {
                            welcomeMessage = `Welcome back! 🎉 I've restored your previous conversation context. How can I help you today?`;
                        }
                    } else {
                        welcomeMessage = `Welcome back! 🎉 I've restored your previous conversation. How can I help you today?`;
                    }
                } catch (error) {
                    logger.warn('Error getting state for returning user:', error.message);
                    welcomeMessage = `Welcome back! 🎉 I've restored your previous conversation. How can I help you today?`;
                }
            } else {
                // New user
                welcomeMessage = `Welcome to your AI assistant! 👋 This is your first time using this bot. I can help you with questions, analyze documents and images, generate content, and much more. How can I assist you today?`;
            }
            
            await this.sendMessage(remoteJid, welcomeMessage);
            logger.info(`Sent ${isReturningUser ? 'returning' : 'new'} user welcome message to ${userId}`);
            
        } catch (error) {
            logger.warn('Could not send personalized welcome message:', error.message);
            // Fallback welcome message
            try {
                await this.sendMessage(remoteJid, '👋 Welcome to your AI assistant! How can I help you today?');
            } catch (fallbackError) {
                logger.error('Failed to send even fallback welcome message:', fallbackError.message);
            }
        }
    }

    async sendToADK(message, sessionId, userId, jid, mediaParts = []) {
        try {
            // Prepare message parts (text + media)
            const parts = [
                {
                    text: message
                }
            ];
            
            // Add media parts if present
            if (mediaParts && mediaParts.length > 0) {
                parts.push(...mediaParts);
            }

            const payload = {
                appName: ADK_APP_NAME,
                userId: userId,
                sessionId: sessionId,
                newMessage: {
                    parts: parts,
                    role: "user"
                },
                streaming: false, // Disable streaming to test non-streaming responses
                // Include system context about user state persistence
                systemContext: {
                    instructions: "You have access to persistent user state with 'user:' prefix. Use user:total_sessions, user:first_interaction, user:last_login, and other user: prefixed state to personalize responses. Session-scoped state resets on new sessions. Remember user preferences and conversation history across sessions."
                }
            };

            logger.info(`Sending to ADK (non-streaming): ${JSON.stringify(payload)}`);

            // Use regular endpoint for non-streaming
            const response = await axios.post(`${ADK_URL}/run`, payload, {
                headers: {
                    'Content-Type': 'application/json'
                },
                timeout: config.adk.timeout,
                validateStatus: function (status) {
                    return status >= 200 && status < 600;
                }
            });

            logger.info(`ADK Response Status: ${response.status}`);
            
            // Handle 500 errors - might be invalid session, try creating a new one
            if (response.status === 500) {
                logger.warn(`ADK Service Error (500), trying with new session...`);
                
                // Try creating a new session and retry
                const newSessionId = await this.createADKSession(userId);
                if (newSessionId) {
                    payload.sessionId = newSessionId;
                    
                    // Update the session in memory
                    if (this.activeSessions && this.activeSessions.has(userId)) {
                        this.activeSessions.get(userId).sessionId = newSessionId;
                    }
                    
                    // Retry non-streaming request
                    return await this.sendToADK(message, newSessionId, userId, jid, mediaParts);
                }
                
                logger.error(`ADK Service Error: Unable to create new session`);
                return 'I apologize, but the AI service is currently experiencing issues. The development team has been notified. Please try again later.';
            }
            
            // Process successful non-streaming response
            if (response.status === 200) {
                return await this.handleNonStreamingResponse(response.data, jid, sessionId);
            }

            // Fallback - return informative error message
            logger.info(`ADK Error Status: ${response.status}`);
            return 'I received your message, but the AI service returned an unexpected response. Please try again.';

        } catch (error) {
            logger.error('Error calling ADK API:', error.message);
            
            // Return error message to user
            if (error.response) {
                logger.error(`ADK Error Response: ${JSON.stringify(error.response.data)}`);
                return `Sorry, I encountered an error: ${error.response.status} ${error.response.statusText}`;
            } else if (error.code === 'ECONNREFUSED') {
                return 'Sorry, the AI service is currently unavailable. Please try again later.';
            } else if (error.code === 'ECONNABORTED') {
                return 'Sorry, the request timed out. Please try again with a shorter message.';
            } else {
                return 'Sorry, I encountered an unexpected error. Please try again.';
            }
        }
    }

    async handleStreamingResponse(stream, jid) {
        return new Promise((resolve, reject) => {
            let buffer = '';
            let fullResponse = '';
            let hasStarted = false;
            
            stream.on('data', (chunk) => {
                buffer += chunk.toString();
                
                // Process complete lines (SSE events)
                const lines = buffer.split('\n');
                buffer = lines.pop() || ''; // Keep incomplete line in buffer
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const jsonData = line.substring(6); // Remove "data: " prefix
                            
                            // Skip empty data lines
                            if (jsonData.trim() === '') continue;
                            
                            const eventData = JSON.parse(jsonData);
                            
                            // Extract text from the event
                            if (eventData.content && eventData.content.parts) {
                                const textPart = eventData.content.parts.find(part => part.text && !part.thoughtSignature);
                                if (textPart && textPart.text) {
                                    fullResponse = textPart.text;
                                    hasStarted = true;
                                    logger.debug(`Streaming chunk received: ${textPart.text.length} chars`);
                                }
                            }
                            
                            // Check if this is the final response (not partial)
                            if (eventData.partial !== true && fullResponse) {
                                logger.info(`ADK Streaming Final Response: ${fullResponse.substring(0, 100)}...`);
                                resolve(fullResponse);
                                return;
                            }
                            
                        } catch (parseError) {
                            logger.warn('Error parsing SSE data:', parseError.message);
                            // Continue processing other lines
                        }
                    }
                }
            });
            
            stream.on('end', () => {
                if (fullResponse) {
                    logger.info(`ADK Streaming Complete: ${fullResponse.length} characters`);
                    resolve(fullResponse);
                } else {
                    logger.warn('ADK Streaming ended without response');
                    resolve('I received your message, but the response was incomplete. Please try again.');
                }
            });
            
            stream.on('error', (error) => {
                logger.error('ADK Streaming error:', error.message);
                reject(error);
            });
            
            // Timeout handling - increased timeout for streaming
            setTimeout(() => {
                if (fullResponse) {
                    logger.info(`ADK Streaming timeout reached, returning current response: ${fullResponse.length} characters`);
                    resolve(fullResponse);
                } else {
                    logger.warn('ADK Streaming timeout without response');
                    resolve('Response timed out. Please try again with a shorter message.');
                }
            }, config.adk.timeout * 2); // Double timeout for streaming
        });
    }

    async handleNonStreamingResponse(data, jid, sessionId) {
        try {
            logger.info(`ADK Non-Streaming Response: ${JSON.stringify(data)}`);
            
            // Extract response from data - return both text and images
            let responseText = '';
            let imageParts = [];
            let artifactImages = [];
            
            if (data && data.response) {
                responseText = data.response;
            } else if (data && data.content && data.content.parts) {
                // Process all parts - text and images
                for (const part of data.content.parts) {
                    if (part.text) {
                        responseText += part.text;
                    } else if (part.inline_data && part.inline_data.mime_type && part.inline_data.data) {
                        imageParts.push({
                            mimeType: part.inline_data.mime_type,
                            data: part.inline_data.data
                        });
                    }
                }
            } else if (typeof data === 'string') {
                responseText = data;
            } else if (Array.isArray(data)) {
                // Handle array response format
                for (const event of data) {
                    if (event.content && event.content.parts && event.content.parts.length > 0) {
                        for (const part of event.content.parts) {
                            if (part.text) {
                                responseText += part.text;
                            } else if (part.inline_data && part.inline_data.mime_type && part.inline_data.data) {
                                imageParts.push({
                                    mimeType: part.inline_data.mime_type,
                                    data: part.inline_data.data
                                });
                            }
                        }
                    } else if (event.response) {
                        responseText = event.response;
                    }

                    // Check for artifact images in artifactDelta
                    if (event.actions && event.actions.artifactDelta) {
                        const userId = this.getUserIdFromJid(jid);
                        for (const artifactName in event.actions.artifactDelta) {
                            // Check if this is an image artifact
                            if (artifactName.includes('.png') || artifactName.includes('.jpg') || artifactName.includes('.jpeg') || artifactName.includes('.webp')) {
                                try {
                                    logger.info(`Fetching image artifact: ${artifactName} for user: ${userId}, session: ${sessionId}`);
                                    const imageData = await this.artifactService.loadArtifactBySession('app', userId, sessionId, artifactName);
                                    if (imageData && imageData.data) {
                                        artifactImages.push({
                                            mimeType: imageData.mimeType || 'image/png',
                                            data: imageData.data
                                        });
                                        logger.info(`Successfully fetched image artifact: ${artifactName}`);
                                    }
                                } catch (error) {
                                    logger.error(`Error fetching image artifact ${artifactName}:`, error);
                                }
                            }
                        }
                    }
                }
            }

            // Combine inline images and artifact images
            const allImages = [...imageParts, ...artifactImages];
            
            if (responseText || allImages.length > 0) {
                logger.info(`ADK Final Response: Text=${responseText ? responseText.substring(0, 100) + '...' : 'none'} Images=${allImages.length}`);
                return {
                    text: responseText || 'Here\'s your generated image:',
                    images: allImages
                };
            } else {
                logger.warn('No valid response text or images found in ADK response');
                return {
                    text: 'I received your message, but the AI service returned an unexpected response format. Please try rephrasing your question.',
                    images: []
                };
            }
            
        } catch (error) {
            logger.error('Error handling non-streaming response:', error);
            return {
                text: 'Sorry, I encountered an error processing the AI response. Please try again.',
                images: []
            };
        }
    }

    getUserIdFromJid(jid) {
        // Extract userId from WhatsApp JID (e.g., "6592377976@s.whatsapp.net" -> "6592377976@s.whatsapp.net")
        return jid;
    }

    parseADKResponse(data) {
        try {
            // ADK returns an array of events, we need to extract the response
            if (Array.isArray(data)) {
                let finalResponse = '';
                
                for (const event of data) {
                    // Look for content in the event
                    if (event.content && event.content.parts && event.content.parts.length > 0) {
                        const textPart = event.content.parts.find(part => part.text);
                        if (textPart) {
                            finalResponse = textPart.text;
                        }
                    } else if (event.response) {
                        finalResponse = event.response;
                    }
                }
                
                if (finalResponse) {
                    logger.info(`ADK Final Response: ${finalResponse}`);
                    return finalResponse;
                }
            }

            // Fallback - return informative error message
            logger.info(`ADK Raw Response: ${JSON.stringify(data)}`);
            return 'I received your message, but the AI service returned an unexpected response format. Please try rephrasing your question.';
        } catch (error) {
            logger.error('Error parsing ADK response:', error);
            return 'Sorry, I encountered an error processing the AI response. Please try again.';
        }
    }

    async sendMessage(jid, text) {
        try {
            // WhatsApp has message length limits, so we need to chunk long messages
            const maxLength = 800; // More conservative limit for reliable WhatsApp delivery
            
            if (text.length <= maxLength) {
                await this.sock.sendMessage(jid, { text: text });
                logger.info(`Sent message to ${jid}: ${text}`);
            } else {
                // Split long messages into chunks
                const chunks = this.splitMessage(text, maxLength);
                for (let i = 0; i < chunks.length; i++) {
                    const chunk = chunks[i];
                    const chunkText = chunks.length > 1 ? `📄 *Part ${i + 1}/${chunks.length}*\n\n${chunk}` : chunk;
                    
                    await this.sock.sendMessage(jid, { text: chunkText });
                    logger.info(`Sent message chunk ${i + 1}/${chunks.length} to ${jid}: ${chunk.substring(0, 100)}...`);
                    
                    // Add small delay between chunks
                    if (i < chunks.length - 1) {
                        await new Promise(resolve => setTimeout(resolve, 500));
                    }
                }
            }
        } catch (error) {
            logger.error(`Failed to send message to ${jid}:`, error);
        }
    }

    async sendImage(jid, imageData) {
        try {
            // Convert base64 to Buffer
            const buffer = Buffer.from(imageData.data, 'base64');
            
            logger.info(`Sending image to ${jid}: ${imageData.mimeType}, size: ${buffer.length} bytes`);
            
            await this.sock.sendMessage(jid, { 
                image: buffer, 
                mimetype: imageData.mimeType,
                caption: '🎨 Generated image'
            });
            
            logger.info(`Successfully sent image to ${jid}`);
        } catch (error) {
            logger.error(`Failed to send image to ${jid}:`, error);
            // Fallback - send error message
            await this.sendMessage(jid, '❌ Sorry, I had trouble sending the generated image. Please try again.');
        }
    }

    splitMessage(text, maxLength) {
        if (text.length <= maxLength) {
            return [text];
        }

        const chunks = [];
        let currentChunk = '';
        
        // Split by sentences first, then by words if needed
        const sentences = text.split(/([.!?]+\s*)/);
        
        for (let i = 0; i < sentences.length; i++) {
            const sentence = sentences[i];
            
            if ((currentChunk + sentence).length <= maxLength) {
                currentChunk += sentence;
            } else {
                if (currentChunk) {
                    chunks.push(currentChunk.trim());
                    currentChunk = '';
                }
                
                // If single sentence is too long, split by words
                if (sentence.length > maxLength) {
                    const words = sentence.split(' ');
                    let wordChunk = '';
                    
                    for (const word of words) {
                        if ((wordChunk + ' ' + word).length <= maxLength) {
                            wordChunk += (wordChunk ? ' ' : '') + word;
                        } else {
                            if (wordChunk) {
                                chunks.push(wordChunk);
                                wordChunk = word;
                            } else {
                                // Single word is too long, force split
                                chunks.push(word.substring(0, maxLength));
                                wordChunk = word.substring(maxLength);
                            }
                        }
                    }
                    
                    if (wordChunk) {
                        currentChunk = wordChunk;
                    }
                } else {
                    currentChunk = sentence;
                }
            }
        }
        
        if (currentChunk) {
            chunks.push(currentChunk.trim());
        }
        
        return chunks.filter(chunk => chunk.length > 0);
    }

    handleMessageUpdates(updates) {
        // Handle message receipt confirmations, read receipts, etc.
        updates.forEach(update => {
            if (update.update.status) {
                logger.debug(`Message ${update.key.id} status: ${update.update.status}`);
            }
        });
    }

    generateSessionId() {
        return `wa_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    // Clean up old sessions periodically
    cleanupSessions() {
        const now = new Date();
        const maxAge = config.bot.sessionMaxAgeMs;

        for (const [userId, session] of this.activeSessions.entries()) {
            if (now - session.lastActivity > maxAge) {
                this.activeSessions.delete(userId);
                logger.info(`Cleaned up expired session for user ${userId}`);
            }
        }
    }

    async start() {
        try {
            await this.initialize();
            
            // Clean up sessions periodically
            setInterval(() => {
                this.cleanupSessions();
            }, config.bot.sessionCleanupIntervalMs);

        } catch (error) {
            logger.error('Failed to start WhatsApp Bot:', error);
            process.exit(1);
        }
    }
}

// Handle graceful shutdown
process.on('SIGINT', () => {
    logger.info('Received SIGINT, shutting down gracefully...');
    process.exit(0);
});

process.on('SIGTERM', () => {
    logger.info('Received SIGTERM, shutting down gracefully...');
    process.exit(0);
});

// Start the bot
if (require.main === module) {
    const bot = new WhatsAppBot();
    bot.start().catch(error => {
        logger.error('Bot startup failed:', error);
        process.exit(1);
    });
}

module.exports = WhatsAppBot;
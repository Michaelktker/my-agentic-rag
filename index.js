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
const ADK_URL = process.env.ADK_URL || config.adk.url; // Keep for backward compatibility
const ADK_APP_NAME = process.env.ADK_APP_NAME || config.adk.appName;
const BUCKET_NAME = process.env.BUCKET_NAME || config.gcs.bucketName;
// Note: ARTIFACTS_BUCKET_NAME removed - artifact persistence now handled server-side by ADK
const PROJECT_ID = process.env.PROJECT_ID || config.gcs.projectId;

// ADK Endpoint Configuration with fallback
const PRODUCTION_ADK_URL = process.env.PRODUCTION_ADK_URL || 'https://my-agentic-rag-638797485217.us-central1.run.app';
const STAGING_ADK_URL = process.env.STAGING_ADK_URL || 'https://my-agentic-rag-454188184539.us-central1.run.app';
const LOCALHOST_ADK_URL = process.env.LOCALHOST_ADK_URL || 'http://localhost:8000';
const HEALTH_CHECK_TIMEOUT = parseInt(process.env.HEALTH_CHECK_TIMEOUT || '5000'); // 5 seconds in milliseconds

console.log('🔧 WhatsApp Bot Configuration:');
console.log(`📍 Production ADK URL: ${PRODUCTION_ADK_URL}`);
console.log(`📍 Staging ADK URL: ${STAGING_ADK_URL}`);
console.log(`📍 Localhost ADK URL: ${LOCALHOST_ADK_URL}`);
console.log(`🏥 Health check timeout: ${HEALTH_CHECK_TIMEOUT}ms`);
console.log(`📱 App Name: ${ADK_APP_NAME}`);

// Initialize Google Cloud Storage for session management only
const storage = new Storage({ projectId: PROJECT_ID });
const bucket = storage.bucket(BUCKET_NAME);
// Note: artifactsBucket removed - artifact operations now handled server-side by ADK

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
 * Health check function for ADK endpoints
 */
async function checkEndpointHealth(url, timeout = HEALTH_CHECK_TIMEOUT) {
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);
        
        // Try health endpoint first
        const healthUrl = `${url.replace(/\/$/, '')}/health`;
        const response = await fetch(healthUrl, { 
            signal: controller.signal,
            method: 'GET'
        });
        
        clearTimeout(timeoutId);
        
        if (response.ok) {
            logger.debug(`✅ Health check passed for ${url}`);
            return true;
        }
        
        logger.debug(`❌ Health check failed for ${url}: ${response.status}`);
        return false;
        
    } catch (error) {
        logger.debug(`❌ Health check failed for ${url}:`, error.message);
        return false;
    }
}

/**
 * Get active ADK endpoint with fallback logic
 */
async function getActiveAdkEndpoint() {
    logger.info('🔍 Checking ADK endpoint health...');
    
    // Try production first
    if (await checkEndpointHealth(PRODUCTION_ADK_URL)) {
        logger.info(`✅ Using production endpoint: ${PRODUCTION_ADK_URL}`);
        return PRODUCTION_ADK_URL;
    }
    
    // Fallback to staging
    logger.warn('⚠️ Production unavailable, trying staging...');
    if (await checkEndpointHealth(STAGING_ADK_URL)) {
        logger.info(`✅ Using staging endpoint: ${STAGING_ADK_URL}`);
        return STAGING_ADK_URL;
    }
    
    // Final fallback to localhost for local development
    logger.warn('⚠️ Both cloud endpoints unavailable, trying localhost...');
    if (await checkEndpointHealth(LOCALHOST_ADK_URL)) {
        logger.info(`✅ Using localhost endpoint: ${LOCALHOST_ADK_URL}`);
        return LOCALHOST_ADK_URL;
    }
    
    // All endpoints down - use production and let error bubble up
    logger.error(`❌ All endpoints unavailable (production, staging, localhost), defaulting to production`);
    return PRODUCTION_ADK_URL;
}

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
 * Media File Handler for WhatsApp messages
 * Simplified to only process media without client-side GCS operations
 * All artifact management is handled server-side by ADK
 */
class MediaHandler {
    constructor() {
        // No artifactService needed - ADK handles all persistence
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

                logger.info(`Processed XLSX file as text: ${filename} -> ${filename.replace('.xlsx', '.txt')} (text/plain) for user ${userId}`);
                
                return {
                    filename: filename.replace('.xlsx', '.txt'),
                    mimeType: 'text/plain',
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

                logger.info(`Processed DOCX file as text: ${filename} -> ${filename.replace('.docx', '.txt')} (text/plain) for user ${userId}`);
                
                return {
                    filename: filename.replace('.docx', '.txt'),
                    mimeType: 'text/plain',
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

            logger.info(`Processed media file: ${filename} (${mimeType}) for user ${userId}`);
            
            return {
                filename,
                mimeType,
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
        this.mediaHandler = new MediaHandler();
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
                shouldIgnoreJid: jid => jid && jid.endsWith('@broadcast'),
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
                
                // Always create a new ADK session (ADK sessions are ephemeral)
                const adkSessionId = await this.createADKSession(userId);
                if (!adkSessionId) {
                    await this.sendMessage(remoteJid, 'Sorry, I\'m unable to create a new conversation session right now. Please try again later.');
                    return;
                }
                
                if (existingSession) {
                    // Existing user - create new ADK session but keep user context
                    session = {
                        sessionId: adkSessionId,
                        userId: userId,
                        createdAt: new Date(),
                        lastActivity: new Date(),
                        isReturningUser: true
                    };
                    
                    // Update session storage with new ADK session ID
                    await this.sessionManager.storeUserSession(userId, adkSessionId, {
                        isReturningUser: true,
                        previousSessionDate: existingSession.createdAt
                    });
                    
                    logger.info(`Created new ADK session ${session.sessionId} for returning user ${userId}`);
                } else {
                    // New user - create new ADK session
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
            let adkMessage = messageText;
            
            // Auto-trigger @Myker when media is uploaded
            if (mediaParts.length > 0) {
                if (!messageText) {
                    // Media only: Request renaming
                    adkMessage = '@Myker I\'ve uploaded a media file to rename_and_save_media_artifact.';
                } else {
                    // Media + text: Request renaming and public URL, then append user's text
                    adkMessage = '@Myker I\'ve uploaded a media file to rename_and_save_media_artifact and make_artifact_public. ' + messageText;
                }
            }
            
            // Welcome message disabled - skip greeting
            // if (!session.hasGreeted) {
            //     await this.sendWelcomeMessage(remoteJid, userId, session.sessionId, session.isReturningUser);
            //     session.hasGreeted = true;
            // }

            // Send message to ADK with streaming (including media parts)
            logger.info(`🚀 Sending to ADK: message="${adkMessage}", mediaParts=${mediaParts.length}, session=${session.sessionId}`);
            const response = await this.sendToADK(adkMessage, session.sessionId, userId, remoteJid, mediaParts);
            logger.info(`📨 ADK Response received: ${response ? 'Success' : 'No response'}`);
            
            if (response) {
                // Handle multimodal response (text + images)
                if (typeof response === 'object' && (response.text || response.images)) {
                    // Send text message if present
                    if (response.text) {
                        logger.info(`📤 Sending text response to user: ${response.text.substring(0, 100)}...`);
                        await this.sendMessage(remoteJid, response.text);
                    }
                    
                    // Send images if present
                    if (response.images && response.images.length > 0) {
                        logger.info(`📤 Sending ${response.images.length} images to user`);
                        for (const image of response.images) {
                            await this.sendImage(remoteJid, image);
                        }
                    }
                } else {
                    // Fallback for text-only responses
                    logger.info(`📤 Sending fallback text response to user: ${response.substring(0, 100)}...`);
                    await this.sendMessage(remoteJid, response);
                }
            } else {
                logger.info(`ℹ️ No response from ADK, message handling complete`);
            }

        } catch (error) {
            logger.error('Error handling incoming message:', error);
            logger.error('Error message:', error.message || 'No error message');
            logger.error('Error name:', error.name || 'No error name');
            logger.error('Error stack:', error.stack || 'No stack trace');
            logger.error('Error details:', {
                message: error.message,
                name: error.name,
                stack: error.stack,
                toString: error.toString(),
                errorType: typeof error
            });
            
            // Send error message to user
            try {
                const remoteJid = message?.key?.remoteJid;
                if (remoteJid) {
                    await this.sendMessage(remoteJid, '❌ Sorry, I encountered an error processing your message. Please try again.');
                }
            } catch (sendError) {
                logger.error('Failed to send error message to user:', sendError);
            }
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
            // Get the active ADK endpoint
            const adkUrl = await getActiveAdkEndpoint();
            
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
                sessionId: this.generateSessionId(),
                state: initialState,
                events: null
            };

            logger.info(`📤 Creating ADK session for user: ${userId} using endpoint: ${adkUrl}`);

            const response = await axios.post(`${adkUrl}/apps/${ADK_APP_NAME}/users/${encodeURIComponent(userId)}/sessions`, payload, {
                headers: {
                    'Content-Type': 'application/json'
                },
                timeout: config.adk.timeout,
                validateStatus: function (status) {
                    return status >= 200 && status < 600;
                }
            });

            if (response.status === 200 && response.data.id) {
                logger.info(`✅ Created ADK session: ${response.data.id} for user: ${userId}`);
                
                // If this is a returning user, increment their session count
                await this.updateReturnUserState(response.data.id, userId);
                
                return response.data.id;
            } else {
                logger.error(`Failed to create ADK session: ${response.status}`);
                logger.error(`Response data:`, response.data);
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
            // Get the active ADK endpoint
            const adkUrl = await getActiveAdkEndpoint();
            
            let welcomeMessage;
            
            if (isReturningUser) {
                // Returning user - get their persistent state
                try {
                    const sessionResponse = await axios.get(`${adkUrl}/apps/${ADK_APP_NAME}/users/${userId}/sessions/${sessionId}`, {
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
            // Get the active ADK endpoint
            const adkUrl = await getActiveAdkEndpoint();
            
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
                stateDelta: null // Optional state changes for the session
            };

            logger.info(`📤 Sending to ADK: ${adkUrl}/run`);
            logger.debug(`Payload: ${JSON.stringify(payload)}`);

            // Use selected endpoint for request
            const response = await axios.post(`${adkUrl}/run`, payload, {
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
                    
                    // Retry request
                    return await this.sendToADK(message, newSessionId, userId, jid, mediaParts);
                }
                
                logger.error(`ADK Service Error: Unable to create new session`);
                return 'I apologize, but the AI service is currently experiencing issues. The development team has been notified. Please try again later.';
            }
            
            // Process successful response
            if (response.status === 200) {
                return await this.handleNonStreamingResponse(response.data, jid, sessionId);
            }

            // Fallback - return informative error message
            logger.info(`ADK Error Status: ${response.status}`);
            return 'I received your message, but the AI service returned an unexpected response. Please try again.';

        } catch (error) {
            logger.error('❌ ADK request failed:', error.message);
            
            // Emergency fallback if this was production and it failed
            if (error.config && error.config.url && error.config.url.includes('production')) {
                logger.warn('🔄 Attempting emergency fallback to staging...');
                try {
                    const payload = {
                        appName: ADK_APP_NAME,
                        userId: userId,
                        sessionId: sessionId,
                        newMessage: {
                            parts: [{ text: message }, ...mediaParts],
                            role: "user"
                        },
                        streaming: false,
                        systemContext: {
                            instructions: "You have access to persistent user state with 'user:' prefix. Use user:total_sessions, user:first_interaction, user:last_login, and other user: prefixed state to personalize responses. Session-scoped state resets on new sessions. Remember user preferences and conversation history across sessions."
                        }
                    };

                    const fallbackResponse = await axios.post(`${STAGING_ADK_URL}/run`, payload, {
                        headers: { 'Content-Type': 'application/json' },
                        timeout: config.adk.timeout,
                        validateStatus: function (status) {
                            return status >= 200 && status < 600;
                        }
                    });

                    if (fallbackResponse.status === 200) {
                        logger.info('✅ Emergency fallback to staging successful');
                        return await this.handleNonStreamingResponse(fallbackResponse.data, jid, sessionId);
                    }
                    
                } catch (fallbackError) {
                    logger.error('❌ Emergency fallback also failed:', fallbackError.message);
                }
            }
            
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
            
            // Handle empty response (happens when no @Myker mention) - ignore silently
            if (!data || (Array.isArray(data) && data.length === 0)) {
                logger.info('Empty ADK response (likely no @Myker mention) - ignoring message silently');
                return null; // Return null to indicate no response should be sent
            }
            
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
                    // NOTE: Artifact loading removed - ADK handles all artifact management server-side
                    // Images generated by ADK are returned directly in the response
                    if (event.actions && event.actions.artifactDelta) {
                        logger.info(`ArtifactDelta detected in response - artifacts are managed by ADK server-side`);
                        // Legacy client-side artifact loading has been removed
                        // All artifacts are now handled by ADK's tool_context on the server
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
            // Check if this is an empty response (no @Myker mention) - return null instead of error
            if (Array.isArray(data) && data.length === 0) {
                logger.info('Empty ADK response detected in fallback - returning null');
                return null;
            }
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

    /**
     * Start polling for webhook-generated outbound messages
     */
    startWebhookMessagePolling() {
        logger.info('🔄 Starting webhook message polling...');
        
        // Poll every 30 seconds for outbound messages
        setInterval(async () => {
            try {
                await this.processWebhookMessages();
            } catch (error) {
                logger.error('Error processing webhook messages:', error);
            }
        }, 30000); // 30 second interval
    }

    /**
     * Process outbound messages from webhook callbacks
     */
    async processWebhookMessages() {
        try {
            // List outbound messages from GCS
            const [files] = await bucket.getFiles({
                prefix: 'outbound_messages/',
                maxResults: 10 // Process up to 10 messages per poll
            });

            if (files.length === 0) {
                return; // No messages to process
            }

            logger.info(`📬 Processing ${files.length} webhook messages...`);

            for (const file of files) {
                try {
                    // Download and parse message
                    const [data] = await file.download();
                    const messageData = JSON.parse(data.toString());

                    // Validate message format
                    if (messageData.jid && messageData.message) {
                        logger.info(`📤 Sending webhook message to ${messageData.jid}: ${messageData.message.substring(0, 100)}...`);
                        
                        // Send the message
                        await this.sendMessage(messageData.jid, messageData.message);
                        
                        // Delete processed message
                        await file.delete();
                        logger.info(`✅ Processed and deleted webhook message: ${file.name}`);
                        
                        // Add small delay between messages
                        await new Promise(resolve => setTimeout(resolve, 1000));
                    } else {
                        logger.warn(`❌ Invalid message format: ${file.name}`);
                        // Delete invalid message
                        await file.delete();
                    }
                } catch (messageError) {
                    logger.error(`❌ Error processing message ${file.name}:`, messageError);
                    // Don't delete on processing error - might be temporary
                }
            }
        } catch (error) {
            logger.error('❌ Error in webhook message polling:', error);
        }
    }

    async start() {
        try {
            await this.initialize();
            
            // Clean up sessions periodically
            setInterval(() => {
                this.cleanupSessions();
            }, config.bot.sessionCleanupIntervalMs);

            // Start webhook message polling
            this.startWebhookMessagePolling();

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
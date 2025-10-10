const makeWASocket = require('@whiskeysockets/baileys').default;
const { DisconnectReason, useMultiFileAuthState, downloadMediaMessage, fetchLatestBaileysVersion } = require('@whiskeysockets/baileys');
const { Boom } = require('@hapi/boom');
const P = require('pino');
const axios = require('axios');
const { Storage } = require('@google-cloud/storage');
const fs = require('fs');
const path = require('path');
const qrcode = require('qrcode-terminal');

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
const PROJECT_ID = process.env.PROJECT_ID || config.gcs.projectId;

// Initialize Google Cloud Storage
const storage = new Storage({ projectId: PROJECT_ID });
const bucket = storage.bucket(BUCKET_NAME);

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
 * WhatsApp Bot Class
 */
class WhatsAppBot {
    constructor() {
        this.sock = null;
        this.authState = new GCSAuthState();
        this.activeSessions = new Map(); // Store user sessions
    }

    async initialize() {
        try {
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
            if (!message.message) return;

            const remoteJid = message.key.remoteJid;
            const messageText = this.extractMessageText(message);
            
            if (!messageText || !remoteJid) return;

            logger.info(`Received message from ${remoteJid}: ${messageText}`);

            // Use remoteJid as userId for ADK session
            const userId = remoteJid;

            // Create or get session for this user
            let session = this.activeSessions.get(userId);
            if (!session) {
                // Create a new ADK session
                const adkSessionId = await this.createADKSession(userId);
                if (!adkSessionId) {
                    await this.sendMessage(remoteJid, 'Sorry, I\'m unable to create a new conversation session right now. Please try again later.');
                    return;
                }
                
                session = {
                    sessionId: adkSessionId,
                    userId: userId,
                    createdAt: new Date(),
                    lastActivity: new Date()
                };
                this.activeSessions.set(userId, session);
                logger.info(`Created new session ${session.sessionId} for user ${userId}`);
            } else {
                session.lastActivity = new Date();
            }

            // Send message to ADK with streaming
            const response = await this.sendToADK(messageText, session.sessionId, userId, remoteJid);
            
            if (response) {
                // Send complete response back to WhatsApp in one message
                await this.sendMessage(remoteJid, response);
            }

        } catch (error) {
            logger.error('Error handling incoming message:', error);
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
            const payload = {
                appName: ADK_APP_NAME,
                userId: userId,
                state: {}
            };

            logger.info(`Creating ADK session for user: ${userId}`);

            const response = await axios.post(`${ADK_URL}/apps/${ADK_APP_NAME}/users/${userId}/sessions`, payload, {
                headers: {
                    'Content-Type': 'application/json'
                },
                timeout: config.adk.timeout
            });

            if (response.status === 200 && response.data.id) {
                logger.info(`Created ADK session: ${response.data.id}`);
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

    async sendToADK(message, sessionId, userId, jid) {
        try {
            const payload = {
                appName: ADK_APP_NAME,
                userId: userId,
                sessionId: sessionId,
                newMessage: {
                    parts: [
                        {
                            text: message
                        }
                    ],
                    role: "user"
                },
                streaming: true // Enable streaming for real-time responses
            };

            logger.info(`Sending to ADK (streaming): ${JSON.stringify(payload)}`);

            // Use streaming endpoint
            const response = await axios.post(`${ADK_URL}/run_sse`, payload, {
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'text/event-stream'
                },
                responseType: 'stream',
                timeout: config.adk.timeout,
                validateStatus: function (status) {
                    return status >= 200 && status < 600;
                }
            });

            logger.info(`ADK Streaming Response Status: ${response.status}`);
            
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
                    
                    // Retry streaming request
                    return await this.sendToADK(message, newSessionId, userId, jid);
                }
                
                logger.error(`ADK Service Error: Unable to create new session`);
                return 'I apologize, but the AI service is currently experiencing issues. The development team has been notified. Please try again later.';
            }
            
            // Process successful streaming response
            if (response.status === 200) {
                return await this.handleStreamingResponse(response.data, jid);
            }

            // Fallback - return informative error message
            logger.info(`ADK Streaming Error Status: ${response.status}`);
            return 'I received your message, but the AI service returned an unexpected response. Please try again.';

        } catch (error) {
            logger.error('Error calling ADK Streaming API:', error.message);
            
            // Return error message to user
            if (error.response) {
                logger.error(`ADK Streaming Error Response: ${JSON.stringify(error.response.data)}`);
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
            
            // Send initial "thinking" indicator only once
            this.sendMessage(jid, '🤖 *Processing your request...*');
            
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
            await this.sock.sendMessage(jid, { text: text });
            logger.info(`Sent message to ${jid}: ${text}`);
        } catch (error) {
            logger.error(`Failed to send message to ${jid}:`, error);
        }
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
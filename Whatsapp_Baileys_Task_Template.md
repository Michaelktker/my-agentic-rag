# WhatsApp Baileys - Task Template

## 🚀 Overview

Baileys is a powerful TypeScript/JavaScript library that provides a direct WebSocket API for interacting with WhatsApp Web without requiring a browser. This template provides a comprehensive guide for building production-ready WhatsApp bots and applications using Baileys.

## 🏗️ Core Architecture & Concepts

### 1. **Connection Management**

#### **Basic Socket Initialization**
```typescript
import makeWASocket, { DisconnectReason, useMultiFileAuthState } from '@whiskeysockets/baileys'
import { Boom } from '@hapi/boom'

async function connectToWhatsApp() {
    // Load authentication state
    const { state, saveCreds } = await useMultiFileAuthState('auth_info_baileys')
    
    // Create socket
    const sock = makeWASocket({
        auth: state,
        printQRInTerminal: true,
        browser: ['My WhatsApp Bot', 'Chrome', '1.0.0'],
        syncFullHistory: true,
        markOnlineOnConnect: false,
        defaultQueryTimeoutMs: 60000
    })
    
    // Handle connection updates
    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect } = update
        
        if (connection === 'close') {
            const shouldReconnect = (lastDisconnect?.error as Boom)?.output?.statusCode !== DisconnectReason.loggedOut
            
            console.log('Connection closed:', lastDisconnect?.error, 'Reconnecting:', shouldReconnect)
            
            if (shouldReconnect) {
                connectToWhatsApp()
            }
        } else if (connection === 'open') {
            console.log('WhatsApp connected successfully!')
        }
    })
    
    // Save credentials when updated
    sock.ev.on('creds.update', saveCreds)
    
    return sock
}
```

#### **Authentication Methods**

**QR Code Authentication:**
```typescript
import QRCode from 'qrcode'

sock.ev.on('connection.update', async (update) => {
    const { qr } = update
    
    if (qr) {
        // Display QR code in terminal
        console.log(await QRCode.toString(qr, { type: 'terminal' }))
        
        // Or send QR to frontend
        // sendQRToFrontend(qr)
    }
})
```

**Pairing Code Authentication:**
```typescript
async function authenticateWithPairingCode(phoneNumber: string) {
    const { state, saveCreds } = await useMultiFileAuthState('auth_info')
    
    const sock = makeWASocket({
        auth: state,
        printQRInTerminal: false
    })
    
    // Request pairing code for unregistered devices
    if (!sock.authState.creds.registered) {
        const code = await sock.requestPairingCode(phoneNumber) // Format: "1234567890" (no symbols)
        console.log(`Pairing code: ${code}`)
        // User enters this code in WhatsApp: Settings > Linked Devices > Link Device
    }
    
    sock.ev.on('creds.update', saveCreds)
    return sock
}
```

### 2. **Message Handling**

#### **Receiving Messages**
```typescript
import { downloadMediaMessage, getContentType } from '@whiskeysockets/baileys'
import fs from 'fs'

sock.ev.on('messages.upsert', async ({ messages, type }) => {
    if (type !== 'notify') return // Only handle new messages
    
    for (const message of messages) {
        // Skip messages from self
        if (message.key.fromMe) continue
        
        const remoteJid = message.key.remoteJid
        const messageContent = message.message
        
        if (!messageContent) continue
        
        // Handle different message types
        if (messageContent.conversation) {
            // Text message
            const text = messageContent.conversation
            console.log(`Text from ${remoteJid}: ${text}`)
            
            // Auto-reply
            await sock.sendMessage(remoteJid, {
                text: `You said: ${text}`
            })
        }
        
        if (messageContent.extendedTextMessage) {
            // Extended text with links/mentions
            const text = messageContent.extendedTextMessage.text
            const contextInfo = messageContent.extendedTextMessage.contextInfo
            
            console.log(`Extended text: ${text}`)
            if (contextInfo?.mentionedJid) {
                console.log('Mentioned users:', contextInfo.mentionedJid)
            }
        }
        
        if (messageContent.imageMessage) {
            // Image message
            console.log('Received image message')
            
            try {
                const buffer = await downloadMediaMessage(
                    message,
                    'buffer',
                    {},
                    {
                        logger: console,
                        reuploadRequest: sock.updateMediaMessage
                    }
                )
                
                // Save image
                fs.writeFileSync(`./downloads/image-${message.key.id}.jpg`, buffer)
                
                // Reply with confirmation
                await sock.sendMessage(remoteJid, {
                    text: 'Image received and saved!'
                })
            } catch (error) {
                console.error('Error downloading image:', error)
            }
        }
        
        // Mark message as read
        await sock.readMessages([message.key])
    }
})

// Handle message updates (edits, deletes, reactions)
sock.ev.on('messages.update', (updates) => {
    for (const { key, update } of updates) {
        if (update.pollUpdates) {
            console.log('Poll updated:', key.id)
        }
        
        if (update.messageStubType) {
            console.log('Message status updated:', key.id)
        }
    }
})
```

#### **Sending Messages**

**Text Messages:**
```typescript
// Basic text
await sock.sendMessage('1234567890@s.whatsapp.net', {
    text: 'Hello, World!'
})

// Text with mentions
await sock.sendMessage(groupJid, {
    text: '@1234567890 @9876543210 check this out!',
    mentions: ['1234567890@s.whatsapp.net', '9876543210@s.whatsapp.net']
})

// Text with link preview
await sock.sendMessage(jid, {
    text: 'Check out: https://github.com/whiskeysockets/baileys'
})

// Reply to a message
await sock.sendMessage(jid, 
    { text: 'This is a reply' },
    { quoted: originalMessage }
)
```

**Media Messages:**
```typescript
// Send image
await sock.sendMessage(jid, {
    image: { url: './photo.jpg' },  // Can be URL, Buffer, or stream
    caption: 'Beautiful sunset!',
    jpegThumbnail: fs.readFileSync('./thumb.jpg').toString('base64')
})

// Send video
await sock.sendMessage(jid, {
    video: fs.readFileSync('./video.mp4'),
    caption: 'Check this out!',
    gifPlayback: false,  // Set to true for GIF-like playback
    ptv: false  // Set to true for video note
})

// Send audio/voice note
await sock.sendMessage(jid, {
    audio: { url: './voice.ogg' },
    mimetype: 'audio/ogg; codecs=opus',
    ptt: true,  // Present as voice note
    waveform: [0, 10, 20, 30, 25, 15, 5]  // Voice waveform
})

// Send document
await sock.sendMessage(jid, {
    document: { url: './report.pdf' },
    mimetype: 'application/pdf',
    fileName: 'Monthly Report.pdf',
    caption: 'Here is the report'
})

// Send sticker
await sock.sendMessage(jid, {
    sticker: fs.readFileSync('./sticker.webp'),
    isAnimated: false
})

// Send location
await sock.sendMessage(jid, {
    location: {
        degreesLatitude: 24.121231,
        degreesLongitude: 55.1121221,
        name: 'My Location',
        address: '123 Main Street'
    }
})

// Send contact
const vcard = 'BEGIN:VCARD\n' +
    'VERSION:3.0\n' +
    'FN:John Doe\n' +
    'ORG:Company Inc;\n' +
    'TEL;type=CELL;type=VOICE;waid=1234567890:+1 234 567 890\n' +
    'END:VCARD'

await sock.sendMessage(jid, {
    contacts: {
        displayName: 'John Doe',
        contacts: [{ vcard }]
    }
})

// Send view-once message
await sock.sendMessage(jid, {
    image: { url: './private.jpg' },
    viewOnce: true,
    caption: 'This will disappear after viewing'
})
```

### 3. **Advanced Messaging Features**

#### **Message Reactions**
```typescript
// Add reaction
await sock.sendMessage(jid, {
    react: {
        text: '❤️',
        key: message.key
    }
})

// Remove reaction
await sock.sendMessage(jid, {
    react: {
        text: '',  // Empty string removes reaction
        key: message.key
    }
})

// Handle incoming reactions
sock.ev.on('messages.reaction', (reactions) => {
    for (const reaction of reactions) {
        console.log(`${reaction.key.participant} reacted with ${reaction.reaction.text}`)
    }
})
```

#### **Message Editing and Deletion**
```typescript
// Send message
const sentMessage = await sock.sendMessage(jid, {
    text: 'Original mesage'  // Typo intentional
})

// Edit message (within 15 minutes)
await sock.sendMessage(jid, {
    text: 'Original message',  // Fixed typo
    edit: sentMessage.key
})

// Delete message for everyone
await sock.sendMessage(jid, {
    delete: sentMessage.key
})

// Delete message for self only
await sock.chatModify({
    clear: {
        messages: [{
            id: sentMessage.key.id,
            fromMe: true,
            timestamp: sentMessage.messageTimestamp
        }]
    }
}, jid)
```

#### **Polls**
```typescript
// Create single-choice poll
await sock.sendMessage(jid, {
    poll: {
        name: 'What should we do this weekend?',
        values: ['Go hiking', 'Watch movies', 'Play games', 'Stay home'],
        selectableCount: 1
    }
})

// Create multiple-choice poll
await sock.sendMessage(groupJid, {
    poll: {
        name: 'Pick your favorite programming languages',
        values: ['JavaScript', 'Python', 'Go', 'Rust', 'TypeScript'],
        selectableCount: 3
    }
})

// Handle poll updates
sock.ev.on('messages.update', async (updates) => {
    for (const { key, update } of updates) {
        if (update.pollUpdates) {
            const pollCreation = await getMessage(key) // Implement getMessage
            
            if (pollCreation) {
                const aggregatedVotes = getAggregateVotesInPollMessage({
                    message: pollCreation,
                    pollUpdates: update.pollUpdates
                })
                
                console.log('Poll results:', aggregatedVotes)
            }
        }
    }
})
```

### 4. **Presence and Status Management**

#### **Presence Updates**
```typescript
// Set availability status
await sock.sendPresenceUpdate('available')  // Online
await sock.sendPresenceUpdate('unavailable')  // Offline

// Chat-specific presence
await sock.sendPresenceUpdate('composing', jid)  // Typing
await sock.sendPresenceUpdate('recording', jid)  // Recording audio
await sock.sendPresenceUpdate('paused', jid)    // Stop typing/recording

// Subscribe to someone's presence
await sock.presenceSubscribe(jid)

// Handle presence updates
sock.ev.on('presence.update', ({ id, presences }) => {
    for (const [jid, presence] of Object.entries(presences)) {
        console.log(`${jid} is ${presence.lastKnownPresence}`)
    }
})

// Send message with typing simulation
async function sendWithTyping(jid: string, text: string) {
    await sock.presenceSubscribe(jid)
    await sock.sendPresenceUpdate('composing', jid)
    await new Promise(resolve => setTimeout(resolve, 2000))
    await sock.sendPresenceUpdate('paused', jid)
    await sock.sendMessage(jid, { text })
}
```

### 5. **Group Management**

#### **Group Operations**
```typescript
// Create group
const group = await sock.groupCreate(
    'My Awesome Group',
    ['1234567890@s.whatsapp.net', '9876543210@s.whatsapp.net']
)
console.log(`Created group: ${group.id}`)

// Get group metadata
const metadata = await sock.groupMetadata(group.id)
console.log(`Group: ${metadata.subject}`)
console.log(`Description: ${metadata.desc}`)
console.log(`Participants: ${metadata.participants.length}`)

// Update group settings
await sock.groupUpdateSubject(group.id, 'Updated Group Name')
await sock.groupUpdateDescription(group.id, 'New group description')

// Group privacy settings
await sock.groupSettingUpdate(group.id, 'announcement')    // Only admins can send
await sock.groupSettingUpdate(group.id, 'not_announcement') // Everyone can send
await sock.groupSettingUpdate(group.id, 'locked')         // Only admins can edit
await sock.groupSettingUpdate(group.id, 'unlocked')       // Everyone can edit

// Participant management
await sock.groupParticipantsUpdate(group.id, ['user@s.whatsapp.net'], 'add')
await sock.groupParticipantsUpdate(group.id, ['user@s.whatsapp.net'], 'remove')
await sock.groupParticipantsUpdate(group.id, ['user@s.whatsapp.net'], 'promote')
await sock.groupParticipantsUpdate(group.id, ['user@s.whatsapp.net'], 'demote')

// Invite management
const inviteCode = await sock.groupInviteCode(group.id)
console.log(`Invite link: https://chat.whatsapp.com/${inviteCode}`)

// Join group via invite
await sock.groupAcceptInvite('INVITE_CODE_HERE')

// Get group info without joining
const groupInfo = await sock.groupGetInviteInfo('INVITE_CODE_HERE')
console.log('Group info:', groupInfo)

// Leave group
await sock.groupLeave(group.id)
```

### 6. **Chat Management**

#### **Chat Operations**
```typescript
// Archive/unarchive chat
const lastMessage = // Get from store
await sock.chatModify({ archive: true, lastMessages: [lastMessage] }, jid)
await sock.chatModify({ archive: false, lastMessages: [lastMessage] }, jid)

// Mute/unmute chat
await sock.chatModify({ mute: 8 * 60 * 60 * 1000 }, jid)  // 8 hours
await sock.chatModify({ mute: null }, jid)  // Unmute

// Pin/unpin chat
await sock.chatModify({ pin: true }, jid)
await sock.chatModify({ pin: false }, jid)

// Mark as read/unread
await sock.chatModify({ markRead: true, lastMessages: [lastMessage] }, jid)
await sock.chatModify({ markRead: false, lastMessages: [lastMessage] }, jid)

// Delete chat
await sock.chatModify({
    delete: true,
    lastMessages: [{
        key: lastMessage.key,
        messageTimestamp: lastMessage.messageTimestamp
    }]
}, jid)
```

#### **Disappearing Messages**
```typescript
// Enable disappearing messages (24 hours)
await sock.sendMessage(jid, {
    disappearingMessagesInChat: 86400
})

// Disable disappearing messages
await sock.sendMessage(jid, {
    disappearingMessagesInChat: false
})

// Send single ephemeral message
await sock.sendMessage(jid,
    { text: 'This will disappear in 24 hours' },
    { ephemeralExpiration: 86400 }
)

// Group ephemeral settings
await sock.groupToggleEphemeral(groupJid, 604800)  // 7 days
await sock.groupToggleEphemeral(groupJid, 0)       // Disable
```

### 7. **Data Storage & Management**

#### **In-Memory Store**
```typescript
import { makeInMemoryStore } from '@whiskeysockets/baileys'

// Create store
const store = makeInMemoryStore({})

// Load from file
store.readFromFile('./baileys_store.json')

// Save to file periodically
setInterval(() => {
    store.writeToFile('./baileys_store.json')
}, 10_000)

// Bind to socket
store.bind(sock.ev)

// Access stored data
sock.ev.on('chats.upsert', () => {
    const allChats = store.chats.all()
    console.log(`Total chats: ${allChats.length}`)
})

// Implement getMessage for better functionality
const sock = makeWASocket({
    auth: state,
    getMessage: async (key) => {
        const jid = key.remoteJid
        const id = key.id
        const message = store.messages[jid]?.get(id)
        return message?.message
    }
})
```

#### **Custom Database Storage**
```typescript
interface AuthState {
    creds: AuthenticationCreds
    keys: SignalDataTypeMap
}

class DatabaseAuthState {
    private userId: string
    
    constructor(userId: string) {
        this.userId = userId
    }
    
    async loadAuthState(): Promise<AuthState> {
        // Load from database
        const creds = await db.getCredentials(this.userId)
        const keys = await db.getKeys(this.userId)
        
        return { creds, keys }
    }
    
    async saveAuthState(state: Partial<AuthState>) {
        if (state.creds) {
            await db.saveCredentials(this.userId, state.creds)
        }
        if (state.keys) {
            await db.saveKeys(this.userId, state.keys)
        }
    }
}

// Usage
const authState = new DatabaseAuthState('user123')
const { creds, keys } = await authState.loadAuthState()

const sock = makeWASocket({
    auth: { creds, keys }
})

sock.ev.on('creds.update', (update) => {
    authState.saveAuthState({ creds: update })
})

sock.ev.on('keys.update', (update) => {
    authState.saveAuthState({ keys: update })
})
```

### 8. **Privacy & Security Settings**

#### **Privacy Management**
```typescript
// Block/unblock users
await sock.updateBlockStatus('1234567890@s.whatsapp.net', 'block')
await sock.updateBlockStatus('1234567890@s.whatsapp.net', 'unblock')

// Get blocked users
const blocklist = await sock.fetchBlocklist()
console.log('Blocked users:', blocklist)

// Privacy settings
await sock.updateLastSeenPrivacy('contacts')        // all, contacts, contact_blacklist, none
await sock.updateOnlinePrivacy('match_last_seen')   // all, match_last_seen
await sock.updateProfilePicturePrivacy('contacts')  // all, contacts, contact_blacklist, none
await sock.updateStatusPrivacy('contacts')          // all, contacts, contact_blacklist, none
await sock.updateReadReceiptsPrivacy('all')         // all, none
await sock.updateGroupsAddPrivacy('contacts')       // all, contacts, contact_blacklist

// Fetch current privacy settings
const privacySettings = await sock.fetchPrivacySettings(true)
console.log('Privacy settings:', privacySettings)
```

### 9. **Profile Management**

#### **Profile Operations**
```typescript
// Update profile name
await sock.updateProfileName('My New Name')

// Update profile status
await sock.updateProfileStatus('Hello, World!')

// Update profile picture
await sock.updateProfilePicture(jid, { url: './new-profile-pic.jpg' })

// Remove profile picture
await sock.removeProfilePicture(jid)

// Get profile picture
const ppUrl = await sock.profilePictureUrl(jid, 'image')  // 'image' for high-res
console.log('Profile picture URL:', ppUrl)

// Get user status
const status = await sock.fetchStatus(jid)
console.log('User status:', status)

// Check if number exists on WhatsApp
const [result] = await sock.onWhatsApp('1234567890')
if (result?.exists) {
    console.log(`Number exists: ${result.jid}`)
}

// Get business profile
const businessProfile = await sock.getBusinessProfile(jid)
if (businessProfile) {
    console.log('Business info:', businessProfile)
}
```

## 🛠️ Implementation Patterns

### 1. **Bot Framework Structure**
```typescript
import makeWASocket, { 
    DisconnectReason, 
    useMultiFileAuthState,
    makeInMemoryStore,
    downloadMediaMessage,
    getContentType
} from '@whiskeysockets/baileys'
import { Boom } from '@hapi/boom'
import P from 'pino'

class WhatsAppBot {
    private sock: any
    private store: any
    private logger: any
    
    constructor() {
        this.logger = P({ level: 'info' })
        this.store = makeInMemoryStore({})
        this.setupStore()
    }
    
    private setupStore() {
        // Load store from file
        try {
            this.store.readFromFile('./bot_store.json')
        } catch (error) {
            console.log('No existing store found, starting fresh')
        }
        
        // Save store periodically
        setInterval(() => {
            this.store.writeToFile('./bot_store.json')
        }, 30_000)
    }
    
    async connect() {
        const { state, saveCreds } = await useMultiFileAuthState('./auth_session')
        
        this.sock = makeWASocket({
            auth: state,
            logger: this.logger,
            printQRInTerminal: true,
            browser: ['WhatsApp Bot', 'Chrome', '1.0.0'],
            syncFullHistory: false,
            markOnlineOnConnect: false,
            generateHighQualityLinkPreview: true,
            getMessage: this.getMessage.bind(this)
        })
        
        // Bind store to socket
        this.store.bind(this.sock.ev)
        
        // Setup event handlers
        this.sock.ev.on('connection.update', this.handleConnection.bind(this))
        this.sock.ev.on('creds.update', saveCreds)
        this.sock.ev.on('messages.upsert', this.handleMessages.bind(this))
        this.sock.ev.on('messages.update', this.handleMessageUpdates.bind(this))
        this.sock.ev.on('presence.update', this.handlePresence.bind(this))
        this.sock.ev.on('chats.upsert', this.handleChats.bind(this))
        this.sock.ev.on('contacts.upsert', this.handleContacts.bind(this))
    }
    
    private async getMessage(key: any) {
        const jid = key.remoteJid
        const id = key.id
        const message = this.store.messages[jid]?.get(id)
        return message?.message
    }
    
    private handleConnection(update: any) {
        const { connection, lastDisconnect } = update
        
        if (connection === 'close') {
            const shouldReconnect = (lastDisconnect?.error as Boom)?.output?.statusCode !== DisconnectReason.loggedOut
            
            this.logger.info({ lastDisconnect }, 'Connection closed')
            
            if (shouldReconnect) {
                setTimeout(() => this.connect(), 5000)
            }
        } else if (connection === 'open') {
            this.logger.info('WhatsApp connection opened')
        }
    }
    
    private async handleMessages({ messages, type }: any) {
        if (type !== 'notify') return
        
        for (const message of messages) {
            if (message.key.fromMe) continue
            
            await this.processMessage(message)
        }
    }
    
    private async processMessage(message: any) {
        const jid = message.key.remoteJid
        const messageContent = message.message
        
        if (!messageContent) return
        
        try {
            // Handle different message types
            if (messageContent.conversation) {
                await this.handleTextMessage(jid, messageContent.conversation, message)
            } else if (messageContent.extendedTextMessage) {
                await this.handleTextMessage(jid, messageContent.extendedTextMessage.text, message)
            } else if (messageContent.imageMessage) {
                await this.handleMediaMessage(jid, message, 'image')
            } else if (messageContent.videoMessage) {
                await this.handleMediaMessage(jid, message, 'video')
            } else if (messageContent.audioMessage) {
                await this.handleMediaMessage(jid, message, 'audio')
            } else if (messageContent.documentMessage) {
                await this.handleMediaMessage(jid, message, 'document')
            }
            
            // Mark as read
            await this.sock.readMessages([message.key])
            
        } catch (error) {
            this.logger.error({ error, jid }, 'Error processing message')
        }
    }
    
    private async handleTextMessage(jid: string, text: string, message: any) {
        console.log(`Text from ${jid}: ${text}`)
        
        // Command processing
        if (text.startsWith('/')) {
            await this.handleCommand(jid, text, message)
        } else {
            // Regular message processing
            await this.handleRegularMessage(jid, text, message)
        }
    }
    
    private async handleCommand(jid: string, command: string, message: any) {
        const [cmd, ...args] = command.split(' ')
        
        switch (cmd.toLowerCase()) {
            case '/help':
                await this.sendMessage(jid, {
                    text: `Available commands:
/help - Show this help
/ping - Test bot response
/info - Get bot information
/weather <city> - Get weather info
/joke - Get a random joke`
                })
                break
                
            case '/ping':
                await this.sendMessage(jid, { text: 'Pong! 🏓' })
                break
                
            case '/info':
                await this.sendMessage(jid, {
                    text: `🤖 WhatsApp Bot
Version: 1.0.0
Status: Online
Uptime: ${process.uptime()} seconds`
                })
                break
                
            case '/weather':
                if (args.length > 0) {
                    await this.getWeather(jid, args.join(' '))
                } else {
                    await this.sendMessage(jid, { text: 'Please provide a city name. Usage: /weather <city>' })
                }
                break
                
            case '/joke':
                await this.sendRandomJoke(jid)
                break
                
            default:
                await this.sendMessage(jid, { text: 'Unknown command. Type /help for available commands.' })
        }
    }
    
    private async handleRegularMessage(jid: string, text: string, message: any) {
        // AI or rule-based response logic
        if (text.toLowerCase().includes('hello') || text.toLowerCase().includes('hi')) {
            await this.sendMessage(jid, { text: 'Hello! How can I help you today?' })
        }
    }
    
    private async handleMediaMessage(jid: string, message: any, type: string) {
        console.log(`Received ${type} from ${jid}`)
        
        try {
            const buffer = await downloadMediaMessage(
                message,
                'buffer',
                {},
                {
                    logger: this.logger,
                    reuploadRequest: this.sock.updateMediaMessage
                }
            )
            
            // Process media (save, analyze, etc.)
            const filename = `./downloads/${type}-${message.key.id}`
            require('fs').writeFileSync(filename, buffer)
            
            await this.sendMessage(jid, {
                text: `✅ ${type.charAt(0).toUpperCase() + type.slice(1)} received and processed!`
            })
            
        } catch (error) {
            this.logger.error({ error }, `Error downloading ${type}`)
            await this.sendMessage(jid, {
                text: `❌ Failed to process ${type}`
            })
        }
    }
    
    private async sendMessage(jid: string, content: any, options: any = {}) {
        try {
            return await this.sock.sendMessage(jid, content, options)
        } catch (error) {
            this.logger.error({ error, jid }, 'Error sending message')
        }
    }
    
    private async getWeather(jid: string, city: string) {
        // Mock weather API call
        await this.sendMessage(jid, {
            text: `🌤️ Weather in ${city}:
Temperature: 25°C
Condition: Partly Cloudy
Humidity: 60%
Wind: 10 km/h`
        })
    }
    
    private async sendRandomJoke(jid: string) {
        const jokes = [
            "Why don't scientists trust atoms? Because they make up everything!",
            "Why did the scarecrow win an award? He was outstanding in his field!",
            "Why don't eggs tell jokes? They'd crack each other up!"
        ]
        
        const joke = jokes[Math.floor(Math.random() * jokes.length)]
        await this.sendMessage(jid, { text: `😄 ${joke}` })
    }
    
    private handleMessageUpdates(updates: any) {
        for (const { key, update } of updates) {
            if (update.pollUpdates) {
                console.log('Poll updated:', key.id)
            }
        }
    }
    
    private handlePresence({ id, presences }: any) {
        for (const [jid, presence] of Object.entries(presences)) {
            console.log(`${jid} is ${(presence as any).lastKnownPresence}`)
        }
    }
    
    private handleChats(chats: any) {
        console.log(`Received ${chats.length} chat updates`)
    }
    
    private handleContacts(contacts: any) {
        console.log(`Received ${contacts.length} contact updates`)
    }
    
    async start() {
        console.log('Starting WhatsApp Bot...')
        await this.connect()
    }
    
    async stop() {
        if (this.sock) {
            this.sock.end()
        }
        this.store.writeToFile('./bot_store.json')
        console.log('Bot stopped')
    }
}

// Usage
const bot = new WhatsAppBot()
bot.start()

// Graceful shutdown
process.on('SIGINT', async () => {
    console.log('Shutting down bot...')
    await bot.stop()
    process.exit(0)
})
```

### 2. **Multi-Session Management**
```typescript
class MultiSessionManager {
    private sessions: Map<string, any> = new Map()
    private logger = P({ level: 'info' })
    
    async createSession(sessionId: string, phoneNumber?: string) {
        if (this.sessions.has(sessionId)) {
            throw new Error(`Session ${sessionId} already exists`)
        }
        
        const { state, saveCreds } = await useMultiFileAuthState(`./sessions/${sessionId}`)
        
        const sock = makeWASocket({
            auth: state,
            logger: this.logger.child({ sessionId }),
            printQRInTerminal: !phoneNumber,
            browser: [`Bot-${sessionId}`, 'Chrome', '1.0.0']
        })
        
        // Handle pairing code if phone number provided
        if (phoneNumber && !sock.authState.creds.registered) {
            const code = await sock.requestPairingCode(phoneNumber)
            console.log(`Pairing code for ${sessionId}: ${code}`)
        }
        
        sock.ev.on('creds.update', saveCreds)
        
        this.sessions.set(sessionId, {
            sock,
            phoneNumber,
            connected: false,
            lastActivity: Date.now()
        })
        
        // Setup connection handling
        sock.ev.on('connection.update', (update: any) => {
            const { connection } = update
            const session = this.sessions.get(sessionId)
            
            if (session) {
                session.connected = connection === 'open'
                if (connection === 'open') {
                    session.lastActivity = Date.now()
                }
            }
        })
        
        return sessionId
    }
    
    getSession(sessionId: string) {
        return this.sessions.get(sessionId)
    }
    
    async sendMessage(sessionId: string, jid: string, content: any) {
        const session = this.getSession(sessionId)
        if (!session?.connected) {
            throw new Error(`Session ${sessionId} not connected`)
        }
        
        return await session.sock.sendMessage(jid, content)
    }
    
    async destroySession(sessionId: string) {
        const session = this.sessions.get(sessionId)
        if (session) {
            session.sock.end()
            this.sessions.delete(sessionId)
        }
    }
    
    listSessions() {
        return Array.from(this.sessions.entries()).map(([id, session]) => ({
            id,
            connected: session.connected,
            phoneNumber: session.phoneNumber,
            lastActivity: session.lastActivity
        }))
    }
}
```

### 3. **Message Queue System**
```typescript
import { EventEmitter } from 'events'

interface QueuedMessage {
    id: string
    sessionId: string
    jid: string
    content: any
    options?: any
    timestamp: number
    retries: number
    maxRetries: number
}

class MessageQueue extends EventEmitter {
    private queue: QueuedMessage[] = []
    private processing = false
    private sessionManager: MultiSessionManager
    
    constructor(sessionManager: MultiSessionManager) {
        super()
        this.sessionManager = sessionManager
    }
    
    addMessage(sessionId: string, jid: string, content: any, options: any = {}) {
        const message: QueuedMessage = {
            id: `${Date.now()}-${Math.random()}`,
            sessionId,
            jid,
            content,
            options,
            timestamp: Date.now(),
            retries: 0,
            maxRetries: 3
        }
        
        this.queue.push(message)
        this.emit('messageAdded', message)
        
        if (!this.processing) {
            this.processQueue()
        }
        
        return message.id
    }
    
    private async processQueue() {
        if (this.processing || this.queue.length === 0) return
        
        this.processing = true
        
        while (this.queue.length > 0) {
            const message = this.queue.shift()!
            
            try {
                await this.sendMessage(message)
                this.emit('messageSent', message)
            } catch (error) {
                message.retries++
                
                if (message.retries <= message.maxRetries) {
                    // Re-queue with delay
                    setTimeout(() => {
                        this.queue.unshift(message)
                    }, 1000 * message.retries)
                } else {
                    this.emit('messageFailed', message, error)
                }
            }
            
            // Rate limiting
            await new Promise(resolve => setTimeout(resolve, 1000))
        }
        
        this.processing = false
    }
    
    private async sendMessage(message: QueuedMessage) {
        const session = this.sessionManager.getSession(message.sessionId)
        
        if (!session?.connected) {
            throw new Error(`Session ${message.sessionId} not connected`)
        }
        
        return await session.sock.sendMessage(message.jid, message.content, message.options)
    }
    
    getQueueStatus() {
        return {
            pending: this.queue.length,
            processing: this.processing
        }
    }
}
```

## 🚀 Production Deployment

### 1. **Docker Configuration**
```dockerfile
# Dockerfile
FROM node:18-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci --only=production

# Copy source code
COPY . .

# Create necessary directories
RUN mkdir -p ./auth_sessions ./downloads ./logs

# Set permissions
RUN chown -R node:node /app
USER node

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD node healthcheck.js

EXPOSE 3000

CMD ["node", "index.js"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  whatsapp-bot:
    build: .
    restart: unless-stopped
    volumes:
      - ./auth_sessions:/app/auth_sessions
      - ./downloads:/app/downloads
      - ./logs:/app/logs
    environment:
      - NODE_ENV=production
      - LOG_LEVEL=info
    ports:
      - "3000:3000"
    
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - redis_data:/data
    
  mongodb:
    image: mongo:6
    restart: unless-stopped
    volumes:
      - mongo_data:/data/db
    environment:
      - MONGO_INITDB_ROOT_USERNAME=admin
      - MONGO_INITDB_ROOT_PASSWORD=password

volumes:
  redis_data:
  mongo_data:
```

### 2. **Environment Configuration**
```typescript
// config.ts
export const config = {
    // Bot settings
    botName: process.env.BOT_NAME || 'WhatsApp Bot',
    logLevel: process.env.LOG_LEVEL || 'info',
    autoReconnect: process.env.AUTO_RECONNECT === 'true',
    
    // Session settings
    sessionPath: process.env.SESSION_PATH || './auth_sessions',
    storePath: process.env.STORE_PATH || './store',
    
    // Rate limiting
    messageDelay: parseInt(process.env.MESSAGE_DELAY || '1000'),
    maxRetries: parseInt(process.env.MAX_RETRIES || '3'),
    
    // Media settings
    maxMediaSize: parseInt(process.env.MAX_MEDIA_SIZE || '100') * 1024 * 1024, // MB
    downloadPath: process.env.DOWNLOAD_PATH || './downloads',
    
    // Database
    mongoUrl: process.env.MONGO_URL || 'mongodb://localhost:27017/whatsapp-bot',
    
    // Redis
    redisUrl: process.env.REDIS_URL || 'redis://localhost:6379',
    
    // API settings
    port: parseInt(process.env.PORT || '3000'),
    apiKey: process.env.API_KEY,
    
    // Webhook
    webhookUrl: process.env.WEBHOOK_URL,
    webhookSecret: process.env.WEBHOOK_SECRET
}
```

### 3. **API Server Integration**
```typescript
import express from 'express'
import cors from 'cors'
import helmet from 'helmet'
import rateLimit from 'express-rate-limit'

class WhatsAppAPI {
    private app = express()
    private bot: WhatsAppBot
    
    constructor(bot: WhatsAppBot) {
        this.bot = bot
        this.setupMiddleware()
        this.setupRoutes()
    }
    
    private setupMiddleware() {
        this.app.use(helmet())
        this.app.use(cors())
        this.app.use(express.json({ limit: '10mb' }))
        
        // Rate limiting
        const limiter = rateLimit({
            windowMs: 15 * 60 * 1000, // 15 minutes
            max: 100 // limit each IP to 100 requests per windowMs
        })
        this.app.use('/api/', limiter)
        
        // Auth middleware
        this.app.use('/api/', (req, res, next) => {
            const apiKey = req.headers['x-api-key']
            if (!apiKey || apiKey !== config.apiKey) {
                return res.status(401).json({ error: 'Invalid API key' })
            }
            next()
        })
    }
    
    private setupRoutes() {
        // Health check
        this.app.get('/health', (req, res) => {
            res.json({
                status: 'ok',
                timestamp: new Date().toISOString(),
                uptime: process.uptime()
            })
        })
        
        // Send message
        this.app.post('/api/send-message', async (req, res) => {
            try {
                const { sessionId, jid, content, options } = req.body
                
                if (!sessionId || !jid || !content) {
                    return res.status(400).json({
                        error: 'Missing required fields: sessionId, jid, content'
                    })
                }
                
                const result = await this.bot.sendMessage(sessionId, jid, content, options)
                
                res.json({
                    success: true,
                    messageId: result.key.id,
                    timestamp: result.messageTimestamp
                })
            } catch (error) {
                res.status(500).json({
                    error: 'Failed to send message',
                    details: error.message
                })
            }
        })
        
        // Get session status
        this.app.get('/api/sessions/:sessionId/status', (req, res) => {
            const { sessionId } = req.params
            const session = this.bot.getSession(sessionId)
            
            if (!session) {
                return res.status(404).json({ error: 'Session not found' })
            }
            
            res.json({
                sessionId,
                connected: session.connected,
                lastActivity: session.lastActivity
            })
        })
        
        // Create session
        this.app.post('/api/sessions', async (req, res) => {
            try {
                const { sessionId, phoneNumber } = req.body
                
                if (!sessionId) {
                    return res.status(400).json({ error: 'sessionId is required' })
                }
                
                const id = await this.bot.createSession(sessionId, phoneNumber)
                
                res.json({
                    success: true,
                    sessionId: id
                })
            } catch (error) {
                res.status(500).json({
                    error: 'Failed to create session',
                    details: error.message
                })
            }
        })
        
        // Get QR code
        this.app.get('/api/sessions/:sessionId/qr', async (req, res) => {
            const { sessionId } = req.params
            // Implementation for QR code generation
            // This would need to be integrated with your connection handling
        })
    }
    
    start(port: number = 3000) {
        this.app.listen(port, () => {
            console.log(`API server running on port ${port}`)
        })
    }
}
```

## 📊 Monitoring & Analytics

### 1. **Logging Configuration**
```typescript
import P from 'pino'
import { createWriteStream } from 'fs'

const logger = P({
    level: process.env.LOG_LEVEL || 'info',
    formatters: {
        level: (label) => ({ level: label.toUpperCase() }),
        bindings: (bindings) => ({ pid: bindings.pid, hostname: bindings.hostname })
    },
    timestamp: () => `,"timestamp":"${new Date().toISOString()}"`
}, P.multistream([
    { stream: process.stdout },
    { stream: createWriteStream('./logs/app.log', { flags: 'a' }) },
    { stream: createWriteStream('./logs/error.log', { flags: 'a' }), level: 'error' }
]))

// Usage in bot
this.logger.info({ jid, messageType }, 'Message received')
this.logger.error({ error, jid }, 'Failed to process message')
```

### 2. **Metrics Collection**
```typescript
class BotMetrics {
    private metrics = {
        messagesReceived: 0,
        messagesSent: 0,
        mediaDownloaded: 0,
        errors: 0,
        connections: 0,
        disconnections: 0
    }
    
    increment(metric: keyof typeof this.metrics, value = 1) {
        this.metrics[metric] += value
    }
    
    getMetrics() {
        return {
            ...this.metrics,
            uptime: process.uptime(),
            memoryUsage: process.memoryUsage(),
            timestamp: new Date().toISOString()
        }
    }
    
    reset() {
        Object.keys(this.metrics).forEach(key => {
            this.metrics[key as keyof typeof this.metrics] = 0
        })
    }
}
```

## 🔧 Best Practices

### 1. **Error Handling**
- ✅ Implement comprehensive try-catch blocks
- ✅ Handle connection drops gracefully
- ✅ Use exponential backoff for retries
- ✅ Log errors with context information
- ✅ Implement circuit breakers for external services

### 2. **Performance Optimization**
- ✅ Use message queues for rate limiting
- ✅ Implement caching for group metadata
- ✅ Optimize media downloads with streaming
- ✅ Use connection pooling for databases
- ✅ Monitor memory usage and implement cleanup

### 3. **Security**
- ✅ Validate all incoming data
- ✅ Implement API authentication
- ✅ Use HTTPS for all external communications
- ✅ Sanitize file uploads and downloads
- ✅ Implement rate limiting and abuse prevention

### 4. **Scalability**
- ✅ Design for horizontal scaling
- ✅ Use external storage for session data
- ✅ Implement load balancing
- ✅ Use microservices architecture for complex bots
- ✅ Implement health checks and monitoring

## 📚 Additional Resources

### Installation
```bash
# NPM
npm install @whiskeysockets/baileys

# Yarn
yarn add @whiskeysockets/baileys

# Latest edge version
npm install github:whiskeysockets/baileys
```

### Key Dependencies
```json
{
  "dependencies": {
    "@whiskeysockets/baileys": "^6.7.8",
    "@hapi/boom": "^10.0.1",
    "pino": "^8.19.0",
    "qrcode": "^1.5.3",
    "express": "^4.18.2",
    "cors": "^2.8.5",
    "helmet": "^7.1.0"
  }
}
```

### Official Links
- [GitHub Repository](https://github.com/WhiskeySockets/Baileys)
- [Documentation](https://whiskeysockets.github.io/Baileys/)
- [Examples](https://github.com/WhiskeySockets/Baileys/tree/master/Example)

---

*This template provides a comprehensive foundation for building production-ready WhatsApp bots using Baileys. Adapt the patterns and examples to your specific use case and requirements.*
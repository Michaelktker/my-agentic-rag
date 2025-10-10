# WhatsApp ADK Bot

A WhatsApp bot built with Baileys that integrates with Google's ADK (Agent Development Kit) for intelligent conversation handling.

## Features

- **WhatsApp Integration**: Uses the latest Baileys library for WhatsApp Web API
- **Google Cloud Storage**: Custom auth state storage in GCS bucket `gs://authstate`
- **ADK Integration**: Connects to your production ADK endpoint
- **Session Management**: Each WhatsApp user gets a unique ADK session
- **Non-streaming Responses**: Configured for non-streaming responses as requested
- **Automatic Reconnection**: Handles connection drops and reconnects automatically
- **Session Cleanup**: Automatically cleans up old user sessions

## Prerequisites

1. **Google Cloud Setup**:
   - Google Cloud project: `production-adk`
   - ADK service running at: `https://my-agentic-rag-638797485217.us-central1.run.app`
   - GCS bucket: `gs://authstate` (already created)
   - Application Default Credentials configured

2. **Node.js**: Version 18 or higher

## Installation

1. Install dependencies:
```bash
npm install
```

2. Ensure your Google Cloud credentials are set up:
```bash
gcloud auth application-default login
gcloud config set project production-adk
```

## Usage

### Start the Bot (Recommended)

```bash
npm run start:check
```

This script will:
- Check dependencies and install if needed
- Verify Google Cloud authentication
- Test ADK service connectivity
- Test GCS bucket access
- Start the bot with proper checks

### Direct Start

```bash
npm start
```

### Development Mode (with auto-restart)

```bash
npm run dev
```

### Test Connections

```bash
npm test
```

### First Time Setup

1. Run the bot for the first time
2. A QR code will be displayed in the terminal
3. Scan the QR code with your WhatsApp mobile app
4. The bot will connect and start listening for messages

## How It Works

### Authentication State Storage

- Uses a custom `GCSAuthState` class that stores all auth data in Google Cloud Storage
- Auth files are stored in the `gs://authstate/whatsapp-auth/` folder
- Automatically handles credential persistence and retrieval

### Message Flow

1. **Incoming Message**: User sends message to WhatsApp bot
2. **Session Management**: Bot creates/retrieves user session using `remoteJid` as `userId`
3. **ADK Request**: Message sent to ADK endpoint with:
   - `message`: The user's message
   - `session_id`: Unique session ID for the user
   - `user_id`: WhatsApp remoteJid
   - `stream`: false (as requested)
4. **Response**: ADK response sent back to WhatsApp user

### Session Management

- Each WhatsApp user gets a unique session ID
- Sessions are mapped by `remoteJid` (WhatsApp user identifier)
- Sessions auto-expire after 24 hours of inactivity
- Cleanup runs every hour to remove expired sessions

## Configuration

### Environment Variables (Optional)

You can set these environment variables to override defaults:

```bash
export ADK_URL="https://my-agentic-rag-638797485217.us-central1.run.app"
export BUCKET_NAME="authstate"
export PROJECT_ID="production-adk"
export LOG_LEVEL="info"
```

### ADK Endpoint

The bot sends POST requests to `/chat` endpoint with the following payload:

```json
{
  "message": "User's message text",
  "session_id": "wa_1234567890_abcdef123",
  "user_id": "1234567890@s.whatsapp.net",
  "stream": false
}
```

Expected response format:
```json
{
  "response": "AI response text"
}
```

## File Structure

```
.
├── index.js          # Main bot implementation
├── package.json      # Dependencies and scripts
└── WHATSAPP_README.md         # This file
```

## Key Components

### GCSAuthState Class

- Custom authentication state management
- Stores all auth data in Google Cloud Storage
- Handles serialization/deserialization of auth credentials
- Thread-safe file operations

### WhatsAppBot Class

- Main bot logic and WhatsApp connection management
- Message handling and routing
- ADK API integration
- Session management
- Automatic reconnection logic

## Error Handling

- Connection failures are automatically retried
- ADK API errors are gracefully handled and user-friendly messages are sent
- Authentication state persistence ensures sessions survive restarts
- Comprehensive logging for debugging

## Logging

The bot uses Pino logger with pretty printing. Log levels:

- `info`: General operational information
- `debug`: Detailed debugging information
- `error`: Error conditions
- `warn`: Warning conditions

## Security Considerations

- Auth state is securely stored in Google Cloud Storage
- Uses Google Cloud IAM for access control
- Session IDs are randomly generated
- No sensitive data logged in production

## Troubleshooting

### Bot Won't Connect
- Check if QR code is being displayed
- Ensure WhatsApp Web is not open in browser
- Verify Google Cloud credentials

### ADK Integration Issues
- Check ADK service health: `curl https://my-agentic-rag-638797485217.us-central1.run.app/health`
- Verify network connectivity
- Check logs for API response details

### Storage Issues
- Verify GCS bucket permissions
- Check Application Default Credentials
- Ensure bucket `gs://authstate` exists and is accessible

## Production Deployment

For production deployment:

1. Use a process manager like PM2:
```bash
npm install -g pm2
pm2 start index.js --name whatsapp-bot
```

2. Set up monitoring and alerting
3. Configure log rotation
4. Set up health checks
5. Use environment variables for configuration

## License

MIT License - see package.json for details
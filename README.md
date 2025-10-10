# WhatsApp ADK Bot

A production-ready WhatsApp bot powered by Google's Agent Development Kit (ADK) that provides intelligent conversational AI through WhatsApp messaging. The bot integrates with a cloud-hosted ADK service to deliver RAG (Retrieval-Augmented Generation) capabilities, document search, and real-time AI responses.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        WhatsApp Bot System                          │
├─────────────────────────────────────────────────────────────────────┤
│  WhatsApp ↔ Baileys Library ↔ Node.js Bot ↔ Google ADK Service     │
│  ├── Authentication: QR Code + Google Cloud Storage               │
│  ├── Streaming: Server-Sent Events (SSE) for real-time responses  │
│  ├── Session Management: User-specific conversation sessions       │
│  └── AI Backend: ADK RAG Agent with document retrieval            │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Components

- **WhatsApp Integration**: Baileys v6.7.8 library for WhatsApp Web API
- **ADK Service**: Cloud-hosted AI agent at `https://my-agentic-rag-638797485217.us-central1.run.app`
- **Authentication**: Google Cloud Storage for persistent WhatsApp auth state
- **Streaming**: Real-time AI responses using Server-Sent Events
- **Session Management**: User-specific conversation contexts
- **Logging**: Structured logging with Pino for monitoring and debugging

## 🚀 Quick Start

### Prerequisites

- **Node.js**: Version 18+ - [Install](https://nodejs.org/)
- **Google Cloud Account**: For authentication state storage
- **WhatsApp Account**: For bot registration

### Installation

```bash
# Install dependencies
npm install

# Start the bot
npm start
```

### First-Time Setup

1. **QR Code Scan**: When you first run the bot, it will display a QR code
2. **WhatsApp Pairing**: Open WhatsApp on your phone and scan the QR code
3. **Authentication**: The bot will connect and save auth state to Google Cloud Storage
4. **Ready**: Bot will show "WhatsApp Bot Connected Successfully!" message

## 📱 WhatsApp Bot Features

### Core Functionality
- **Conversational AI**: Natural language conversations powered by ADK
- **Document Search**: Retrieval-augmented generation from knowledge base
- **Real-time Responses**: Streaming responses for faster user experience
- **Session Management**: Maintains conversation context per user
- **Error Recovery**: Automatic session recreation on service errors

### User Experience
- **Processing Indicator**: Shows "🤖 *Processing your request...*" while thinking
- **Complete Responses**: Delivers full AI responses in single, clean messages
- **Persistent Sessions**: Remembers conversation context across messages
- **Error Handling**: Graceful error messages for service issues

## 📋 Available Commands

| Command | Description |
|---------|-------------|
| `npm install` | Install Node.js dependencies |
| `npm start` | Start the WhatsApp bot |
| `npm run dev` | Start bot in development mode with auto-restart |

## 🔧 Configuration

### Required Files
- **`config.json`**: ADK service URL and authentication settings
- **`package.json`**: Node.js dependencies and scripts

### Key Settings in `config.json`
```json
{
  "adk": {
    "url": "https://my-agentic-rag-638797485217.us-central1.run.app",
    "timeout": 30000
  },
  "gcs": {
    "bucketName": "production-adk",
    "authStateFile": "whatsapp-bot-auth.json"
  },
  "whatsapp": {
    "browser": ["WhatsApp ADK Bot", "Chrome", "1.0.0"]
  }
}
```

## 🌐 ADK Service Integration

### Production ADK Service
- **Service URL**: `https://my-agentic-rag-638797485217.us-central1.run.app`
- **Endpoints**: 
  - `/run`: Standard API calls
  - `/run_sse`: Streaming responses (Server-Sent Events)
  - `/apps/{app_name}/users/{user_id}/sessions`: Session management

### Authentication & Sessions
- Each WhatsApp user gets a unique ADK session
- Sessions are created automatically on first interaction
- Session IDs are maintained for conversation continuity

## 🔐 Security & Authentication

### Google Cloud Storage
WhatsApp authentication state is stored securely in Google Cloud Storage:
- **Bucket**: `production-adk`
- **File**: `whatsapp-bot-auth.json`
- **Purpose**: Persistent WhatsApp Web session to avoid re-scanning QR codes

### ADK Service Authentication
- Connects to production ADK service without additional authentication
- Uses session-based communication for user context management
- Automatic retry with new sessions on service errors

## 📁 Project Structure

```
my-agentic-rag/
├── index.js                # Main WhatsApp bot application
├── config.json            # Configuration settings
├── package.json           # Node.js dependencies and scripts
├── README.md              # This documentation
├── WHATSAPP_README.md     # Original WhatsApp setup guide
├── Dockerfile             # Docker containerization
├── Makefile              # Build and deployment commands
├── app/                   # Backend ADK service (Python)
│   ├── agent.py          # RAG agent implementation
│   ├── server.py         # FastAPI backend server
│   ├── retrievers.py     # Document retrieval logic
│   └── utils/            # Utility functions
├── deployment/           # Infrastructure code
│   └── terraform/        # Terraform configurations
├── data_ingestion/       # Document processing pipeline
├── tests/               # Test suites
└── notebooks/           # Development notebooks
```

## 🤖 Bot Behavior

### Message Flow
1. **Receive**: User sends WhatsApp message
2. **Process**: Bot shows "🤖 *Processing your request...*"
3. **Stream**: Internal streaming from ADK service (not visible to user)
4. **Respond**: Complete AI response sent as single message

### Session Management
- **Creation**: New ADK session created for each unique WhatsApp user
- **Retention**: Sessions maintained for conversation continuity
- **Recovery**: Automatic session recreation on 500 errors from ADK service

### Error Handling
- **Connection Issues**: "AI service is currently unavailable"
- **Timeouts**: "Request timed out. Please try again with a shorter message"
- **Service Errors**: Automatic retry with new session creation

## 🧠 AI Capabilities

### Document Search & RAG
- **Knowledge Base**: Searches through indexed documents
- **Context-Aware**: Provides intelligent responses based on retrieved content
- **Real-time**: Fast document retrieval and AI generation

### Conversational Features
- **Natural Language**: Understands and responds in natural conversation
- **Context Retention**: Remembers conversation history within sessions
- **Multi-turn Dialogs**: Supports back-and-forth conversations

### Usage Examples
```
User: "Search for information about metformin"
Bot: [Returns detailed medical information about metformin]

User: "Go to retrieve doc and tell me more about BigQuery"
Bot: [Searches documents and provides BigQuery technical details]

User: "What is Google Cloud?"
Bot: [Combines document search with web search for comprehensive answer]
```

## 🚀 Development & Deployment

### Local Development
```bash
# Clone the repository
git clone <repository-url>

# Install dependencies
npm install

# Start the bot
npm start
```

### Docker Deployment
```bash
# Build Docker image
docker build -t whatsapp-adk-bot .

# Run container
docker run -p 3000:3000 whatsapp-adk-bot
```

## 📊 Monitoring & Logging

### Structured Logging
The bot uses Pino for structured JSON logging:
- **Info**: Connection status, message handling, ADK responses
- **Debug**: Streaming chunks, session management
- **Error**: Service failures, authentication issues, timeouts
- **Warn**: Retries, partial responses, parsing errors

### Log Examples
```json
{"level":30,"time":1696982345000,"msg":"Received message from 6592377976@s.whatsapp.net: Hi"}
{"level":30,"time":1696982346000,"msg":"ADK Streaming Response Status: 200"}
{"level":30,"time":1696982347000,"msg":"ADK Streaming Complete: 32 characters"}
```

## 🔧 Troubleshooting

### Common Issues

**QR Code Not Appearing**
- Check internet connection
- Verify Google Cloud Storage permissions
- Clear browser cache and restart

**Bot Not Responding**
- Check ADK service status: `https://my-agentic-rag-638797485217.us-central1.run.app`
- Verify session creation in logs
- Check for 500 errors and automatic retries

**Authentication Failures**
- Ensure Google Cloud credentials are configured
- Verify GCS bucket access permissions
- Check auth state file in cloud storage

### Debug Mode
```bash
# Enable detailed logging
DEBUG=* npm start
```

## 📚 Additional Documentation

- **WhatsApp Setup**: [`WHATSAPP_README.md`](WHATSAPP_README.md)
- **Deployment Guide**: [`deployment/README.md`](deployment/README.md)
- **Development Notes**: [`GEMINI.md`](GEMINI.md)

## 🏷️ Built With

- [Baileys](https://github.com/WhiskeySockets/Baileys) - WhatsApp Web API
- [Google Agent Development Kit (ADK)](https://cloud.google.com/agent-development-kit)
- [Google Cloud Storage](https://cloud.google.com/storage) - Authentication persistence
- [Node.js](https://nodejs.org/) - Runtime environment
- [Axios](https://axios-http.com/) - HTTP client for ADK communication
- [Pino](https://getpino.io/) - High-performance logging

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

---

*Last updated: October 10, 2025*

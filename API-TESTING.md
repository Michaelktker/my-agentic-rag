# API Testing Guide for my-agentic-rag

This document provides the correct API schema and examples for testing your deployed agentic RAG service.

## Service URLs

- **Staging**: https://my-agentic-rag-454188184539.us-central1.run.app
- **Production**: https://my-agentic-rag-638797485217.us-central1.run.app (after production deployment)

## API Endpoints

### Main Chat Endpoint: `/run`

**Method**: POST  
**Content-Type**: application/json

#### Request Schema

```json
{
  "appName": "my-agentic-rag",
  "userId": "string",
  "sessionId": "string", 
  "newMessage": {
    "parts": [
      {
        "text": "your message text here"
      }
    ],
    "role": "user"  // optional
  },
  "streaming": false,  // optional, default false
  "stateDelta": {}     // optional
}
```

#### Example Test Commands

##### Basic Test (No Authentication)
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "appName": "my-agentic-rag",
    "userId": "test-user",
    "sessionId": "test-session-123",
    "newMessage": {
      "parts": [{"text": "Hello, can you help me with Python programming?"}],
      "role": "user"
    }
  }' \
  https://my-agentic-rag-454188184539.us-central1.run.app/run
```

##### With Authentication (for production)
```bash
curl -X POST \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{
    "appName": "my-agentic-rag", 
    "userId": "test-user",
    "sessionId": "test-session-123",
    "newMessage": {
      "parts": [{"text": "Tell me about pandas dataframes"}],
      "role": "user"
    }
  }' \
  https://my-agentic-rag-454188184539.us-central1.run.app/run
```

### Streaming Endpoint: `/run_sse`

Same schema as `/run` but returns Server-Sent Events (SSE) for real-time streaming responses.

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "appName": "my-agentic-rag",
    "userId": "test-user", 
    "sessionId": "test-session-123",
    "newMessage": {
      "parts": [{"text": "Explain machine learning"}]
    }
  }' \
  https://my-agentic-rag-454188184539.us-central1.run.app/run_sse
```

### Other Useful Endpoints

#### API Documentation
- **Swagger UI**: https://my-agentic-rag-454188184539.us-central1.run.app/docs
- **OpenAPI JSON**: https://my-agentic-rag-454188184539.us-central1.run.app/openapi.json

#### Health Check
```bash
curl https://my-agentic-rag-454188184539.us-central1.run.app/
```

#### List Apps
```bash
curl https://my-agentic-rag-454188184539.us-central1.run.app/list-apps
```

#### Session Management
```bash
# List sessions for a user
curl https://my-agentic-rag-454188184539.us-central1.run.app/apps/my-agentic-rag/users/test-user/sessions

# Get specific session
curl https://my-agentic-rag-454188184539.us-central1.run.app/apps/my-agentic-rag/users/test-user/sessions/test-session-123
```

## Quick Test Script

Save this as `test-api.sh`:

```bash
#!/bin/bash

SERVICE_URL="https://my-agentic-rag-454188184539.us-central1.run.app"
USER_ID="test-user-$(date +%s)"
SESSION_ID="session-$(date +%s)"

echo "Testing API with USER_ID: $USER_ID, SESSION_ID: $SESSION_ID"

curl -X POST \
  -H "Content-Type: application/json" \
  -d "{
    \"appName\": \"my-agentic-rag\",
    \"userId\": \"$USER_ID\",
    \"sessionId\": \"$SESSION_ID\",
    \"newMessage\": {
      \"parts\": [{\"text\": \"Hello! Can you tell me about the capabilities of this RAG system?\"}],
      \"role\": \"user\"
    }
  }" \
  "$SERVICE_URL/run"
```

Make it executable: `chmod +x test-api.sh`

## Common Issues and Solutions

1. **"Field required" errors**: Make sure all required fields (`appName`, `userId`, `sessionId`, `newMessage`) are included
2. **"Extra inputs are not permitted"**: Don't include extra fields in the `newMessage.parts` objects - only `text` is supported for basic messages
3. **Internal Server Error**: Usually indicates authentication issues or backend service problems
4. **Authentication errors**: Use `gcloud auth print-identity-token` for authenticated requests

## Load Testing

The service includes load testing that verifies:
- ✅ 70 requests completed successfully (0 failures)
- ✅ Average response time ~1.8 seconds
- ✅ Both `/run_sse` message and end endpoints working

## Message Format Details

The `newMessage.parts` array supports different content types:
- `text`: Plain text messages (most common)
- `fileData`: File attachments  
- `inlineData`: Base64 encoded data
- `functionCall`: Function call requests
- `functionResponse`: Function call responses

For basic chat, stick with the `text` format shown in examples above.
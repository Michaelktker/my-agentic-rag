# Polling Agent Architecture

## Overview

This document explains the **Polling Agent Architecture** implemented for handling long-running FAL.ai media generation operations within Google ADK constraints.

## Problem Statement

### The Challenge
- **ADK Function Timeout**: ADK function tools have a ~120-second timeout limit
- **Video Generation Time**: FAL.ai video generation takes 2-5 minutes
- **HTTP 405 Errors**: Incorrect URL formats caused polling failures
- **User Experience**: Users were stuck waiting with no feedback

### Previous Approach (Removed)
- ❌ **Long-Running Function Tools**: Caused timeouts after 120 seconds
- ❌ **Background Polling Manager**: Too complex, didn't integrate well with ADK
- ❌ **Webhook System**: Required external infrastructure, unreliable

## Solution: Smart Polling Agent

### Architecture Components

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Polling Agent Workflow                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. User Request                                                    │
│     ↓                                                              │
│  2. FAL MCP Agent → generate() → Returns request_id + status_url    │
│     ↓                                                              │
│  3. Root Agent → Calls poll_fal_operation(request_id, status_url)   │
│     ↓                                                              │
│  4. Polling Agent → Smart Polling Strategy:                        │
│     ├─ Images: 20 attempts × 3s = 60s (usually complete)          │
│     └─ Videos: 3 attempts × 3s = 9s (return guidance)             │
│     ↓                                                              │
│  5. Result or Guidance Message                                     │
│     ↓                                                              │
│  6. [For Videos] User asks "check status" after 2-3 minutes       │
│     ↓                                                              │
│  7. Polling Agent → poll_fal_operation() again → Final result     │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Features

#### 1. **Smart Polling Strategy**
```python
# Quick check attempts based on media type
max_quick_checks = 20 if submission_type != "text-to-video" else 3
```

- **Images**: 20 attempts (usually complete quickly)  
- **Videos**: 3 attempts (return guidance message)

#### 2. **Proper URL Construction**
```python
# Fixed HTTP 405 error by using correct URL format
if status_url:
    final_status_url = status_url  # Use FAL-provided URL
elif model_name:
    final_status_url = f"https://queue.fal.run/{model_name}/requests/{fal_request_id}/status"
else:
    final_status_url = f"https://queue.fal.run/requests/{fal_request_id}/status"
```

#### 3. **HTTP Status Handling**
```python
if response.status in [200, 202]:  # Both OK and "Still Processing"
    # Handle appropriately instead of treating 202 as error
```

#### 4. **User-Friendly Messages**
```python
return f"""⏳ **Your video is being generated!** 🎬

Video generation typically takes **2-5 minutes**. 

**What to do:**
1. ✨ Wait 2-3 minutes
2. 💬 Ask me: *"Check the status of my video"* or *"Is my video ready?"*
3. 🔄 I'll check and get your video for you!

**Request ID:** `{fal_request_id}`
"""
```

## Implementation Details

### Files Structure
```
app/
├── polling_agent.py          # ✅ Main polling logic
├── agent.py                  # ✅ Root agent with polling integration
└── server.py                 # ✅ Clean server without old endpoints

# Removed (cleaned up):
├── polling_manager.py        # ❌ Removed - too complex
├── clean_server.py          # ❌ Removed - one-time script
├── refactor_agent.py        # ❌ Removed - one-time script
└── refactor_summary.sh      # ❌ Removed - one-time script
```

### Core Function: `poll_fal_operation()`

```python
async def poll_fal_operation(
    fal_request_id: str,
    submission_type: str = "text-to-video",
    status_url: str = "",
    model_name: str = ""
) -> str:
    """
    Poll FAL.ai for result. Does quick check for fast operations, 
    returns guidance for slow ones.
    """
    # 1. Determine correct status URL (fixes HTTP 405)
    # 2. Quick polling attempts based on media type
    # 3. Return result if completed, guidance if not
    # 4. Handle errors gracefully with helpful messages
```

## Usage Examples

### Image Generation (Fast)
```
User: "Generate an image of a cat with yarn"
↓
FAL MCP Agent: Returns request_id + status_url
↓
Polling Agent: 20 quick checks → ✅ Image ready in 30s!
```

### Video Generation (Slow)
```
User: "Generate a video of a cat playing"
↓
FAL MCP Agent: Returns request_id + status_url  
↓
Polling Agent: 3 quick checks → ⏳ "Video being generated, check back in 2-3 minutes"
↓
[User waits 2-3 minutes]
↓
User: "Check the status of my video"
↓
Polling Agent: Poll again → ✅ Video ready!
```

## Benefits

### ✅ **ADK Compatible**
- Works within ADK's 120-second function timeout
- No hanging connections or background tasks
- Follows ADK request/response patterns

### ✅ **User Experience**
- Clear guidance on wait times
- Helpful status messages
- No confusion about what to do next

### ✅ **Reliable**
- Proper error handling for network issues
- Graceful degradation on timeouts
- Fixed HTTP 405 URL format errors

### ✅ **Maintainable**
- Simple, focused architecture
- Easy to debug and extend
- Clean separation of concerns

## Technical Decisions

### Why Not Background Tasks?
- **ADK Limitation**: No built-in background task support
- **Complexity**: Would require external task queue/scheduler
- **Reliability**: More failure points and harder debugging

### Why Not Webhooks?
- **Infrastructure**: Requires additional services
- **ADK Integration**: Complex to integrate with agent responses
- **Reliability**: Network dependencies and callback failures

### Why Smart Polling?
- **Simplicity**: Works within existing ADK patterns
- **Flexibility**: Different strategies for different media types
- **User Control**: Users decide when to check back

## Future Enhancements

### Possible Improvements
1. **Session State**: Store request IDs for automatic follow-up
2. **Batch Checking**: Check multiple operations at once  
3. **Progress Indicators**: More detailed status information
4. **Push Notifications**: Integration with WhatsApp notifications

### Not Recommended
- ❌ **True Background Tasks**: Not supported by ADK architecture
- ❌ **WebSocket Connections**: Would complicate deployment
- ❌ **Database Persistence**: Adds unnecessary complexity for this use case

## Conclusion

The **Polling Agent Architecture** successfully solves the long-running operation challenge within ADK constraints. It provides a user-friendly experience while maintaining reliability and simplicity.

**Key Success Metrics:**
- ✅ No more timeout errors  
- ✅ Clear user guidance
- ✅ HTTP 405 errors resolved
- ✅ Fast completion for images
- ✅ Manageable workflow for videos

This architecture demonstrates how to work **with** ADK's design patterns rather than against them, resulting in a robust and maintainable solution.
# @Myker Mention Flow

**Architecture**: Mention-based activation pattern using ADK callbacks

---

## Overview

The WhatsApp bot uses a **mention-based activation pattern** where the agent only processes messages that explicitly mention `@Myker`. This prevents the bot from responding to every message in group chats and provides focused, intentional interactions.

## Implementation

**Location**: `app/agent.py`  
**Callbacks**: `before_agent_callback()`, `after_agent_callback()`

### Workflow Diagram

```
User Message
    ↓
before_agent_callback()
    ↓
Check for @Myker mention
    ├─ NOT FOUND ❌ → Set skip_processing = True → Override response
    └─ FOUND ✅ → Clean message → Process normally
         ↓
Agent Execution
    ↓
after_agent_callback()
    ↓
Return response
```

---

## Scenario 1: Message WITHOUT @Myker

**Input**: `"Hello, how are you?"`

### Processing Flow

1. **before_agent_callback()**
   - Extract text from message
   - Search for `@Myker` (case-insensitive)
   - Result: **NOT FOUND ❌**

2. **Set Agent State**
   ```python
   state["skip_processing"] = True
   state["mention_response"] = "I only respond when mentioned with @Myker..."
   ```

3. **Agent Execution**
   - Processing bypassed (skip_processing = True)
   - Tools NOT invoked

4. **after_agent_callback()**
   - Check `skip_processing` flag
   - Override response with mention instruction

**Output**: `"I only respond when mentioned with @Myker. Please mention me to ask questions or request assistance."`

---

## Scenario 2: Message WITH @Myker

**Input**: `"@Myker Hello, how are you?"`

### Processing Flow

1. **before_agent_callback()**
   - Extract text from message
   - Search for `@Myker` (case-insensitive)
   - Result: **FOUND ✅**

2. **Clean Message**
   ```python
   # Before: "@Myker Hello, how are you?"
   # After:  "Hello, how are you?"
   
   cleaned_text = re.sub(r'@myker\s*', '', text, flags=re.IGNORECASE)
   ```

3. **Set Agent State**
   ```python
   state["skip_processing"] = False
   # Update message content with cleaned text
   ```

4. **Agent Execution**
   - Full processing enabled
   - All tools available:
     - GitHub search (via MCP)
     - Vertex AI Search
     - Document processing
     - fal.ai model generation
     - Media handling

5. **after_agent_callback()**
   - `skip_processing = False`
   - No override needed
   - Return agent's full response

**Output**: `[Full intelligent response with tool usage, context retrieval, and multimodal capabilities]`

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Case-insensitive** | `@Myker`, `@myker`, `@MYKER` all work |
| **Position flexible** | Mention can appear anywhere in message |
| **Whitespace smart** | Extra spaces handled automatically |
| **Multimodal safe** | Images, files, audio preserved |
| **Logged** | All checks and cleanings logged |
| **Efficient** | Skips processing for non-mentions |

---

## Code Reference

**File**: `app/agent.py`

### Before Agent Callback
```python
def before_agent_callback(agent, state, message, metadata):
    """Check for @Myker mention before processing"""
    text = extract_text_from_message(message)
    
    if not contains_mention(text, "myker"):
        state["skip_processing"] = True
        state["mention_response"] = "I only respond when mentioned with @Myker..."
        return
    
    # Clean mention from message
    cleaned_text = re.sub(r'@myker\s*', '', text, flags=re.IGNORECASE)
    # Update message content...
```

### After Agent Callback
```python
def after_agent_callback(agent, state, result):
    """Override response if mention not found"""
    if state.get("skip_processing"):
        return state.get("mention_response")
    return result
```

---

## Configuration

**Environment Variables**: None required  
**ADK Agent Settings**: Callbacks attached during agent initialization

```python
root_agent = Agent(
    name="root",
    before_agent_callback=before_agent_callback,
    after_agent_callback=after_agent_callback,
    ...
)
```

---

## Benefits

1. **Group Chat Friendly**: Only responds when explicitly mentioned
2. **Resource Efficient**: Doesn't process every message
3. **Clear UX**: Users know how to activate the bot
4. **Flexible**: Works with any message format or media type
5. **Logged**: Full audit trail of mention checks

---

## Testing

```bash
# Test mention detection
curl -X POST https://your-service.run.app/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "@Myker Hello", "sessionId": "test-123"}'

# Expected: Full response with tool usage

# Test without mention
curl -X POST https://your-service.run.app/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "sessionId": "test-123"}'

# Expected: "I only respond when mentioned with @Myker..."
```

# @Myker Mention Flow & Terminal Commands

**Architecture**: Mention-based activation pattern using ADK callbacks + Terminal command routing

---

## Overview

The WhatsApp bot uses two primary interaction patterns:

1. **@Myker Mention Pattern**: Agent only processes messages that explicitly mention `@Myker` for AI-powered conversations
2. **Terminal Command Pattern**: Direct command execution via `/help`, `/ping`, `/sh`, `/tty`, `/cop` commands for infrastructure operations

---

## Message Routing Architecture

```
WhatsApp Message
    ↓
index.js: processMessage()
    ↓
Check for Terminal Commands (/help, /ping, /sh, /tty, /cop)
    ├─ TERMINAL COMMAND ✅ → terminal-handler.js → Execute → Return
    └─ NOT TERMINAL COMMAND ❌ → Continue to ADK
         ↓
Check for @Myker mention
    ├─ NOT FOUND ❌ → Skip processing → "I only respond when mentioned..."
    └─ FOUND ✅ → Clean message → ADK Agent → Process with tools
```

**Key Design**: Terminal commands are intercepted BEFORE ADK processing (line ~867 in index.js) to prevent conflicts and ensure fast command execution.

---

## Pattern 1: Terminal Command Flow (November 2025)

**New Feature**: Secure cloud terminal for infrastructure management

### Terminal Command Routing

**Location**: `index.js` → `terminal-handler.js`

```javascript
// Early interception before ADK
if (terminalHandler.shouldHandle(from)) {
  const handled = await terminalHandler.handleTerminalMessage(sock, from, messageText);
  if (handled) return; // Stop processing, terminal handled it
}
```

### Terminal Commands

| Command | Purpose | Example | Security |
|---------|---------|---------|----------|
| `/help` | Show available commands | `/help` | JID allowlist |
| `/ping` | Check terminal status | `/ping` | JID allowlist |
| `/sh <cmd>` | One-shot shell command | `/sh terraform version` | Triple-layer validation |
| `/tty start` | Start interactive PTY | `/tty start` | JID + idle timeout |
| `/tty stop` | Stop PTY session | `/tty stop` | JID + session owner |
| `/cop <prompt>` | GitHub Copilot CLI | `/cop what is terraform` | JID + GitHub token |

### Terminal Processing Flow

```
Terminal Message (e.g., "/sh terraform version")
    ↓
terminal-handler.js: handleTerminalMessage()
    ↓
Security Layer 1: isAllowedJid(from)
    ├─ NOT ALLOWED ❌ → Send "Access denied" → Stop
    └─ ALLOWED ✅ → Continue
         ↓
Parse command type (/help, /ping, /sh, /tty, /cop)
    ↓
Security Layer 2: prefixAllowed() [for /sh and /tty]
    ├─ NOT ALLOWED ❌ → Send "Command not in allowlist" → Stop
    └─ ALLOWED ✅ → Continue
         ↓
Security Layer 3: sanitize() [block dangerous symbols]
    ├─ BLOCKED SYMBOLS ❌ → Send "Contains blocked symbol" → Stop
    └─ CLEAN ✅ → Execute
         ↓
Execute command (exec(), spawn(), or PTY)
    ↓
Output handling:
    ├─ Small (<3000 chars) → Send as text message
    └─ Large (>3000 chars) → Save as file → Send as document
```

### Example: `/sh terraform version`

```
1. User sends: "/sh terraform version"
2. index.js detects terminal command
3. terminal-handler.js validates:
   - JID: 120363423143842705@g.us ✅
   - Prefix: "terraform" in allowlist ✅
   - Symbols: no dangerous chars ✅
4. Execute: exec("terraform version")
5. Output: "Terraform v1.13.5"
6. Send as text message
```

### Example: `/cop what is terraform`

```
1. User sends: "/cop what is terraform"
2. terminal-handler.js validates JID ✅
3. Execute: copilot -p "what is terraform" --allow-all-tools
4. Output: AI-powered explanation from GitHub Copilot
5. Send as text message or file (based on length)
```

### Terminal Security Layers

**Layer 1: JID Allowlist** (`config.json`)
```json
{
  "terminal": {
    "allowedJids": ["120363423143842705@g.us"]
  }
}
```

**Layer 2: Command Prefix Validation**
```json
{
  "terminal": {
    "allowedPrefixes": ["gcloud", "terraform", "gh", "copilot", "ls", "pwd", "cat"]
  }
}
```

**Layer 3: Symbol Blocking**
```json
{
  "terminal": {
    "blockedSymbols": [";", "&&", "||", "|", ">", "<", "`", "$", "(", ")"]
  }
}
```

---

## Pattern 2: @Myker Mention Flow

**Implementation**: `app/agent.py`  
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

# ADK Session Persistence Guide

## How Session Persistence Works When Users Log Out and Log In

Based on the ADK documentation and implementation, here's how to properly handle session persistence for users who log out and log back in with the same user ID.

## Key Concepts from ADK Documentation

### 1. State Scoping with Prefixes

ADK uses **state prefixes** to determine the persistence scope and lifetime of data:

```javascript
// Session-scoped state (lost when session ends)
session.state['current_intent'] = 'book_flight'
session.state['session_message_count'] = 5

// User-scoped state (persists across sessions for same user)
session.state['user:preferred_language'] = 'fr'
session.state['user:total_sessions'] = 3
session.state['user:first_interaction'] = '2025-10-12T10:00:00Z'

// App-scoped state (global across all users)
session.state['app:global_discount_code'] = 'SAVE10'
session.state['app:bot_version'] = '1.0.0'

// Temporary state (not persisted, cleared after invocation)
session.state['temp:raw_api_response'] = {...}
session.state['temp:validation_needed'] = true
```

### 2. Session Lifecycle for Persistent Users

#### When User First Logs In:
1. Create new ADK session with initial user state
2. Set `user:first_interaction` timestamp
3. Initialize `user:total_sessions = 1`
4. Store user preferences with `user:` prefix

#### When User Logs Out:
1. Session-scoped state is destroyed
2. User-scoped state (`user:*`) is preserved by ADK
3. App-scoped state (`app:*`) remains available globally

#### When User Logs Back In:
1. Create new ADK session (new session ID)
2. User-scoped state automatically becomes available
3. Increment `user:total_sessions`
4. Update `user:last_login` timestamp
5. Can access all previous `user:*` preferences and data

## Implementation in WhatsApp Bot

### 1. Creating Sessions with Persistent State

```javascript
async createADKSession(userId) {
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
    
    // ... create session
}
```

### 2. Welcoming Returning Users

```javascript
async sendWelcomeMessage(remoteJid, userId, sessionId) {
    // ADK automatically provides access to user: prefixed state
    const stateCheckPayload = {
        appName: ADK_APP_NAME,
        userId: userId,
        sessionId: sessionId,
        newMessage: {
            parts: [{
                text: "Tell me about my previous interactions. How many times have I used this bot? When was my first interaction? Include this information naturally in a brief welcome message. If this is my first time, welcome me as a new user."
            }],
            role: "user"
        },
        streaming: false
    };
    
    // The agent can access user:total_sessions, user:first_interaction, etc.
}
```

### 3. Saving User Preferences

```javascript
async saveUserPreference(userId, sessionId, preferenceKey, preferenceValue) {
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
            [`user:${preferenceKey}`]: preferenceValue,  // Persists across sessions
            'temp:preference_updated': true              // Temporary, not persisted
        }
    };
    
    // ... send to ADK
}
```

## Benefits of This Approach

### ✅ **Automatic Persistence**
- No need to manage external databases
- ADK handles state persistence automatically
- User data survives session restarts

### ✅ **Scalable**
- Works across multiple ADK instances
- No session affinity required
- Stateless application design

### ✅ **Flexible Scoping**
```javascript
// Examples of different persistence scopes:
session.state['user:theme_preference'] = 'dark'           // User persists
session.state['user:notification_settings'] = {...}      // User persists
session.state['current_conversation_topic'] = 'travel'   // Session only
session.state['app:maintenance_mode'] = false            // Global app
session.state['temp:processing_flag'] = true             // Temporary
```

### ✅ **Smart State Management**
- User preferences follow the user across devices
- Session data resets appropriately for new conversations
- Temporary data is automatically cleaned up

## Best Practices

### 1. Use Appropriate Prefixes
```javascript
// ✅ Good - User preferences
session.state['user:language'] = 'en'
session.state['user:timezone'] = 'UTC-5'

// ✅ Good - Session context
session.state['current_task'] = 'booking_flight'
session.state['session_start_time'] = timestamp

// ✅ Good - Temporary processing
session.state['temp:api_response'] = responseData
session.state['temp:validation_result'] = result
```

### 2. Initialize User State Properly
```javascript
// First time user
const newUserState = {
    'user:first_interaction': new Date().toISOString(),
    'user:total_sessions': 1,
    'user:preferences': {},
};

// Returning user (ADK automatically merges existing user: state)
const returningUserState = {
    'user:last_login': new Date().toISOString(),
    'user:total_sessions': existingCount + 1,  // Increment
};
```

### 3. Handle State in Agent Instructions
```javascript
const payload = {
    // ...
    systemContext: {
        instructions: `
            You have access to persistent user state with 'user:' prefix. 
            Use user:total_sessions, user:first_interaction, user:last_login, 
            and other user: prefixed state to personalize responses. 
            Session-scoped state resets on new sessions. 
            Remember user preferences and conversation history across sessions.
        `
    }
};
```

## Testing Session Persistence

### Test Scenario 1: New User
1. User sends first message
2. Bot creates session with `user:first_interaction`
3. User receives welcome message for new users

### Test Scenario 2: Returning User
1. User sends message (same userId as before)
2. Bot creates new session but ADK provides existing `user:*` state
3. Bot says "Welcome back! This is your session #X, you first used this bot on [date]"

### Test Scenario 3: User Preferences
1. User sets preference: "I prefer short responses"
2. Bot saves: `user:response_style = 'short'`
3. User logs out and back in
4. New session automatically has access to `user:response_style`
5. Bot continues giving short responses

## Troubleshooting

### Issue: User state not persisting
**Solution**: Ensure you're using `user:` prefix for persistent data:
```javascript
// ❌ Wrong - will not persist
session.state['language'] = 'en'

// ✅ Correct - will persist across sessions
session.state['user:language'] = 'en'
```

### Issue: Too much data in session
**Solution**: Use appropriate prefixes for data lifecycle:
```javascript
// ❌ Wrong - large data in persistent user state
session.state['user:full_conversation_history'] = [...] // Grows forever

// ✅ Better - use session scope for conversation, summary in user scope
session.state['conversation_messages'] = [...]           // Session only
session.state['user:conversation_summary'] = "..."       // Persists but small
```

### Issue: State not available in new session
**Solution**: Ensure session creation waits for ADK to merge user state:
```javascript
// Create session and wait for user state to be available
const session = await createADKSession(userId);
// ADK automatically merges existing user:* state into new session
```

## Conclusion

ADK's prefix-based state management provides a powerful and elegant solution for session persistence. By using the `user:` prefix pattern, user data automatically persists across logout/login cycles without requiring external storage or complex state management code.

The key is understanding the different state scopes and using the appropriate prefix for each type of data based on its intended lifetime and sharing scope.
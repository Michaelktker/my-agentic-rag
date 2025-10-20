#!/bin/bash

# Monitor FAL MCP logs every 60 seconds
# Usage: ./monitor_fal_mcp.sh

echo "🔍 Starting FAL MCP monitoring (every 60 seconds)..."
echo "Looking for video generation activity, timeouts, and model results"
echo "Press Ctrl+C to stop"
echo ""

# Get current timestamp for starting point
START_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Counter for monitoring cycles
CYCLE=1

while true; do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📊 Monitoring Cycle #$CYCLE - $(date)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Check for recent video generation activity (last 2 minutes)
    RECENT_TIME=$(date -u -d '2 minutes ago' +"%Y-%m-%dT%H:%M:%SZ")
    
    echo "🎥 Searching for video generation activity since $RECENT_TIME..."
    
    # Look for MCP, FAL, video generation, queue, timeout, success patterns
    gcloud logging read "
        resource.type=cloud_run_revision AND 
        resource.labels.service_name=my-agentic-rag AND 
        (
            textPayload:\"MCP\" OR 
            textPayload:\"fal\" OR 
            textPayload:\"video\" OR 
            textPayload:\"generate\" OR 
            textPayload:\"submit\" OR 
            textPayload:\"timeout\" OR 
            textPayload:\"queue\" OR 
            textPayload:\"status\" OR 
            textPayload:\"result\" OR 
            textPayload:\"wan\" OR 
            textPayload:\"kling\" OR 
            textPayload:\"preview\" OR 
            textPayload:\"completed\" OR 
            textPayload:\"failed\" OR 
            textPayload:\"success\" OR 
            textPayload:\"error\" OR
            textPayload:\"30s\" OR
            textPayload:\"30 sec\"
        ) AND 
        timestamp>=\"$RECENT_TIME\"" \
        --limit=20 2>/dev/null | head -50
    
    echo ""
    echo "🔄 Looking for WhatsApp message processing..."
    
    # Check for WhatsApp activity and POST requests
    gcloud logging read "
        resource.type=cloud_run_revision AND 
        resource.labels.service_name=my-agentic-rag AND 
        (
            textPayload:\"POST /run\" OR 
            textPayload:\"whatsapp\" OR 
            textPayload:\"Successfully loaded artifact\" OR
            textPayload:\"media_\"
        ) AND 
        timestamp>=\"$RECENT_TIME\"" \
        --limit=10 2>/dev/null | head -30
        
    echo ""
    echo "⚠️  Checking for errors and warnings..."
    
    # Check for errors
    gcloud logging read "
        resource.type=cloud_run_revision AND 
        resource.labels.service_name=my-agentic-rag AND 
        (
            severity>=ERROR OR
            textPayload:\"ERROR\" OR
            textPayload:\"Exception\" OR
            textPayload:\"Failed\" OR
            textPayload:\"timeout\" OR
            textPayload:\"Timeout\"
        ) AND 
        timestamp>=\"$RECENT_TIME\"" \
        --limit=5 2>/dev/null | head -20

    echo ""
    echo "📈 Service Health Check..."
    
    # Check latest health and run requests
    gcloud logging read "
        resource.type=cloud_run_revision AND 
        resource.labels.service_name=my-agentic-rag AND 
        textPayload:\"HTTP/1.1\" AND
        timestamp>=\"$RECENT_TIME\"" \
        --limit=5 2>/dev/null | grep -E "(200 OK|POST|GET)" | head -3
    
    echo ""
    echo "⏰ Next check in 60 seconds... (Cycle #$CYCLE completed at $(date))"
    echo ""
    
    # Increment cycle counter
    ((CYCLE++))
    
    # Wait 60 seconds
    sleep 60
done
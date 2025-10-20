"""
Webhook Handler for FAL.ai Video Generation Completion
Implements async callback pattern for long-running video generation tasks
"""

import os
import asyncio
import json
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, HttpUrl
import aiohttp
from google.cloud import storage
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "https://my-agentic-rag-aktu2chyfa-uc.a.run.app")
WHATSAPP_BOT_URL = os.getenv("WHATSAPP_BOT_URL", "http://localhost:3000")
BUCKET_NAME = os.getenv("BUCKET_NAME", "whatsapp-bot-auth")

# Initialize GCS
storage_client = storage.Client()
bucket = storage_client.bucket(BUCKET_NAME)


class WebhookRequest(BaseModel):
    """FAL.ai webhook callback payload"""
    status: str
    request_id: Optional[str] = None
    queue_position: Optional[int] = None
    response_url: Optional[HttpUrl] = None
    logs: Optional[list] = None
    metrics: Optional[Dict[str, Any]] = None
    data: Optional[Dict[str, Any]] = None  # Contains the actual result data
    error: Optional[str] = None


class VideoGenerationContext(BaseModel):
    """Context for tracking video generation requests"""
    user_id: str
    session_id: str
    jid: str  # WhatsApp JID for sending completion message
    model_name: str
    prompt: str
    request_id: str
    status_url: str
    response_url: str
    created_at: str
    webhook_url: str


class WebhookHandler:
    """Handles webhook callbacks for long-running tasks"""
    
    def __init__(self):
        self.pending_requests: Dict[str, VideoGenerationContext] = {}
        self.webhook_folder = "webhooks/video_generation"
    
    async def register_video_generation(
        self,
        request_id: str,
        user_id: str,
        session_id: str,
        jid: str,
        model_name: str,
        prompt: str,
        status_url: str,
        response_url: str
    ) -> str:
        """
        Register a new video generation request for webhook tracking
        
        Returns:
            str: Webhook URL for FAL.ai callback
        """
        # Create unique webhook URL for this request
        webhook_url = f"{WEBHOOK_BASE_URL}/webhook/fal/{request_id}"
        
        # Create context
        context = VideoGenerationContext(
            user_id=user_id,
            session_id=session_id,
            jid=jid,
            model_name=model_name,
            prompt=prompt,
            request_id=request_id,
            status_url=status_url,
            response_url=response_url,
            created_at=asyncio.get_event_loop().time(),
            webhook_url=webhook_url
        )
        
        # Store in memory and GCS for persistence
        self.pending_requests[request_id] = context
        await self._store_context_gcs(request_id, context)
        
        logger.info(f"🎬 Registered video generation: {request_id} for user {user_id}")
        logger.info(f"📡 Webhook URL: {webhook_url}")
        
        return webhook_url
    
    async def handle_webhook_callback(self, request_id: str, webhook_data: WebhookRequest):
        """Handle incoming webhook callback from FAL.ai"""
        logger.info(f"📨 Webhook callback received for request: {request_id}")
        logger.info(f"📊 Status: {webhook_data.status}")
        
        # Get context from memory or GCS
        context = await self._get_context(request_id)
        if not context:
            logger.error(f"❌ Context not found for request: {request_id}")
            raise HTTPException(status_code=404, detail="Request context not found")
        
        # Process based on status
        if webhook_data.status == "COMPLETED":
            await self._handle_completion(context, webhook_data)
        elif webhook_data.status == "FAILED":
            await self._handle_failure(context, webhook_data)
        elif webhook_data.status == "IN_PROGRESS":
            await self._handle_progress(context, webhook_data)
        else:
            logger.warning(f"⚠️ Unknown status: {webhook_data.status}")
    
    async def _handle_completion(self, context: VideoGenerationContext, webhook_data: WebhookRequest):
        """Handle successful video generation completion"""
        try:
            logger.info(f"✅ Video generation completed: {context.request_id}")
            
            # Try to get video URL from multiple sources
            video_url = None
            
            # First try from webhook data if it has the URL
            if hasattr(webhook_data, 'data') and webhook_data.data and 'url' in webhook_data.data:
                video_url = webhook_data.data['url']
                logger.info(f"📹 Got video URL from webhook data: {video_url}")
            
            # If not in webhook data, fetch from response URL
            elif webhook_data.response_url or context.response_url:
                response_url = str(webhook_data.response_url) if webhook_data.response_url else context.response_url
                final_result = await self._fetch_final_result(response_url)
                if final_result:
                    # Try different possible fields for the video URL
                    video_url = (final_result.get("url") or 
                               final_result.get("video_url") or
                               final_result.get("data", {}).get("url") if isinstance(final_result.get("data"), dict) else None)
                    logger.info(f"📹 Got video URL from response: {video_url}")
            
            if video_url:
                # Send completion message to WhatsApp user
                completion_message = (
                    f"🎬 Your video is ready!\n\n"
                    f"**Model:** {context.model_name}\n"
                    f"**Prompt:** {context.prompt[:100]}{'...' if len(context.prompt) > 100 else ''}\n\n"
                    f"🔗 **Download your video:**\n{video_url}\n\n"
                    f"✨ Video generated successfully!"
                )
                
                await self._send_whatsapp_message(context.jid, completion_message)
                logger.info(f"📱 Sent completion message to user: {context.user_id}")
                
            else:
                logger.error(f"❌ No video URL found in webhook or response")
                await self._send_error_message(context, "Video was generated but URL not accessible")
                
        except Exception as e:
            logger.error(f"❌ Error handling completion: {e}")
            await self._send_error_message(context, f"Error processing completion: {e}")
        finally:
            # Cleanup
            await self._cleanup_context(context.request_id)
    
    async def _handle_failure(self, context: VideoGenerationContext, webhook_data: WebhookRequest):
        """Handle failed video generation"""
        logger.error(f"❌ Video generation failed: {context.request_id}")
        
        error_msg = "Unknown error"
        if webhook_data.logs:
            # Extract error from logs
            for log in webhook_data.logs:
                if "error" in str(log).lower():
                    error_msg = str(log)
                    break
        
        failure_message = (
            f"❌ Video generation failed\n\n"
            f"**Model:** {context.model_name}\n"
            f"**Prompt:** {context.prompt[:100]}...\n\n"
            f"**Error:** {error_msg}\n\n"
            f"Please try again with different parameters or contact support."
        )
        
        await self._send_whatsapp_message(context.jid, failure_message)
        await self._cleanup_context(context.request_id)
    
    async def _handle_progress(self, context: VideoGenerationContext, webhook_data: WebhookRequest):
        """Handle progress updates"""
        logger.info(f"⏳ Progress update for {context.request_id}: {webhook_data.status}")
        
        # Optionally send progress updates to user
        if webhook_data.queue_position is not None:
            progress_message = (
                f"⏳ Your video is in progress...\n\n"
                f"**Queue position:** {webhook_data.queue_position}\n"
                f"**Model:** {context.model_name}\n\n"
                f"I'll notify you when it's ready! 🎬"
            )
            await self._send_whatsapp_message(context.jid, progress_message)
    
    async def _fetch_final_result(self, response_url: str) -> Optional[Dict[str, Any]]:
        """Fetch final result from FAL.ai response URL"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(response_url) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"❌ Error fetching result: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"❌ Error fetching final result: {e}")
            return None
    
    async def _send_whatsapp_message(self, jid: str, message: str):
        """Send message to WhatsApp user via bot API"""
        try:
            # Send message directly to WhatsApp bot's message queue
            # Store message in GCS for bot to pick up via polling or webhook
            
            logger.info(f"📱 Sending to {jid}: {message}")
            
            # Store outbound message in GCS for WhatsApp bot pickup
            message_data = {
                "jid": jid,
                "message": message,
                "timestamp": json.dumps(asyncio.get_event_loop().time()),  # Convert to string
                "type": "webhook_notification"
            }
            
            # Create unique message ID
            message_id = f"webhook_msg_{uuid.uuid4().hex[:12]}"
            message_path = f"outbound_messages/{message_id}.json"
            
            # Store in GCS for bot pickup
            blob = bucket.blob(message_path)
            blob.upload_from_string(
                json.dumps(message_data, indent=2),
                content_type='application/json'
            )
            
            logger.info(f"📦 Stored outbound message for bot pickup: {message_path}")
            
            # TODO: Could also implement direct bot notification via HTTP POST
            # await self._notify_bot_directly(jid, message)
            
        except Exception as e:
            logger.error(f"❌ Error sending WhatsApp message: {e}")
    
    async def _send_error_message(self, context: VideoGenerationContext, error: str):
        """Send error message to user"""
        error_message = (
            f"❌ Sorry, there was an issue with your video generation:\n\n"
            f"**Error:** {error}\n\n"
            f"Please try again or contact support if the issue persists."
        )
        await self._send_whatsapp_message(context.jid, error_message)
    
    async def _get_context(self, request_id: str) -> Optional[VideoGenerationContext]:
        """Get context from memory or GCS"""
        # Try memory first
        if request_id in self.pending_requests:
            return self.pending_requests[request_id]
        
        # Try GCS
        try:
            context_path = f"{self.webhook_folder}/{request_id}.json"
            blob = bucket.blob(context_path)
            
            if blob.exists():
                data = blob.download_as_text()
                context_data = json.loads(data)
                context = VideoGenerationContext(**context_data)
                
                # Store back in memory
                self.pending_requests[request_id] = context
                return context
        except Exception as e:
            logger.error(f"❌ Error loading context from GCS: {e}")
        
        return None
    
    async def _store_context_gcs(self, request_id: str, context: VideoGenerationContext):
        """Store context in GCS for persistence"""
        try:
            context_path = f"{self.webhook_folder}/{request_id}.json"
            blob = bucket.blob(context_path)
            
            # Convert context to dict and store
            context_data = context.dict()
            blob.upload_from_string(
                json.dumps(context_data, indent=2),
                content_type='application/json'
            )
            
            logger.debug(f"💾 Stored context in GCS: {context_path}")
        except Exception as e:
            logger.error(f"❌ Error storing context in GCS: {e}")
    
    async def _cleanup_context(self, request_id: str):
        """Clean up context from memory and GCS"""
        # Remove from memory
        if request_id in self.pending_requests:
            del self.pending_requests[request_id]
        
        # Remove from GCS
        try:
            context_path = f"{self.webhook_folder}/{request_id}.json"
            blob = bucket.blob(context_path)
            if blob.exists():
                blob.delete()
                logger.debug(f"🗑️ Cleaned up context: {request_id}")
        except Exception as e:
            logger.error(f"❌ Error cleaning up context: {e}")


# Global webhook handler instance
webhook_handler = WebhookHandler()


# FastAPI endpoints for webhook handling
def add_webhook_routes(app: FastAPI):
    """Add webhook routes to FastAPI app"""
    
    @app.post("/webhook/fal/{request_id}")
    async def fal_webhook_callback(
        request_id: str,
        webhook_data: WebhookRequest,
        background_tasks: BackgroundTasks
    ):
        """Handle FAL.ai webhook callbacks"""
        try:
            # Process webhook in background to return quickly
            background_tasks.add_task(
                webhook_handler.handle_webhook_callback,
                request_id,
                webhook_data
            )
            
            return {"status": "received", "request_id": request_id}
            
        except Exception as e:
            logger.error(f"❌ Webhook callback error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/webhook/status/{request_id}")
    async def get_webhook_status(request_id: str):
        """Get status of a webhook request"""
        context = await webhook_handler._get_context(request_id)
        if not context:
            raise HTTPException(status_code=404, detail="Request not found")
        
        return {
            "request_id": request_id,
            "user_id": context.user_id,
            "model_name": context.model_name,
            "created_at": context.created_at,
            "webhook_url": context.webhook_url
        }
    
    @app.get("/webhook/health")
    async def webhook_health():
        """Webhook health check"""
        return {
            "status": "healthy",
            "pending_requests": len(webhook_handler.pending_requests),
            "webhook_base_url": WEBHOOK_BASE_URL
        }


# Export for use in main server
__all__ = ["webhook_handler", "add_webhook_routes", "WebhookHandler", "VideoGenerationContext"]
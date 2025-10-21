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
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "https://my-agentic-rag-454188184539.us-central1.run.app")
WHATSAPP_BOT_URL = os.getenv("WHATSAPP_BOT_URL", "http://localhost:3000")
BUCKET_NAME = os.getenv("BUCKET_NAME", os.getenv("ARTIFACTS_BUCKET_NAME", "adk_artifact"))

# Ensure the webhook base URL is complete
if WEBHOOK_BASE_URL and not WEBHOOK_BASE_URL.startswith('http'):
    WEBHOOK_BASE_URL = f"https://{WEBHOOK_BASE_URL}"

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


class ImageGenerationContext(BaseModel):
    """Context for tracking image generation requests"""
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


class ImageEditingContext(BaseModel):
    """Context for tracking image editing requests"""
    user_id: str
    session_id: str
    jid: str  # WhatsApp JID for sending completion message
    model_name: str
    prompt: str
    image_url: str  # Original image URL
    request_id: str
    status_url: str
    response_url: str
    created_at: str
    webhook_url: str


class WebhookHandler:
    """Handles webhook callbacks for long-running tasks"""
    
    def __init__(self):
        self.pending_video_requests: Dict[str, VideoGenerationContext] = {}
        self.pending_image_requests: Dict[str, ImageGenerationContext] = {}
        self.pending_edit_requests: Dict[str, ImageEditingContext] = {}
        self.webhook_folder_video = "webhooks/video_generation"
        self.webhook_folder_image = "webhooks/image_generation"
        self.webhook_folder_edit = "webhooks/image_editing"
    
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
            created_at=str(asyncio.get_event_loop().time()),
            webhook_url=webhook_url
        )
        
        # Store in memory and GCS for persistence
        self.pending_video_requests[request_id] = context
        await self._store_context_gcs(request_id, context, "video")
        
        logger.info(f"🎬 Registered video generation: {request_id} for user {user_id}")
        logger.info(f"📡 Webhook URL: {webhook_url}")
        
        return webhook_url
    
    async def register_image_generation(
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
        Register a new image generation request for webhook tracking
        
        Returns:
            str: Webhook URL for FAL.ai callback
        """
        # Create unique webhook URL for this request
        webhook_url = f"{WEBHOOK_BASE_URL}/webhook/fal/{request_id}"
        
        # Create context
        context = ImageGenerationContext(
            user_id=user_id,
            session_id=session_id,
            jid=jid,
            model_name=model_name,
            prompt=prompt,
            request_id=request_id,
            status_url=status_url,
            response_url=response_url,
            created_at=str(asyncio.get_event_loop().time()),
            webhook_url=webhook_url
        )
        
        # Store in memory and GCS for persistence
        self.pending_image_requests[request_id] = context
        await self._store_context_gcs(request_id, context, "image")
        
        logger.info(f"🎨 Registered image generation: {request_id} for user {user_id}")
        logger.info(f"📡 Webhook URL: {webhook_url}")
        
        return webhook_url
    
    async def register_image_editing(
        self,
        request_id: str,
        user_id: str,
        session_id: str,
        jid: str,
        model_name: str,
        prompt: str,
        image_url: str,
        status_url: str,
        response_url: str
    ) -> str:
        """
        Register a new image editing request for webhook tracking
        
        Returns:
            str: Webhook URL for FAL.ai callback
        """
        # Create unique webhook URL for this request
        webhook_url = f"{WEBHOOK_BASE_URL}/webhook/fal/{request_id}"
        
        # Create context
        context = ImageEditingContext(
            user_id=user_id,
            session_id=session_id,
            jid=jid,
            model_name=model_name,
            prompt=prompt,
            image_url=image_url,
            request_id=request_id,
            status_url=status_url,
            response_url=response_url,
            created_at=str(asyncio.get_event_loop().time()),
            webhook_url=webhook_url
        )
        
        # Store in memory and GCS for persistence
        self.pending_edit_requests[request_id] = context
        await self._store_context_gcs(request_id, context, "edit")
        
        logger.info(f"✂️ Registered image editing: {request_id} for user {user_id}")
        logger.info(f"📡 Webhook URL: {webhook_url}")
        
        return webhook_url
    
    async def update_webhook_request_id(self, old_request_id: str, new_request_id: str) -> bool:
        """
        Update the webhook registration with the actual FAL.ai request ID
        
        Args:
            old_request_id: The temporary request ID we generated
            new_request_id: The actual FAL.ai request ID
            
        Returns:
            bool: True if update successful, False otherwise
        """
        try:
            # Get existing context
            context = await self._get_context(old_request_id)
            if not context:
                logger.error(f"❌ No context found for old request ID: {old_request_id}")
                return False
            
            # Create new context with updated request ID
            new_context = VideoGenerationContext(
                user_id=context.user_id,
                session_id=context.session_id,
                jid=context.jid,
                model_name=context.model_name,
                prompt=context.prompt,
                request_id=new_request_id,  # Use the new FAL.ai request ID
                status_url=context.status_url,
                response_url=context.response_url,
                created_at=context.created_at,
                webhook_url=f"{WEBHOOK_BASE_URL}/webhook/fal/{new_request_id}"  # Update webhook URL
            )
            
            # Store new context with new request ID
            self.pending_requests[new_request_id] = new_context
            await self._store_context_gcs(new_request_id, new_context)
            
            # Cleanup old context
            await self._cleanup_context(old_request_id)
            
            logger.info(f"✅ Updated webhook registration: {old_request_id} → {new_request_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error updating webhook request ID: {e}")
            return False
    
    async def handle_webhook_callback(self, request_id: str, webhook_data: WebhookRequest):
        """Handle incoming webhook callback from FAL.ai"""
        logger.info(f"📨 Webhook callback received for request: {request_id}")
        logger.info(f"📊 Status: {webhook_data.status}")
        logger.info(f"🔍 DEBUG - Full webhook data: {webhook_data.dict()}")
        
        # Get context from memory or GCS
        context = await self._get_context(request_id)
        if not context:
            logger.error(f"❌ Context not found for request: {request_id}")
            raise HTTPException(status_code=404, detail="Request context not found")
        
        # Process based on status (handle multiple possible success values)
        if webhook_data.status in ["COMPLETED", "DONE", "OK", "SUCCESS"]:
            await self._handle_completion(context, webhook_data)
        elif webhook_data.status in ["FAILED", "ERROR"]:
            await self._handle_failure(context, webhook_data)
        elif webhook_data.status == "IN_PROGRESS":
            await self._handle_progress(context, webhook_data)
        else:
            logger.warning(f"⚠️ Unknown status: {webhook_data.status}")
    
    async def _handle_completion(self, context, webhook_data: WebhookRequest):
        """Handle successful generation/editing completion for any operation type"""
        try:
            # Determine operation type
            if isinstance(context, VideoGenerationContext):
                operation_type = "video"
                emoji = "🎬"
                operation_name = "Video generation"
            elif isinstance(context, ImageGenerationContext):
                operation_type = "image"
                emoji = "🎨"
                operation_name = "Image generation"
            elif isinstance(context, ImageEditingContext):
                operation_type = "image"
                emoji = "✂️"
                operation_name = "Image editing"
            else:
                logger.error(f"❌ Unknown context type: {type(context)}")
                return
                
            logger.info(f"✅ {operation_name} completed: {context.request_id}")
            
            # Try to get result URL from multiple sources
            result_url = None
            
            # Debug: Log webhook data structure
            logger.info(f"🔍 Webhook has data: {webhook_data.data is not None}")
            if webhook_data.data:
                logger.info(f"🔍 Data keys: {list(webhook_data.data.keys()) if isinstance(webhook_data.data, dict) else 'Not a dict'}")
            
            # First try from webhook data - check various possible structures
            if webhook_data.data:
                data = webhook_data.data
                # Try various common URL field names based on operation type
                if operation_type == "video":
                    result_url = (
                        data.get('url') or
                        data.get('video_url') or 
                        data.get('video', {}).get('url') if isinstance(data.get('video'), dict) else None or
                        data.get('video') if isinstance(data.get('video'), str) else None or
                        data.get('output', {}).get('url') if isinstance(data.get('output'), dict) else None or
                        data.get('output', {}).get('video_url') if isinstance(data.get('output'), dict) else None or
                        data.get('result', {}).get('url') if isinstance(data.get('result'), dict) else None or
                        data.get('result', {}).get('video_url') if isinstance(data.get('result'), dict) else None
                    )
                else:  # image generation or editing
                    result_url = (
                        data.get('url') or
                        data.get('image_url') or
                        data.get('image', {}).get('url') if isinstance(data.get('image'), dict) else None or
                        data.get('image') if isinstance(data.get('image'), str) else None or
                        data.get('output', {}).get('url') if isinstance(data.get('output'), dict) else None or
                        data.get('output', {}).get('image_url') if isinstance(data.get('output'), dict) else None or
                        data.get('result', {}).get('url') if isinstance(data.get('result'), dict) else None or
                        data.get('result', {}).get('image_url') if isinstance(data.get('result'), dict) else None or
                        # For image arrays (common in image generation)
                        data.get('images', [{}])[0].get('url') if isinstance(data.get('images'), list) and len(data.get('images', [])) > 0 else None
                    )
                if result_url:
                    logger.info(f"{emoji} Got {operation_type} URL from webhook data: {result_url}")
            
            # If not in webhook data, fetch from stored URLs in context
            if not result_url:
                # Try response_url first (webhook or stored context)
                response_url = None
                if webhook_data.response_url:
                    response_url = str(webhook_data.response_url)
                    logger.info(f"🌐 Using response URL from webhook: {response_url}")
                elif context.response_url:
                    response_url = context.response_url
                    logger.info(f"🌐 Using response URL from stored context: {response_url}")
                
                if response_url:
                    logger.info(f"🔍 Fetching from response URL: {response_url}")
                    final_result = await self._fetch_final_result(response_url)
                    if final_result:
                        logger.info(f"🔍 Final result keys: {list(final_result.keys()) if isinstance(final_result, dict) else 'Not a dict'}")
                        
                        # Extract URL from final result based on operation type
                        if operation_type == "video":
                            result_url = (
                                final_result.get('url') or
                                final_result.get('video_url') or
                                final_result.get('video', {}).get('url') if isinstance(final_result.get('video'), dict) else None or
                                final_result.get('video') if isinstance(final_result.get('video'), str) else None
                            )
                        else:  # image
                            result_url = (
                                final_result.get('url') or
                                final_result.get('image_url') or
                                final_result.get('image', {}).get('url') if isinstance(final_result.get('image'), dict) else None or
                                final_result.get('image') if isinstance(final_result.get('image'), str) else None or
                                final_result.get('images', [{}])[0].get('url') if isinstance(final_result.get('images'), list) and len(final_result.get('images', [])) > 0 else None
                            )
                        
                        if result_url:
                            logger.info(f"{emoji} Got {operation_type} URL from final result: {result_url}")
            
            # Send completion message
            if result_url:
                await self._send_completion_message(context, result_url, operation_type)
            else:
                logger.error(f"❌ Could not extract {operation_type} URL from any source")
                await self._send_error_message(context, f"Generated {operation_type} successfully but could not retrieve download URL")
            
            # Clean up
            await self._cleanup_context(context.request_id)
            
        except Exception as e:
            logger.error(f"❌ Error handling {operation_name} completion: {e}")
            await self._send_error_message(context, f"Error processing completed {operation_type}: {str(e)}")
    
    async def _send_completion_message(self, context, result_url: str, operation_type: str):
        """Handle successful video generation completion"""
        try:
            logger.info(f"✅ Video generation completed: {context.request_id}")
            
            # Try to get video URL from multiple sources
            video_url = None
            
            # Debug: Log webhook data structure
            logger.info(f"🔍 Webhook has data: {webhook_data.data is not None}")
            if webhook_data.data:
                logger.info(f"🔍 Data keys: {list(webhook_data.data.keys()) if isinstance(webhook_data.data, dict) else 'Not a dict'}")
            
            # First try from webhook data - check various possible structures
            if webhook_data.data:
                data = webhook_data.data
                # Try various common video URL field names
                video_url = (
                    data.get('url') or
                    data.get('video_url') or 
                    data.get('video', {}).get('url') if isinstance(data.get('video'), dict) else None or
                    data.get('video') if isinstance(data.get('video'), str) else None or
                    data.get('output', {}).get('url') if isinstance(data.get('output'), dict) else None or
                    data.get('output', {}).get('video_url') if isinstance(data.get('output'), dict) else None or
                    data.get('result', {}).get('url') if isinstance(data.get('result'), dict) else None or
                    data.get('result', {}).get('video_url') if isinstance(data.get('result'), dict) else None
                )
                if video_url:
                    logger.info(f"📹 Got video URL from webhook data: {video_url}")
            
            # If not in webhook data, fetch from stored URLs in context
            if not video_url:
                # Try response_url first (webhook or stored context)
                response_url = None
                if webhook_data.response_url:
                    response_url = str(webhook_data.response_url)
                    logger.info(f"🌐 Using response URL from webhook: {response_url}")
                elif context.response_url:
                    response_url = context.response_url
                    logger.info(f"🌐 Using response URL from stored context: {response_url}")
                
                if response_url:
                    logger.info(f"🔍 Fetching from response URL: {response_url}")
                    final_result = await self._fetch_final_result(response_url)
                    if final_result:
                        logger.info(f"🔍 Final result keys: {list(final_result.keys()) if isinstance(final_result, dict) else 'Not a dict'}")
                        # Try different possible fields for the video URL
                        video_url = (
                            final_result.get("url") or 
                            final_result.get("video_url") or
                            final_result.get("video", {}).get("url") if isinstance(final_result.get("video"), dict) else None or
                            final_result.get("video") if isinstance(final_result.get("video"), str) else None or
                            final_result.get("output", {}).get("url") if isinstance(final_result.get("output"), dict) else None or
                            final_result.get("output", {}).get("video_url") if isinstance(final_result.get("output"), dict) else None or
                            final_result.get("data", {}).get("url") if isinstance(final_result.get("data"), dict) else None or
                            final_result.get("data", {}).get("video_url") if isinstance(final_result.get("data"), dict) else None
                        )
                        if video_url:
                            logger.info(f"📹 Got video URL from response: {video_url}")
                        else:
                            logger.error(f"❌ No video URL found in response data: {final_result}")
                    else:
                        logger.error(f"❌ Failed to fetch final result from: {response_url}")
                
                # If still no video URL and we have status URL, try that as fallback
                if not video_url and context.status_url:
                    logger.info(f"🔄 Trying status URL as fallback: {context.status_url}")
                    try:
                        status_result = await self._fetch_final_result(context.status_url)
                        if status_result:
                            video_url = (
                                status_result.get("url") or 
                                status_result.get("video_url") or
                                status_result.get("video", {}).get("url") if isinstance(status_result.get("video"), dict) else None or
                                status_result.get("video") if isinstance(status_result.get("video"), str) else None or
                                status_result.get("output", {}).get("url") if isinstance(status_result.get("output"), dict) else None or
                                status_result.get("output", {}).get("video_url") if isinstance(status_result.get("output"), dict) else None or
                                status_result.get("data", {}).get("url") if isinstance(status_result.get("data"), dict) else None or
                                status_result.get("data", {}).get("video_url") if isinstance(status_result.get("data"), dict) else None
                            )
                            if video_url:
                                logger.info(f"✅ Retrieved video URL from status: {video_url}")
                    except Exception as status_error:
                        logger.error(f"❌ Status URL fallback failed: {str(status_error)}")
            
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
            logger.info(f"🔍 Fetching from response URL: {response_url}")
            
            # Get FAL.ai API key
            fal_api_key = os.getenv("FAL_KEY")
            if not fal_api_key:
                logger.error("❌ FAL_KEY environment variable not set")
                return None
            
            headers = {
                "Authorization": f"Key {fal_api_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(response_url, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"✅ Successfully fetched result from FAL.ai")
                        logger.debug(f"🔍 FAL.ai result: {result}")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Error fetching result: {response.status}")
                        logger.error(f"❌ Error details: {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"❌ Exception fetching final result from: {response_url}")
            logger.error(f"❌ Exception details: {e}")
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
    
    async def _send_completion_message(self, context, result_url: str, operation_type: str):
        """Send completion message to user for any operation type"""
        # Determine emoji and message based on operation type
        if operation_type == "video":
            emoji = "🎬"
            message_type = "video"
            if isinstance(context, VideoGenerationContext):
                message = (
                    f"{emoji} Your video is ready!\n\n"
                    f"**Model:** {context.model_name}\n"
                    f"**Prompt:** {context.prompt}\n\n"
                    f"🔗 **Download your video:**\n{result_url}\n\n"
                    f"✨ Video generated successfully!"
                )
            else:
                message = f"{emoji} Your video is ready!\n\n🔗 **Download:** {result_url}"
        else:  # image generation or editing
            if isinstance(context, ImageEditingContext):
                emoji = "✂️"
                message_type = "image edit"
                message = (
                    f"{emoji} Your image edit is ready!\n\n"
                    f"**Model:** {context.model_name}\n"
                    f"**Edit prompt:** {context.prompt}\n"
                    f"**Original:** {context.image_url}\n\n"
                    f"🔗 **Download your edited image:**\n{result_url}\n\n"
                    f"✨ Image editing completed successfully!"
                )
            else:  # ImageGenerationContext
                emoji = "🎨"
                message_type = "image"
                message = (
                    f"{emoji} Your image is ready!\n\n"
                    f"**Model:** {context.model_name}\n"
                    f"**Prompt:** {context.prompt}\n\n"
                    f"🔗 **Download your image:**\n{result_url}\n\n"
                    f"✨ Image generated successfully!"
                )
        
        await self._send_whatsapp_message(context.jid, message)
        logger.info(f"✅ Sent {message_type} completion message to {context.jid}")

    async def _send_error_message(self, context, error: str):
        """Send error message to user for any operation type"""
        # Determine operation type for appropriate error message
        if isinstance(context, VideoGenerationContext):
            operation = "video generation"
        elif isinstance(context, ImageGenerationContext):
            operation = "image generation"
        elif isinstance(context, ImageEditingContext):
            operation = "image editing"
        else:
            operation = "generation"
            
        error_message = (
            f"❌ Sorry, there was an issue with your {operation}:\n\n"
            f"**Error:** {error}\n\n"
            f"Please try again or contact support if the issue persists."
        )
        await self._send_whatsapp_message(context.jid, error_message)

    async def _send_error_message_legacy(self, context: VideoGenerationContext, error: str):
        """Send error message to user"""
        error_message = (
            f"❌ Sorry, there was an issue with your video generation:\n\n"
            f"**Error:** {error}\n\n"
            f"Please try again or contact support if the issue persists."
        )
        await self._send_whatsapp_message(context.jid, error_message)
    
    async def _get_context(self, request_id: str):
        """Get context from memory or GCS - supports all operation types"""
        # Try memory first for all operation types
        if request_id in self.pending_video_requests:
            return self.pending_video_requests[request_id]
        if request_id in self.pending_image_requests:
            return self.pending_image_requests[request_id]
        if request_id in self.pending_edit_requests:
            return self.pending_edit_requests[request_id]
        
        # Try GCS for all operation types
        for folder, context_class, storage in [
            (self.webhook_folder_video, VideoGenerationContext, self.pending_video_requests),
            (self.webhook_folder_image, ImageGenerationContext, self.pending_image_requests),
            (self.webhook_folder_edit, ImageEditingContext, self.pending_edit_requests)
        ]:
            try:
                context_path = f"{folder}/{request_id}.json"
                blob = bucket.blob(context_path)
                
                if blob.exists():
                    data = blob.download_as_text()
                    context_data = json.loads(data)
                    context = context_class(**context_data)
                    
                    # Store back in memory
                    storage[request_id] = context
                    return context
            except Exception as e:
                logger.error(f"❌ Error loading context from GCS {folder}: {e}")
        
        return None
    
    async def _store_context_gcs(self, request_id: str, context, operation_type: str):
        """Store context in GCS for persistence"""
        try:
            # Determine folder based on operation type
            if operation_type == "video":
                folder = self.webhook_folder_video
            elif operation_type == "image":
                folder = self.webhook_folder_image
            elif operation_type == "edit":
                folder = self.webhook_folder_edit
            else:
                raise ValueError(f"Unknown operation type: {operation_type}")
                
            context_path = f"{folder}/{request_id}.json"
            blob = bucket.blob(context_path)
            
            # Convert context to dict and store
            context_data = context.dict()
            blob.upload_from_string(
                json.dumps(context_data, indent=2),
                content_type='application/json'
            )
            
            logger.debug(f"💾 Stored {operation_type} context in GCS: {context_path}")
        except Exception as e:
            logger.error(f"❌ Error storing {operation_type} context in GCS: {e}")
    
    async def _cleanup_context(self, request_id: str):
        """Clean up context from memory and GCS"""
        # Remove from memory (check all storage types)
        if request_id in self.pending_video_requests:
            del self.pending_video_requests[request_id]
        if request_id in self.pending_image_requests:
            del self.pending_image_requests[request_id]
        if request_id in self.pending_edit_requests:
            del self.pending_edit_requests[request_id]
        
        # Remove from GCS (check all folders)
        for folder in [self.webhook_folder_video, self.webhook_folder_image, self.webhook_folder_edit]:
            try:
                context_path = f"{folder}/{request_id}.json"
                blob = bucket.blob(context_path)
                if blob.exists():
                    blob.delete()
                    logger.debug(f"🗑️ Cleaned up context: {context_path}")
            except Exception as e:
                logger.error(f"❌ Error cleaning up context {folder}: {e}")


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
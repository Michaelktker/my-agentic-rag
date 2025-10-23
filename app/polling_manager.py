"""
Background polling manager for long-running operations.
Handles status checking and result delivery for FAL.ai generations.
"""
import asyncio
import logging
import aiohttp
import os
from typing import Dict, Optional, Any
from dataclasses import dataclass
from google.genai.types import FunctionResponse, Content, Part

logger = logging.getLogger(__name__)

@dataclass
class PendingOperation:
    """Represents a pending long-running operation"""
    fal_request_id: str
    function_call_id: str
    model_name: str
    prompt: str
    operation_type: str  # 'image', 'video', 'edit'
    session_id: str
    user_id: str
    additional_params: Dict[str, Any]
    start_time: float
    max_poll_time: int = 300  # 5 minutes max

class PollingManager:
    """Manages background polling for long-running operations"""
    
    def __init__(self, runner=None):
        self.pending_operations: Dict[str, PendingOperation] = {}
        self.runner = runner
        self.fal_api_key = os.getenv("FAL_KEY")
        self.polling_interval = 3  # Check every 3 seconds
        self.max_retries = 5
        self._polling_task = None
        
    def add_operation(self, operation: PendingOperation):
        """Add a new operation to track"""
        logger.info(f"📝 Adding operation to polling: {operation.fal_request_id}")
        self.pending_operations[operation.fal_request_id] = operation
        
        # Start polling if not already running
        if self._polling_task is None or self._polling_task.done():
            self._polling_task = asyncio.create_task(self._polling_loop())
    
    async def _polling_loop(self):
        """Main polling loop that runs in the background"""
        logger.info("🔄 Starting polling loop")
        
        while self.pending_operations:
            try:
                # Create a copy to iterate over since we'll modify the dict
                operations_to_check = list(self.pending_operations.items())
                
                for fal_request_id, operation in operations_to_check:
                    try:
                        await self._check_operation_status(fal_request_id, operation)
                    except Exception as e:
                        logger.error(f"❌ Error checking operation {fal_request_id}: {e}")
                        # Remove failed operations after max retries
                        if hasattr(operation, 'retry_count'):
                            operation.retry_count += 1
                        else:
                            operation.retry_count = 1
                            
                        if operation.retry_count >= self.max_retries:
                            logger.error(f"🔥 Max retries reached for {fal_request_id}, removing")
                            await self._send_error_response(operation, str(e))
                            del self.pending_operations[fal_request_id]
                
                # Wait before next polling cycle
                if self.pending_operations:
                    await asyncio.sleep(self.polling_interval)
                    
            except Exception as e:
                logger.error(f"❌ Error in polling loop: {e}")
                await asyncio.sleep(self.polling_interval)
        
        logger.info("🛑 Polling loop stopped - no pending operations")
    
    async def _check_operation_status(self, fal_request_id: str, operation: PendingOperation):
        """Check the status of a specific operation"""
        logger.info(f"🔍 Checking status for: {fal_request_id}")
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Key {self.fal_api_key}"}
                
                # Try to get status_url from fal_response, fallback to constructed URL
                fal_response = operation.additional_params.get('fal_response', {})
                if 'status_url' in fal_response:
                    status_url = fal_response['status_url']
                    logger.info(f"🔗 Using FAL status_url: {status_url}")
                else:
                    # Fallback to constructed URL format
                    status_url = f"https://queue.fal.run/{operation.model_name}/requests/{fal_request_id}/status"
                    logger.info(f"🔗 Using constructed status URL: {status_url}")
                
                async with session.get(status_url, headers=headers) as response:
                    logger.info(f"📡 FAL API status check response: {response.status}")
                    
                    if response.status == 200:
                        status_result = await response.json()
                        logger.info(f"📋 Status result: {status_result}")
                        
                        # Check if the request is completed
                        if status_result.get('status') == 'COMPLETED':
                            logger.info(f"✅ Request completed, fetching results...")
                            
                            # Now get the actual results using response_url
                            response_url = fal_response.get('response_url')
                            if not response_url:
                                response_url = f"https://queue.fal.run/{operation.model_name}/requests/{fal_request_id}"
                            
                            async with session.get(response_url, headers=headers) as result_response:
                                logger.info(f"📡 FAL API result response: {result_response.status}")
                                
                                if result_response.status == 200:
                                    result = await result_response.json()
                                    logger.info(f"🎯 Final result keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")
                                    
                                    # Process the completed result
                                    is_complete = True
                                    result_data = None
                                    
                                    if operation.operation_type == 'image':
                                        if 'images' in result and result['images']:
                                            result_data = {
                                                "status": "COMPLETED",
                                                "result": {
                                                    "image_url": result['images'][0]['url'],
                                                    "width": result['images'][0].get('width'),
                                                    "height": result['images'][0].get('height'),
                                                    "model_name": operation.model_name,
                                                    "prompt": operation.prompt
                                                },
                                                "message": f"Successfully generated image with {operation.model_name}"
                                            }
                                    
                                    elif operation.operation_type == 'video':
                                        if 'video' in result and result['video']:
                                            result_data = {
                                                "status": "COMPLETED", 
                                                "result": {
                                                    "video_url": result['video']['url'],
                                                    "duration": result.get('video', {}).get('duration'),
                                                    "width": result.get('video', {}).get('width'),
                                                    "height": result.get('video', {}).get('height'),
                                                    "model_name": operation.model_name,
                                                    "prompt": operation.prompt
                                                },
                                                "message": f"Successfully generated video with {operation.model_name}"
                                            }
                                    
                                    elif operation.operation_type == 'edit':
                                        if 'image' in result and result['image']:
                                            result_data = {
                                                "status": "COMPLETED",
                                                "result": {
                                                    "image_url": result['image']['url'],
                                                    "width": result['image'].get('width'),
                                                    "height": result['image'].get('height'),
                                                    "model_name": operation.model_name,
                                                    "prompt": operation.prompt
                                                },
                                                "message": f"Successfully edited image with {operation.model_name}"
                                            }
                                    
                                    if result_data:
                                        logger.info(f"🎉 OPERATION COMPLETED: {fal_request_id}")
                                        logger.info(f"📋 Function: {operation.operation_type} generation")
                                        await self._send_completion_response(operation, result_data)
                                        del self.pending_operations[fal_request_id]
                                    else:
                                        logger.warning(f"⚠️ Completed but no valid result data found")
                                        
                                else:
                                    error_text = await result_response.text()
                                    logger.error(f"❌ FAL.ai result fetch error {result_response.status}: {error_text}")
                        
                        elif status_result.get('status') == 'IN_PROGRESS' or status_result.get('status') == 'QUEUED':
                            logger.info(f"⏳ Request still in progress...")
                            # Continue polling
                            
                        elif status_result.get('status') == 'FAILED':
                            error_msg = status_result.get('detail', 'Unknown error')
                            logger.error(f"❌ Request failed: {error_msg}")
                            await self._send_error_response(operation, f"FAL.ai request failed: {error_msg}")
                            del self.pending_operations[fal_request_id]
                            
                        else:
                            logger.warning(f"⚠️ Unknown status: {status_result.get('status')}")
                        
                    elif response.status == 400:
                        error_text = await response.text()
                        logger.info(f"📋 Status check returned 400 (still processing): {error_text}")
                        # Request is still in progress, continue polling
                        
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ FAL.ai status check error {response.status}: {error_text}")
                        
        except Exception as e:
            logger.error(f"❌ Error checking operation status: {e}")
            # Continue polling on error
            pass
    
    async def _send_completion_response(self, operation: PendingOperation, result_data: Dict[str, Any]):
        """Send completion response back to ADK runner"""
        try:
            if not self.runner:
                logger.error("❌ No runner available to send response")
                return
            
            logger.info(f"📤 Sending completion response for {operation.function_call_id}")
            
            # Create function response
            function_response = FunctionResponse(
                name=f"generate_{operation.operation_type}_long_running",
                id=operation.function_call_id,
                response=result_data
            )
            
            # Create content with function response
            content = Content(
                role="user",
                parts=[Part(function_response=function_response)]
            )
            
            # Send to runner
            await self._send_to_runner(operation, content)
            
        except Exception as e:
            logger.error(f"❌ Error sending completion response: {e}")
    
    async def _send_error_response(self, operation: PendingOperation, error_message: str):
        """Send error response back to ADK runner"""
        try:
            if not self.runner:
                logger.error("❌ No runner available to send error response")
                return
                
            logger.info(f"📤 Sending error response for {operation.function_call_id}")
            
            error_data = {
                "status": "FAILED",
                "error": error_message,
                "message": f"Failed to generate {operation.operation_type}"
            }
            
            # Create function response
            function_response = FunctionResponse(
                name=f"generate_{operation.operation_type}_long_running", 
                id=operation.function_call_id,
                response=error_data
            )
            
            # Create content with function response
            content = Content(
                role="user",
                parts=[Part(function_response=function_response)]
            )
            
            # Send to runner
            await self._send_to_runner(operation, content)
            
        except Exception as e:
            logger.error(f"❌ Error sending error response: {e}")
    
    async def _send_to_runner(self, operation: PendingOperation, content: Content):
        """Send content to the ADK runner"""
        try:
            if not self.runner:
                logger.warning("⚠️ No runner available - logging completion instead")
                logger.info(f"🎉 OPERATION COMPLETED: {operation.fal_request_id}")
                logger.info(f"📋 Function: {operation.operation_type} generation")
                logger.info(f"💬 Prompt: {operation.prompt}")
                if hasattr(content, 'parts') and content.parts:
                    for part in content.parts:
                        if hasattr(part, 'function_response') and part.function_response:
                            response_data = part.function_response.response
                            if 'result' in response_data:
                                result = response_data['result']
                                if 'image_url' in result:
                                    logger.info(f"🖼️ Image URL: {result['image_url']}")
                                elif 'video_url' in result:
                                    logger.info(f"🎬 Video URL: {result['video_url']}")
                return
            
            # Use the underlying runner if it's a CustomADKRunner
            actual_runner = self.runner
            if hasattr(self.runner, 'runner'):
                actual_runner = self.runner.runner
            
            # Use the runner to send the response back
            events = actual_runner.run_async(
                user_id=operation.user_id,
                session_id=operation.session_id,
                new_message=content
            )
            
            # Process events (this triggers the agent to continue)
            async for event in events:
                logger.info(f"📨 Processed event from runner: {event.author}")
                
        except Exception as e:
            logger.error(f"❌ Error sending to runner: {e}")
            # Fallback: log the completion details
            logger.info(f"🎉 OPERATION COMPLETED (fallback): {operation.fal_request_id}")
            logger.info(f"📋 Function: {operation.operation_type} generation")

# Global polling manager instance
polling_manager = None

def get_polling_manager() -> PollingManager:
    """Get the global polling manager instance"""
    global polling_manager
    if polling_manager is None:
        polling_manager = PollingManager()
    return polling_manager

def set_polling_manager_runner(runner):
    """Set the runner for the polling manager"""
    global polling_manager
    if polling_manager is None:
        polling_manager = PollingManager(runner)
    else:
        polling_manager.runner = runner
    logger.info("🔗 Polling manager runner configured")
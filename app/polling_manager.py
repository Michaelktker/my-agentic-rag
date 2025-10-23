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
        self.app = None  # Will be set by lifespan to access ADK runner dynamically
        self.fal_api_key = os.getenv("FAL_KEY")
        self.polling_interval = 3  # Check every 3 seconds
        self.max_retries = 5
        self._polling_task = None
        
    def get_adk_runner(self):
        """Get the ADK runner - try from app state first, then fallback to self.runner"""
        # Try to get the ADK SDK's runner from the app state
        if self.app and hasattr(self.app.state, 'agentic_app'):
            agentic_app = self.app.state.agentic_app
            if hasattr(agentic_app, 'runner'):
                return agentic_app.runner
        
        # Fallback to the runner passed during initialization
        return self.runner
        
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
                        
                    elif response.status == 202:
                        # 202 means the request is still being processed - this is normal!
                        status_result = await response.json()
                        logger.info(f"⏳ Request still in progress (HTTP 202): {status_result.get('status', 'IN_PROGRESS')}")
                        # Continue polling - this is not an error!
                        
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
            # Get the ADK runner dynamically
            actual_runner = self.get_adk_runner()
            
            if not actual_runner:
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
            
            # If we got a CustomADKRunner wrapper, unwrap it
            if hasattr(actual_runner, 'runner'):
                actual_runner = actual_runner.runner
            
            logger.info(f"📤 Attempting to send result to runner for session: {operation.session_id}")
            logger.info(f"🔍 Using runner type: {type(actual_runner).__name__}")
            
            # Use the runner to send the response back using proper ADK pattern
            try:
                # ADK pattern: Create a message with the function response
                # The content should contain the function_call_id and response
                logger.info(f"🔧 Resuming ADK session with function_call_id: {operation.function_call_id}")
                
                events = actual_runner.run_async(
                    user_id=operation.user_id,
                    session_id=operation.session_id,
                    new_message=content  # This should contain the function response with function_call_id
                )
                
                # Process events (this triggers the agent to continue)
                event_count = 0
                async for event in events:
                    event_count += 1
                    logger.info(f"📨 Processed event {event_count} from runner: {event.author}")
                    
                logger.info(f"✅ Successfully resumed session with {event_count} events processed")
                    
            except Exception as session_error:
                logger.error(f"❌ Session error - trying fallback approach: {session_error}")
                
                # DEBUG: Log what we're trying to send
                logger.info(f"🔍 DEBUG: Content type: {type(content)}")
                logger.info(f"🔍 DEBUG: Content has parts: {hasattr(content, 'parts')}")
                if hasattr(content, 'parts'):
                    logger.info(f"🔍 DEBUG: Parts count: {len(content.parts) if content.parts else 0}")
                
                # Fallback: Log the completion details with image URL for user to see
                logger.info(f"🎉 OPERATION COMPLETED (fallback due to session error): {operation.fal_request_id}")
                logger.info(f"📋 Function: {operation.operation_type} generation")
                logger.info(f"💬 Prompt: {operation.prompt}")
                
                # Extract and log the result URL prominently
                if hasattr(content, 'parts') and content.parts:
                    for part in content.parts:
                        logger.info(f"🔍 DEBUG: Processing part: {type(part)}")
                        if hasattr(part, 'function_response') and part.function_response:
                            logger.info(f"🔍 DEBUG: Found function response!")
                            response_data = part.function_response.response
                            logger.info(f"🔍 DEBUG: Response data keys: {list(response_data.keys()) if isinstance(response_data, dict) else type(response_data)}")
                            if 'result' in response_data:
                                result = response_data['result']
                                logger.info(f"🔍 DEBUG: Result keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")
                                if 'image_url' in result:
                                    logger.info(f"🖼️ *** IMAGE GENERATED SUCCESSFULLY *** URL: {result['image_url']}")
                                    logger.info(f"📏 Dimensions: {result.get('width', 'unknown')}x{result.get('height', 'unknown')}")
                                elif 'video_url' in result:
                                    logger.info(f"🎬 *** VIDEO GENERATED SUCCESSFULLY *** URL: {result['video_url']}")
                                    logger.info(f"📏 Dimensions: {result.get('width', 'unknown')}x{result.get('height', 'unknown')}")
                                    logger.info(f"⏱️ Duration: {result.get('duration', 'unknown')} seconds")
                            else:
                                logger.warning(f"⚠️ No 'result' key in response data")
                        else:
                            logger.info(f"🔍 DEBUG: Part has no function_response: {hasattr(part, 'function_response')}")
                else:
                    logger.warning(f"⚠️ Content has no parts or parts is empty")
                
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
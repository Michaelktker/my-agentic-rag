"""
Long Running Operation Manager for ADK
Handles polling and completion of long-running operations started by LongRunningFunctionTool
"""

import asyncio
import json
import logging
import os
from typing import Dict, Optional
from google.cloud import storage
from google.genai import types

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LongRunningOperationManager:
    """Manages long-running operations for ADK agents"""
    
    def __init__(self):
        self.storage_client = storage.Client()
        self.bucket_name = os.getenv("ARTIFACTS_BUCKET_NAME", "adk_artifact")
        self.bucket = self.storage_client.bucket(self.bucket_name)
    
    async def poll_operation(self, operation_id: str) -> Dict:
        """
        Poll a long-running operation for completion.
        
        Args:
            operation_id: The operation ID from generate_video_long_running
            
        Returns:
            Dict with operation status and results
        """
        try:
            # Import the status function from agent
            from app.agent import get_video_operation_status
            
            status = await get_video_operation_status(operation_id)
            return status
            
        except Exception as e:
            logger.error(f"❌ Error polling operation {operation_id}: {e}")
            return {
                "operation_id": operation_id,
                "status": "ERROR",
                "error": str(e)
            }
    
    async def send_completion_result(
        self,
        operation_id: str,
        agent_runner,
        session_id: str,
        user_id: str,
        function_call_id: str,
        function_name: str
    ):
        """
        Send completion result back to the agent to continue execution.
        
        Args:
            operation_id: The operation ID
            agent_runner: The ADK agent runner instance
            session_id: Session ID for the agent
            user_id: User ID for the agent
            function_call_id: Original function call ID
            function_name: Original function name
        """
        try:
            # Get final operation status
            status = await self.poll_operation(operation_id)
            
            if status["status"] == "COMPLETED":
                # Create success response
                completion_data = {
                    "operation_id": operation_id,
                    "status": "COMPLETED",
                    "video_url": status.get("video_url"),
                    "model_name": status.get("model_name"),
                    "prompt": status.get("prompt"),
                    "message": f"🎬 Your video is ready!\n\n**Model:** {status.get('model_name')}\n**Prompt:** {status.get('prompt', '')[:100]}{'...' if len(status.get('prompt', '')) > 100 else ''}\n\n🔗 **Download:** {status.get('video_url')}\n\n✨ Video generated successfully!"
                }
                
            elif status["status"] == "FAILED":
                # Create error response
                completion_data = {
                    "operation_id": operation_id,
                    "status": "FAILED",
                    "error": status.get("error", "Unknown error"),
                    "message": f"❌ Video generation failed: {status.get('error', 'Unknown error')}"
                }
                
            else:
                # Still in progress or unknown status
                return False
            
            # Create function response to send back to agent
            function_response_part = types.Part(
                function_response=types.FunctionResponse(
                    id=function_call_id,
                    name=function_name,
                    response=completion_data,
                )
            )
            
            # Send back to agent to continue
            await agent_runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=types.Content(
                    parts=[function_response_part],
                    role="user"
                ),
            )
            
            logger.info(f"✅ Sent completion result for operation {operation_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error sending completion result: {e}")
            return False
    
    async def cleanup_operation(self, operation_id: str):
        """Clean up operation data after completion"""
        try:
            operation_path = f"long_running_operations/{operation_id}.json"
            blob = self.bucket.blob(operation_path)
            
            if blob.exists():
                blob.delete()
                logger.info(f"🗑️ Cleaned up operation: {operation_id}")
                
        except Exception as e:
            logger.error(f"❌ Error cleaning up operation {operation_id}: {e}")


# Global instance
operation_manager = LongRunningOperationManager()


async def poll_and_continue_operation(
    operation_id: str,
    agent_runner,
    session_id: str,
    user_id: str,
    function_call_id: str,
    function_name: str = "generate_video_long_running",
    max_polls: int = 120,  # 10 minutes with 5-second intervals
    poll_interval: int = 5
) -> bool:
    """
    Poll an operation until completion and send result back to agent.
    
    This function should be called by the WhatsApp bot when it detects
    a long-running operation has been started.
    
    Args:
        operation_id: Operation ID from the tool
        agent_runner: ADK agent runner
        session_id: Agent session ID
        user_id: User ID
        function_call_id: Original function call ID
        function_name: Original function name
        max_polls: Maximum number of polls before timeout
        poll_interval: Seconds between polls
        
    Returns:
        bool: True if completed successfully, False otherwise
    """
    
    for attempt in range(max_polls):
        try:
            logger.info(f"🔄 Polling operation {operation_id} (attempt {attempt + 1}/{max_polls})")
            
            # Check operation status
            status = await operation_manager.poll_operation(operation_id)
            
            if status["status"] in ["COMPLETED", "FAILED"]:
                # Send result back to agent
                success = await operation_manager.send_completion_result(
                    operation_id=operation_id,
                    agent_runner=agent_runner,
                    session_id=session_id,
                    user_id=user_id,
                    function_call_id=function_call_id,
                    function_name=function_name
                )
                
                if success:
                    # Clean up
                    await operation_manager.cleanup_operation(operation_id)
                    return True
                else:
                    logger.error(f"❌ Failed to send completion result for {operation_id}")
                    return False
            
            elif status["status"] == "IN_PROGRESS":
                logger.info(f"⏳ Operation {operation_id} still in progress...")
                await asyncio.sleep(poll_interval)
                continue
                
            else:
                logger.error(f"❌ Unknown status for operation {operation_id}: {status}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error polling operation {operation_id}: {e}")
            await asyncio.sleep(poll_interval)
            continue
    
    # Timeout
    logger.error(f"⏰ Timeout polling operation {operation_id}")
    return False
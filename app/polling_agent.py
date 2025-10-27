"""
Polling agent for FAL.ai long-running operations.

This agent handles:
- Polling FAL.ai status URLs
- Retrieving results when operations complete
- Providing status updates to the root agent
"""

import asyncio
import logging
from typing import Dict, Any
from google.adk.agents import Agent
from google.adk.tools import FunctionTool

logger = logging.getLogger(__name__)

# Poll FAL operations with exponential backoff
async def poll_fal_status(
    status_url: str,
    response_url: str,
    max_attempts: int = 60,
    initial_delay: float = 2.0
) -> Dict[str, Any]:
    """
    Poll a FAL.ai operation until it completes.
    
    Args:
        status_url: The status URL to poll
        response_url: The response URL to fetch results from
        max_attempts: Maximum number of polling attempts (default: 60 = ~5 minutes)
        initial_delay: Initial delay between polls in seconds
        
    Returns:
        Dictionary with status and result/error information
    """
    import aiohttp
    import os
    
    fal_api_key = os.getenv("FAL_KEY")
    if not fal_api_key:
        return {
            "status": "ERROR",
            "error": "FAL_KEY environment variable not set"
        }
    
    headers = {"Authorization": f"Key {fal_api_key}"}
    delay = initial_delay
    
    logger.info(f"🔄 Starting to poll FAL status: {status_url}")
    
    async with aiohttp.ClientSession() as session:
        for attempt in range(max_attempts):
            try:
                # Check status
                async with session.get(status_url, headers=headers) as response:
                    if response.status == 200:
                        status_data = await response.json()
                        current_status = status_data.get('status', 'UNKNOWN')
                        
                        logger.info(f"📊 Polling attempt {attempt + 1}/{max_attempts}: Status = {current_status}")
                        
                        if current_status == 'COMPLETED':
                            # Fetch the final result
                            logger.info(f"✅ Operation completed! Fetching result from: {response_url}")
                            async with session.get(response_url, headers=headers) as result_response:
                                if result_response.status == 200:
                                    result_data = await result_response.json()
                                    logger.info(f"🎉 Successfully retrieved result")
                                    return {
                                        "status": "COMPLETED",
                                        "result": result_data
                                    }
                                else:
                                    error_text = await result_response.text()
                                    logger.error(f"❌ Failed to fetch result: {error_text}")
                                    return {
                                        "status": "ERROR",
                                        "error": f"Failed to fetch result: {error_text}"
                                    }
                        
                        elif current_status == 'FAILED':
                            error_msg = status_data.get('error', 'Unknown error')
                            logger.error(f"❌ Operation failed: {error_msg}")
                            return {
                                "status": "FAILED",
                                "error": error_msg
                            }
                        
                        elif current_status in ['IN_PROGRESS', 'QUEUED']:
                            # Continue polling
                            logger.info(f"⏳ Operation still {current_status}, waiting {delay}s before next poll...")
                            await asyncio.sleep(delay)
                            # Exponential backoff with max delay of 10 seconds
                            delay = min(delay * 1.5, 10.0)
                        else:
                            logger.warning(f"⚠️ Unknown status: {current_status}")
                            await asyncio.sleep(delay)
                    
                    elif response.status == 202:
                        # 202 means still processing
                        logger.info(f"⏳ Received 202 (still processing), waiting {delay}s...")
                        await asyncio.sleep(delay)
                        delay = min(delay * 1.5, 10.0)
                    
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Unexpected status code {response.status}: {error_text}")
                        return {
                            "status": "ERROR",
                            "error": f"HTTP {response.status}: {error_text}"
                        }
            
            except Exception as e:
                logger.error(f"❌ Error during polling attempt {attempt + 1}: {e}")
                if attempt < max_attempts - 1:
                    await asyncio.sleep(delay)
                else:
                    return {
                        "status": "ERROR",
                        "error": f"Polling failed after {max_attempts} attempts: {str(e)}"
                    }
    
    # Timeout
    logger.error(f"⏱️ Polling timed out after {max_attempts} attempts")
    return {
        "status": "TIMEOUT",
        "error": f"Operation did not complete within {max_attempts} polling attempts"
    }


async def poll_fal_operation(fal_request_id: str, submission_type: str = "text-to-video", status_url: str = "", model_name: str = "") -> str:
    """
    Poll FAL.ai for result and return the final video/image URL.
    For quick operations (images), polls until complete.
    For longer operations (videos), polls for 90 seconds then returns status message.
    
    Args:
        fal_request_id: The FAL.ai request ID to poll (can also be a full status_url)
        submission_type: Type of generation (text-to-video, text-to-image, etc.)
        status_url: Optional full status URL from FAL.ai response
        model_name: Optional model name to construct URL if status_url not provided
    
    Returns:
        String with the final result or error message
    """
    import aiohttp
    import asyncio
    import os
    import logging
    
    # Set up debug logging
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    logger.info(f"🔄 Starting poll for fal_request_id: {fal_request_id}, type: {submission_type}")
    
    fal_key = os.getenv("FAL_KEY")
    if not fal_key:
        logger.error("❌ FAL_KEY environment variable not set")
        return "Error: FAL_KEY environment variable not set"
    
    headers = {
        "Authorization": f"Key {fal_key}",
        "Content-Type": "application/json"
    }
    
    # Determine the status URL to use
    if status_url:
        # Use provided status_url
        final_status_url = status_url
        logger.info(f"📡 Using provided status URL: {final_status_url}")
    elif model_name:
        # Construct with model name
        final_status_url = f"https://queue.fal.run/{model_name}/requests/{fal_request_id}/status"
        logger.info(f"📡 Constructed status URL with model: {final_status_url}")
    else:
        # Fallback: treat fal_request_id as potentially being a full URL
        if fal_request_id.startswith("http"):
            final_status_url = fal_request_id
            logger.info(f"📡 Using fal_request_id as URL: {final_status_url}")
        else:
            # Last resort: try without model name (may fail with 405)
            final_status_url = f"https://queue.fal.run/requests/{fal_request_id}/status"
            logger.warning(f"⚠️ No status_url or model_name provided, using fallback: {final_status_url}")
    
    # Use unified timeout for both image and video generation (90 seconds - before ADK timeout)
    max_attempts = 18  # 18 attempts × 5s = 90 seconds for both (before ADK 120s timeout)
    
    # Create session with timeout
    timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout per request
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for attempt in range(max_attempts):
            try:
                logger.info(f"🔍 Polling attempt {attempt + 1}/{max_attempts}")
                async with session.get(final_status_url, headers=headers) as response:
                    if response.status == 200:
                        status_data = await response.json()
                        logger.info(f"📊 Status response: {status_data}")
                        
                        if status_data.get("status") == "COMPLETED":
                            logger.info("✅ Generation completed! Getting result...")
                            # Get the result using response_url from status
                            result_url = status_data.get("response_url")
                            if not result_url:
                                # Fallback: construct result URL without the /status suffix
                                result_url = final_status_url.replace("/status", "")
                            logger.info(f"📍 Using result URL: {result_url}")
                            async with session.get(result_url, headers=headers) as result_response:
                                if result_response.status == 200:
                                    result_data = await result_response.json()
                                    logger.info(f"📋 Result data: {result_data}")
                                    
                                    if submission_type == "text-to-video":
                                        video_url = result_data.get("video", {}).get("url")
                                        if video_url:
                                            final_result = f"✅ Video generated successfully! 🎬\n\n**Video URL:** {video_url}\n\nYou can download or view the video at this link."
                                            logger.info(f"🎬 Returning video result: {final_result}")
                                            return final_result
                                        else:
                                            error_result = f"❌ Error: No video URL found in result: {result_data}"
                                            logger.error(error_result)
                                            return error_result
                                    else:
                                        # Handle image results
                                        images = result_data.get("images", [])
                                        if images and len(images) > 0:
                                            image_url = images[0].get("url")
                                            if image_url:
                                                final_result = f"✅ Image generated successfully! 🖼️\n\n**Image URL:** {image_url}\n\nYou can view the image at this link."
                                                logger.info(f"🖼️ Returning image result: {final_result}")
                                                return final_result
                                        
                                        error_result = f"❌ Error: No image URL found in result: {result_data}"
                                        logger.error(error_result)
                                        return error_result
                                else:
                                    # Capture detailed error information
                                    error_text = await result_response.text()
                                    error_result = f"❌ Error getting result: HTTP {result_response.status}\nDetails: {error_text}"
                                    logger.error(error_result)
                                    return error_result
                        
                        elif status_data.get("status") == "FAILED":
                            error_msg = status_data.get("error", "Unknown error")
                            error_result = f"❌ Generation failed: {error_msg}"
                            logger.error(error_result)
                            return error_result
                        
                        else:
                            # Still processing, wait and continue
                            logger.info(f"⏳ Status: {status_data.get('status', 'UNKNOWN')}, waiting 5 seconds...")
                            await asyncio.sleep(5)
                            continue
                    
                    elif response.status == 202:
                        # HTTP 202 means "Accepted" - still processing
                        logger.info(f"⏳ Received HTTP 202 (still processing), waiting 5 seconds...")
                        await asyncio.sleep(5)
                        continue
                    
                    else:
                        error_result = f"❌ Error checking status: HTTP {response.status}"
                        logger.error(error_result)
                        return error_result
            
            except Exception as e:
                logger.warning(f"⚠️ Error during polling attempt {attempt + 1}: {str(e)}")
                if attempt < max_attempts - 1:  # If not the last attempt, continue trying
                    logger.info(f"🔄 Retrying in 5 seconds... (attempt {attempt + 2}/{max_attempts})")
                    await asyncio.sleep(5)
                    continue
                else:
                    # Only return error on the final attempt
                    error_result = f"❌ Error during polling: {str(e)}"
                    logger.error(error_result)
                    return error_result
        
        # Reached max attempts - return unified helpful message for both types
        timeout_result = (
            f"@Fal Your video/image is still being generated (taking longer than 90 seconds).\n\n"
            f"Video generation can take 2-5 minutes depending on the model and complexity.\n\n"
            f"Request ID: {fal_request_id}\n"
            f"Status URL: {final_status_url}\n\n"
            f"You can:\n\n"
            f"Wait a few minutes and ask me to check the status again\n"
            f"Check the status directly at: {final_status_url.replace('/status', '')}\n"
            f"I'll keep monitoring this in the background and will notify you when it's ready!"
        )
        logger.warning(f"⏰ Reached max polling attempts ({max_attempts}), returning status message")
        return timeout_result


# Create the polling agent
polling_agent = Agent(
    name="fal_polling_agent",
    model="gemini-2.0-flash",
    description="Specialized agent for polling FAL.ai operations until completion",
    instruction="""
    You are a specialized polling agent for FAL.ai operations.
    
    Your role is to:
    1. Take status_url and response_url from a queued FAL operation
    2. Poll the status_url until the operation completes
    3. Retrieve the final result from response_url when ready
    4. Return the result to the parent agent
    
    When you receive a request to poll a FAL operation:
    - Extract the fal_request_id and submission_type from the conversation
    - Use the poll_fal_operation tool with the fal_request_id and submission_type
    - The tool will handle all the polling logic and return when complete
    - Report the final result clearly to the user
    
    Be patient - some operations may take several minutes to complete.
    """,
    tools=[FunctionTool(func=poll_fal_operation)]
)

logger.info("✅ Polling agent created successfully")

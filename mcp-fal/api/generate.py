"""
Generate module for fal.ai MCP server.

This module provides tools for generating content
and managing queue operations with fal.ai models.
"""

from typing import Dict, Any, Optional
from fastmcp import FastMCP
from .utils import authenticated_request, sanitize_parameters, FalAPIError
from .config import FAL_QUEUE_URL, FAL_DIRECT_URL, AUTHENTICATED_TIMEOUT

def register_generation_tools(mcp: FastMCP):
    """Register generation-related tools with the MCP server."""
    
    async def _poll_until_complete_internal(status_url: str, response_url: str, max_polls: int = 240, poll_interval: int = 2) -> Dict[str, Any]:
        """
        Internal polling function that doesn't rely on MCP tool registration.
        
        Args:
            status_url: The status_url from a queued request
            response_url: The response_url from a queued request  
            max_polls: Maximum number of polls before timeout (default: 240 = 8 minutes)
            poll_interval: Seconds between polls (default: 2)
            
        Returns:
            The final generation result or error details
        """
        import asyncio
        
        try:
            for attempt in range(max_polls):
                try:
                    # Check status with shorter timeout for resilience
                    status_result = await authenticated_request(status_url, timeout=30.0)
                    
                    current_status = status_result.get("status", "UNKNOWN")
                    
                    if current_status == "COMPLETED":
                        try:
                            # Get final result with shorter timeout for resilience
                            final_result = await authenticated_request(response_url, timeout=30.0)
                            return {
                                "status": "COMPLETED",
                                "result": final_result,
                                "polls_taken": attempt + 1
                            }
                        except Exception as result_error:
                            # If result retrieval fails, retry once
                            await asyncio.sleep(1)
                            try:
                                final_result = await authenticated_request(response_url, timeout=30.0)
                                return {
                                    "status": "COMPLETED",
                                    "result": final_result,
                                    "polls_taken": attempt + 1
                                }
                            except Exception:
                                return {
                                    "status": "ERROR",
                                    "error": f"Failed to retrieve final result: {str(result_error)}",
                                    "polls_taken": attempt + 1
                                }
                        
                    elif current_status == "FAILED":
                        # Return failure details
                        return {
                            "status": "FAILED", 
                            "error": status_result.get("error", "Unknown error"),
                            "details": status_result,
                            "polls_taken": attempt + 1
                        }
                        
                    elif current_status in ["IN_QUEUE", "IN_PROGRESS"]:
                        # Still processing, wait and continue
                        if attempt < max_polls - 1:  # Don't sleep on last attempt
                            await asyncio.sleep(poll_interval)
                        continue
                        
                    else:
                        # Unknown status
                        return {
                            "status": "ERROR",
                            "error": f"Unknown status: {current_status}",
                            "details": status_result,
                            "polls_taken": attempt + 1
                        }
                
                except Exception as poll_error:
                    # If polling fails, wait and retry
                    if attempt < max_polls - 1:
                        await asyncio.sleep(poll_interval)
                        continue
                    else:
                        return {
                            "status": "ERROR",
                            "error": f"Polling failed: {str(poll_error)}",
                            "polls_taken": attempt + 1
                        }
            
            # Timeout reached
            return {
                "status": "TIMEOUT",
                "error": f"Operation did not complete within {max_polls * poll_interval} seconds",
                "polls_taken": max_polls
            }
            
        except FalAPIError as e:
            return {
                "status": "ERROR",
                "error": str(e),
                "polls_taken": 0
            }
    
    # Removed problematic **kwargs functions to fix FastMCP compatibility
    # Users should use the specialized generation functions instead (generate_image, generate_video, edit_image)

    @mcp.tool()
    async def result(url: str) -> Dict[str, Any]:
        """
        Get the result of a queued request.
        
        Args:
            url: The response_url from a queued request
            
        Returns:
            The generation result
        """
        if not isinstance(url, str):
            url = str(url)
        
        try:
            result = await authenticated_request(url)
            
            return result
            
        except FalAPIError as e:
            raise

    @mcp.tool()
    async def status(url: str) -> Dict[str, Any]:
        """
        Check the status of a queued request.
        
        Args:
            url: The status_url from a queued request
            
        Returns:
            The current status of the queued request
        """
        if not isinstance(url, str):
            url = str(url)
        
        try:
            result = await authenticated_request(url)
            
            return result
            
        except FalAPIError as e:
            raise

    @mcp.tool()
    async def cancel(url: str) -> Dict[str, Any]:
        """
        Cancel a queued request.
        
        Args:
            url: The cancel_url from a queued request
            
        Returns:
            The result of the cancellation attempt
        """
        if not isinstance(url, str):
            url = str(url)
        
        try:
            result = await authenticated_request(url, method="PUT")
            
            return result
            
        except FalAPIError as e:
            raise

    @mcp.tool()
    async def poll_until_complete(status_url: str, response_url: str, max_polls: int = 240, poll_interval: int = 2) -> Dict[str, Any]:
        """
        Poll a queued request until completion and return final result.
        
        This tool handles the entire polling workflow synchronously, checking status
        repeatedly until the operation completes or fails, then retrieving the final result.
        Uses shorter poll intervals and more resilient timeout handling.
        
        Args:
            status_url: The status_url from a queued request
            response_url: The response_url from a queued request  
            max_polls: Maximum number of polls before timeout (default: 240 = 8 minutes)
            poll_interval: Seconds between polls (default: 2)
            
        Returns:
            The final generation result or error details
        """
        import asyncio
        
        if not isinstance(status_url, str):
            status_url = str(status_url)
        if not isinstance(response_url, str):
            response_url = str(response_url)
            
        try:
            for attempt in range(max_polls):
                try:
                    # Check status with shorter timeout for resilience
                    status_result = await authenticated_request(status_url, timeout=30.0)
                    
                    current_status = status_result.get("status", "UNKNOWN")
                    
                    if current_status == "COMPLETED":
                        try:
                            # Get final result with shorter timeout for resilience
                            final_result = await authenticated_request(response_url, timeout=30.0)
                            return {
                                "status": "COMPLETED",
                                "result": final_result,
                                "polls_taken": attempt + 1
                            }
                        except Exception as result_error:
                            # If result retrieval fails, retry once
                            await asyncio.sleep(1)
                            try:
                                final_result = await authenticated_request(response_url, timeout=30.0)
                                return {
                                    "status": "COMPLETED",
                                    "result": final_result,
                                    "polls_taken": attempt + 1
                                }
                            except Exception:
                                return {
                                    "status": "ERROR",
                                    "error": f"Failed to retrieve final result: {str(result_error)}",
                                    "polls_taken": attempt + 1
                                }
                        
                    elif current_status == "FAILED":
                        # Return failure details
                        return {
                            "status": "FAILED", 
                            "error": status_result.get("error", "Unknown error"),
                            "details": status_result,
                            "polls_taken": attempt + 1
                        }
                        
                    elif current_status in ["IN_QUEUE", "IN_PROGRESS"]:
                        # Still processing, wait and continue
                        if attempt < max_polls - 1:  # Don't sleep on last attempt
                            await asyncio.sleep(poll_interval)
                        continue
                        
                    else:
                        # Unknown status
                        return {
                            "status": "ERROR",
                            "error": f"Unknown status: {current_status}",
                            "details": status_result,
                            "polls_taken": attempt + 1
                        }
                
                except Exception as poll_error:
                    # If polling fails, wait and retry
                    if attempt < max_polls - 1:
                        await asyncio.sleep(poll_interval)
                        continue
                    else:
                        return {
                            "status": "ERROR",
                            "error": f"Polling failed: {str(poll_error)}",
                            "polls_taken": attempt + 1
                        }
            
            # Timeout reached
            return {
                "status": "TIMEOUT",
                "error": f"Operation did not complete within {max_polls * poll_interval} seconds",
                "polls_taken": max_polls
            }
            
        except FalAPIError as e:
            raise

    @mcp.tool()
    async def generate_image(model: str, prompt: str, width: Optional[int] = None, height: Optional[int] = None) -> Dict[str, Any]:
        """
        Generate an image using a fal.ai model with automatic polling.
        
        This tool starts image generation and polls until completion, returning the final result.
        
        Args:
            model: The model ID to use (e.g., "fal-ai/flux/dev")
            prompt: Text description of the image to generate
            width: Optional width in pixels
            height: Optional height in pixels
            
        Returns:
            The final image generation result
        """
        # Prepare parameters
        parameters = {"prompt": prompt}
        if width is not None:
            parameters["width"] = width
        if height is not None:
            parameters["height"] = height
        
        # Sanitize parameters
        parameters = sanitize_parameters(parameters)
        
        try:
            # Start generation directly (queued)
            url = f"{FAL_QUEUE_URL}/{model}"
            queue_result = await authenticated_request(url, method="POST", json_data=parameters)
            
            # Extract URLs for polling
            status_url = queue_result.get("status_url")
            response_url = queue_result.get("response_url")
            
            if not status_url or not response_url:
                return {
                    "status": "ERROR",
                    "error": "Failed to get polling URLs from queue response",
                    "queue_result": queue_result
                }
            
            # Poll until completion
            return await _poll_until_complete_internal(status_url, response_url)
            
        except FalAPIError as e:
            return {
                "status": "ERROR",
                "error": str(e),
                "model": model,
                "prompt": prompt
            }

    @mcp.tool()
    async def generate_video(model: str, prompt: str, image_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate a video using a fal.ai model with automatic polling.
        
        This tool starts video generation and polls until completion, returning the final result.
        
        Args:
            model: The model ID to use (e.g., "fal-ai/kling-video/v2/master/image-to-video")
            prompt: Text description of the video to generate
            image_url: Optional input image URL for image-to-video models
            
        Returns:
            The final video generation result
        """
        # Prepare parameters
        parameters = {"prompt": prompt}
        if image_url is not None:
            parameters["image_url"] = image_url
        
        # Sanitize parameters
        parameters = sanitize_parameters(parameters)
        
        try:
            # Start generation directly (queued)
            url = f"{FAL_QUEUE_URL}/{model}"
            queue_result = await authenticated_request(url, method="POST", json_data=parameters)
            
            # Extract URLs for polling
            status_url = queue_result.get("status_url")
            response_url = queue_result.get("response_url")
            
            if not status_url or not response_url:
                return {
                    "status": "ERROR",
                    "error": "Failed to get polling URLs from queue response",
                    "queue_result": queue_result
                }
            
            # Poll until completion - videos take longer, so use extended timeout (30 minutes)
            return await _poll_until_complete_internal(status_url, response_url, max_polls=600, poll_interval=3)
            
        except FalAPIError as e:
            return {
                "status": "ERROR",
                "error": str(e),
                "model": model,
                "prompt": prompt
            }

    @mcp.tool()
    async def edit_image(model: str, image_url: str, prompt: str) -> Dict[str, Any]:
        """
        Edit an image using a fal.ai model with automatic polling.
        
        This tool starts image editing and polls until completion, returning the final result.
        
        Args:
            model: The model ID to use for image editing
            image_url: URL of the image to edit
            prompt: Text description of the edit to apply
            
        Returns:
            The final image editing result
        """
        # Prepare parameters
        parameters = {
            "image_url": image_url,
            "prompt": prompt
        }
        
        # Sanitize parameters
        parameters = sanitize_parameters(parameters)
        
        try:
            # Start generation directly (queued)
            url = f"{FAL_QUEUE_URL}/{model}"
            queue_result = await authenticated_request(url, method="POST", json_data=parameters)
            
            # Extract URLs for polling
            status_url = queue_result.get("status_url")
            response_url = queue_result.get("response_url")
            
            if not status_url or not response_url:
                return {
                    "status": "ERROR",
                    "error": "Failed to get polling URLs from queue response",
                    "queue_result": queue_result
                }
            
            # Poll until completion
            return await _poll_until_complete_internal(status_url, response_url)
            
        except FalAPIError as e:
            return {
                "status": "ERROR",
                "error": str(e),
                "model": model,
                "prompt": prompt
            }
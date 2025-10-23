# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import asyncio
import json
from typing import Dict, Any
from contextlib import asynccontextmanager

import google.auth
from fastapi import FastAPI, BackgroundTasks, Request
from starlette.middleware.base import BaseHTTPMiddleware
from google.adk.cli.fast_api import get_fast_api_app
from google.cloud import logging as google_cloud_logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider, export
from vertexai import agent_engines

from app.utils.gcs import create_bucket_if_not_exists
from app.utils.tracing import CloudTraceLoggingSpanExporter
from app.utils.typing import Feedback
from app.polling_manager import get_polling_manager

# Deployment test - October 3, 2025 08:40 UTC
_, project_id = google.auth.default()
logging_client = google_cloud_logging.Client()
logger = logging_client.logger(__name__)
allow_origins = (
    os.getenv("ALLOW_ORIGINS", "").split(",") if os.getenv("ALLOW_ORIGINS") else None
)

bucket_name = f"gs://{project_id}-my-agentic-rag-logs-data"
create_bucket_if_not_exists(
    bucket_name=bucket_name, project=project_id, location="us-central1"
)

# Configure artifacts bucket for media files from WhatsApp
artifacts_bucket_name = os.getenv("ARTIFACTS_BUCKET_NAME", "adk_artifact")
artifacts_bucket_uri = f"gs://{artifacts_bucket_name}"

provider = TracerProvider()
processor = export.BatchSpanProcessor(CloudTraceLoggingSpanExporter())
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Agent Engine session configuration - commented out for dev testing
# Use environment variable for agent name, default to project name
# agent_name = os.environ.get("AGENT_ENGINE_SESSION_NAME", "my-agentic-rag")

# Check if an agent with this name already exists
# existing_agents = list(agent_engines.list(filter=f"display_name={agent_name}"))

# if existing_agents:
#     # Use the existing agent
#     agent_engine = existing_agents[0]
# else:
#     # Create a new agent if none exists
#     agent_engine = agent_engines.create(display_name=agent_name)

# Use in-memory session service for dev/testing
# session_service_uri = f"agentengine://{agent_engine.resource_name}"


class SessionContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to capture session_id from ADK requests and store it in context.
    This allows long-running tools to access the session_id.
    """
    async def dispatch(self, request: Request, call_next):
        # Only process /run requests
        if request.url.path == "/run":
            try:
                # Read request body
                body = await request.body()
                body_json = json.loads(body)
                
                # Extract session_id
                session_id = body_json.get("sessionId")
                user_id = body_json.get("userId")
                
                if session_id:
                    # Store in context variable
                    from app.adk_runner import current_session_context
                    current_session_context.set({
                        "session_id": session_id,
                        "user_id": user_id or "unknown"
                    })
                    print(f"🔍 Middleware captured session_id: {session_id}")
                
                # Reconstruct request with body
                async def receive():
                    return {"type": "http.request", "body": body}
                
                request._receive = receive
                
            except Exception as e:
                print(f"⚠️ Error in session context middleware: {e}")
        
        response = await call_next(request)
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events for the FastAPI app."""
    # Startup
    print("🚀 FastAPI server starting up...")
    
    # Configure polling manager with app reference so it can get the runner dynamically
    try:
        from app.polling_manager import get_polling_manager
        polling_mgr = get_polling_manager()
        
        # Store a reference to the app in the polling manager so it can get the runner dynamically
        polling_mgr.app = app
        print("✅ Polling manager configured with app reference")
        
    except Exception as e:
        print(f"❌ Error configuring polling manager: {e}")
    
    yield
    
    # Shutdown
    print("🛑 FastAPI server shutting down...")


def get_custom_runner_from_app(app: FastAPI):
    """Get the custom ADK runner from the FastAPI app state."""
    try:
        if hasattr(app.state, 'custom_adk_runner'):
            return app.state.custom_adk_runner
        return None
    except Exception as e:
        print(f"❌ Error getting custom runner: {e}")
        return None



app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=True,
    artifact_service_uri=artifacts_bucket_uri,
    allow_origins=allow_origins,
    lifespan=lifespan,
    # session_service_uri=session_service_uri,  # Comment out for dev testing
)
app.title = "my-agentic-rag"
app.description = "API for interacting with the Agent my-agentic-rag"

# Add session context middleware to capture session_id from requests
app.add_middleware(SessionContextMiddleware)
print("✅ Session context middleware added to capture session_id from /run requests")


@app.get("/custom-runner/info")
async def get_custom_runner_info() -> Dict[str, Any]:
    """Get information about the custom ADK runner."""
    try:
        custom_runner = get_custom_runner_from_app(app)
        if custom_runner:
            return custom_runner.get_runner_info()
        else:
            return {"status": "error", "message": "Custom runner not available"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/custom-runner/complete-operation")
async def complete_custom_runner_operation(
    data: Dict[str, Any]
) -> Dict[str, Any]:
    """Complete a long-running operation using the custom runner."""
    try:
        custom_runner = get_custom_runner_from_app(app)
        if not custom_runner:
            return {"status": "error", "message": "Custom runner not available"}
        
        session_id = data.get("session_id")
        operation_id = data.get("operation_id")
        result_data = data.get("result_data", {})
        
        if not session_id or not operation_id:
            return {"status": "error", "message": "Missing session_id or operation_id"}
        
        # Complete the operation
        response_stream = await custom_runner.complete_long_running_operation(
            session_id=session_id,
            operation_id=operation_id,
            result_data=result_data
        )
        
        if response_stream:
            return {
                "status": "success",
                "message": f"Operation {operation_id} completed successfully",
                "session_id": session_id
            }
        else:
            return {
                "status": "error", 
                "message": f"Could not complete operation {operation_id}"
            }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/health")
def health_check() -> dict[str, str]:
    """Health check endpoint to test CI/CD pipeline.

    Returns:
        Health status message with timestamp
    """
    import datetime
    return {
        "status": "healthy", 
        "message": "Webhook system deployed - video generation callbacks enabled!", 
        "timestamp": datetime.datetime.now().isoformat(),
        "version": "v1.3"
    }

@app.get("/polling/status")
def polling_status() -> dict:
    """Get current polling manager status and pending operations.
    
    Returns:
        Current polling status and pending operations
    """
    polling_manager = get_polling_manager()
    pending_ops = {}
    
    for fal_id, operation in polling_manager.pending_operations.items():
        pending_ops[fal_id] = {
            "function_call_id": operation.function_call_id,
            "session_id": operation.session_id,
            "user_id": operation.user_id,
            "operation_type": operation.operation_type,
            "prompt": operation.prompt[:100] + "..." if len(operation.prompt) > 100 else operation.prompt
        }
    
    return {
        "status": "active",
        "pending_operations_count": len(pending_ops),
        "pending_operations": pending_ops,
        "polling_active": bool(polling_manager.pending_operations)
    }

@app.get("/version")
def version_info() -> dict[str, str]:
    """Version and deployment info endpoint.
    
    Returns:
        Version information including commit SHA from deployment
    """
    import datetime
    commit_sha = os.environ.get("COMMIT_SHA", "unknown")
    return {
        "version": "v1.3",
        "commit_sha": commit_sha,
        "deployment_time": datetime.datetime.now().isoformat(),
        "message": "End-to-end CI/CD pipeline test with commit-based tagging",
        "environment": os.environ.get("ENV", "unknown"),
        "pipeline_test": "active"
    }

@app.post("/feedback")
def collect_feedback(feedback: Feedback) -> dict[str, str]:
    """Collect and log feedback.

    Args:
        feedback: The feedback data to log

    Returns:
        Success message
    """
    logger.log_struct(feedback.model_dump(), severity="INFO")
    return {"status": "success"}


@app.post("/long-running/start-polling")
async def start_long_running_polling(
    operation_data: Dict[str, Any],
    background_tasks: BackgroundTasks
) -> Dict[str, str]:
    """
    Start polling a long-running operation in the background.
    
    Expected operation_data format:
    {
        "operation_id": "video_gen_123abc",
        "session_id": "session_123", 
        "user_id": "user_456",
        "function_call_id": "call_789",
        "function_name": "generate_video_long_running"
    }
    """
    try:
        operation_id = operation_data.get("operation_id")
        session_id = operation_data.get("session_id")
        user_id = operation_data.get("user_id")
        function_call_id = operation_data.get("function_call_id")
        function_name = operation_data.get("function_name", "generate_video_long_running")
        
        if not all([operation_id, session_id, user_id, function_call_id]):
            return {"status": "error", "message": "Missing required fields"}
        
        # Get the agent runner from the app
        # This will need to be properly integrated with the ADK agent runner
        logger.info(f"🚀 Starting background polling for operation: {operation_id}")
        
        # For now, we'll start a simple background task
        # In production, this should integrate with the actual ADK agent runner
        background_tasks.add_task(
            poll_operation_background,
            operation_id,
            session_id,
            user_id,
            function_call_id,
            function_name
        )
        
        return {
            "status": "success",
            "message": f"Started polling operation {operation_id}",
            "operation_id": operation_id
        }
        
    except Exception as e:
        logger.error(f"❌ Error starting long-running polling: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/long-running/status/{operation_id}")
async def get_operation_status(operation_id: str) -> Dict[str, Any]:
    """Get the current status of a long-running operation."""
    try:
        polling_manager = get_polling_manager()
        # For now, just return the pending operations info
        if operation_id in polling_manager.pending_operations:
            operation = polling_manager.pending_operations[operation_id]
            return {
                "operation_id": operation_id,
                "status": "IN_PROGRESS",
                "model_name": operation.model_name,
                "operation_type": operation.operation_type
            }
        else:
            return {
                "operation_id": operation_id,
                "status": "NOT_FOUND",
                "message": "Operation not found in pending operations"
            }
    except Exception as e:
        logger.error(f"❌ Error getting operation status: {e}")
        return {
            "operation_id": operation_id,
            "status": "ERROR",
            "error": str(e)
        }


async def poll_operation_background(
    operation_id: str,
    session_id: str,
    user_id: str,
    function_call_id: str,
    function_name: str
):
    """Background task to poll long-running operations."""
    try:
        logger.info(f"🔄 Background polling started for operation: {operation_id}")
        
        # For now, we'll just poll the status
        # TODO: Integrate with actual ADK agent runner for completion
        max_attempts = 120  # 10 minutes
        
        polling_manager = get_polling_manager()
        
        for attempt in range(max_attempts):
            # Check if operation is still in pending operations
            if operation_id in polling_manager.pending_operations:
                operation = polling_manager.pending_operations[operation_id]
                status = {
                    "operation_id": operation_id,
                    "status": "IN_PROGRESS",
                    "model_name": operation.model_name,
                    "operation_type": operation.operation_type
                }
            else:
                status = {
                    "operation_id": operation_id,
                    "status": "COMPLETED",
                    "message": "Operation completed and removed from pending list"
                }
            
            if status["status"] in ["COMPLETED", "FAILED"]:
                logger.info(f"✅ Operation {operation_id} completed with status: {status['status']}")
                
                # TODO: Send result back to agent runner
                # This requires integration with the ADK agent runner instance
                # For now, we'll just log the completion
                
                if status["status"] == "COMPLETED":
                    result_url = status.get("video_url") or status.get("image_url") or status.get("result_url")
                    logger.info(f"🎉 Operation {operation_id} completed successfully! Result: {result_url}")
                else:
                    logger.error(f"❌ Operation {operation_id} failed: {status.get('error', 'Unknown error')}")
                
                break
                
            elif status["status"] == "IN_PROGRESS":
                logger.info(f"⏳ Operation {operation_id} still in progress (attempt {attempt + 1}/{max_attempts})")
                await asyncio.sleep(5)  # Wait 5 seconds before next poll
                continue
            else:
                logger.error(f"❌ Unknown status for operation {operation_id}: {status}")
                break
                
        else:
            logger.error(f"⏰ Timeout polling operation {operation_id}")
            
    except Exception as e:
        logger.error(f"❌ Error in background polling for {operation_id}: {e}")


# Main execution
# Deployment Test: Full CI/CD pipeline test - October 3, 2025 13:45 UTC
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

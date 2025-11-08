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
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

import google.auth
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from google.adk.cli.fast_api import get_fast_api_app
from google.cloud import logging as google_cloud_logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider, export
from vertexai import agent_engines

from app.utils.gcs import create_bucket_if_not_exists
from app.utils.tracing import CloudTraceLoggingSpanExporter
from app.utils.typing import Feedback

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

# Session Service Configuration
# ADK's get_fast_api_app() expects a database connection string for session_service_uri
# 
# Options for session persistence:
# 1. SQLite: "sqlite:///./sessions.db" - Ephemeral (lost on container restart)
# 2. PostgreSQL: "postgresql://..." - Fully persistent (recommended for production)
# 3. MySQL: "mysql://..." - Fully persistent alternative
#
# Production approach: Cloud SQL PostgreSQL for persistent session storage
# - Connection string provided via DB_CONNECTION_STRING environment variable
# - Format: postgresql://user:pass@/dbname?host=/cloudsql/project:region:instance
# - Sessions persist across container restarts and deployments
# - Scalable and production-ready
#
# Note: Connection pool parameters (pool_size, pool_pre_ping, etc.) cannot be passed
# via the connection string as they are create_engine() parameters, not DSN parameters.
# ADK's DatabaseSessionService uses default SQLAlchemy pooling settings.
# The db-g1-small tier upgrade (1.7GB RAM) provides sufficient resources for default pooling.
#
# Development fallback: SQLite if DB_CONNECTION_STRING not set
session_service_uri = os.getenv("DB_CONNECTION_STRING", "sqlite:///./sessions.db")

# GCS buckets for artifact storage
session_bucket_name = f"{project_id}-my-agentic-rag-adk-sessions"
create_bucket_if_not_exists(
    bucket_name=f"gs://{session_bucket_name}",
    project=project_id,
    location="us-central1"
)

logger.log_struct({
    "message": "ADK Session Service Configuration",
    "session_service_type": "Cloud SQL PostgreSQL" if "postgresql://" in session_service_uri else "SQLite (ephemeral)",
    "session_service_uri_masked": session_service_uri.split("@")[0] + "@***" if "@" in session_service_uri else session_service_uri,
    "artifacts_bucket_uri": artifacts_bucket_uri,
    "gcs_session_bucket": session_bucket_name,
    "persistence": "Fully persistent" if "postgresql://" in session_service_uri else "Ephemeral",
    "database_tier": "db-g1-small (1.7GB RAM)" if "postgresql://" in session_service_uri else "N/A",
    "project_id": project_id
}, severity="INFO")

provider = TracerProvider()
processor = export.BatchSpanProcessor(CloudTraceLoggingSpanExporter())
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

# Point to the app directory where root_agent is defined
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events for the FastAPI app."""
    # Startup
    print("🚀 FastAPI server starting up...")
    print(f"📦 Session Service: {session_service_uri.split('@')[0] + '@***' if '@' in session_service_uri else session_service_uri}")
    print(f"   Type: {'PostgreSQL (Persistent)' if 'postgresql://' in session_service_uri else 'SQLite (Ephemeral)'}")
    print(f"📦 Artifact Service: {artifacts_bucket_uri}")
    print(f"🏗️  Agent Directory: {AGENT_DIR}")
    if "postgresql://" not in session_service_uri:
        print(f"💾 GCS Session Bucket (reserved): {session_bucket_name}")
    
    yield
    
    # Shutdown
    print("🛑 FastAPI server shutting down...")


# Create the FastAPI app using ADK's get_fast_api_app
# 
# Session Management Strategy:
# - Cloud SQL PostgreSQL for persistent session storage (production)
# - Connection via Unix socket: /cloudsql/project:region:instance
# - Sessions survive container restarts, deployments, and scaling
# - SQLite fallback for local development without Cloud SQL
#
# Why PostgreSQL?
# - Fully persistent across all container lifecycle events
# - Scales horizontally with multiple Cloud Run instances
# - Managed service with automatic backups and HA (production)
# - Standard database URL format supported by ADK
app = get_fast_api_app(
    agents_dir=AGENT_DIR,
    session_service_uri=session_service_uri,  # PostgreSQL or SQLite
    artifact_service_uri=artifacts_bucket_uri,  # GCS bucket for user-scoped artifacts
    allow_origins=allow_origins,
    web=True,
)
app.title = "my-agentic-rag"
app.description = "API for interacting with the Agent my-agentic-rag"


class RemoveUsageMetadataMiddleware(BaseHTTPMiddleware):
    """Middleware to remove usage statistics from API responses."""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Only process JSON responses
        if response.headers.get("content-type", "").startswith("application/json"):
            # Read the response body
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            
            try:
                # Parse JSON
                data = json.loads(body.decode())
                
                # Remove usage_metadata at any level in the response
                def remove_usage_metadata(obj):
                    if isinstance(obj, dict):
                        # Remove usage_metadata keys
                        if 'usage_metadata' in obj:
                            del obj['usage_metadata']
                        if 'usageMetadata' in obj:
                            del obj['usageMetadata']
                        # Also remove specific usage fields
                        for key in ['prompt_token_count', 'candidates_token_count', 
                                   'total_token_count', 'promptTokenCount', 
                                   'candidatesTokenCount', 'totalTokenCount']:
                            if key in obj:
                                del obj[key]
                        # Recursively process nested objects
                        for value in obj.values():
                            remove_usage_metadata(value)
                    elif isinstance(obj, list):
                        for item in obj:
                            remove_usage_metadata(item)
                
                remove_usage_metadata(data)
                
                # Return modified response
                return JSONResponse(
                    content=data,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type
                )
            except (json.JSONDecodeError, UnicodeDecodeError):
                # If we can't parse the JSON, return the original response
                pass
        
        return response


# Add the middleware to the app
app.add_middleware(RemoveUsageMetadataMiddleware)


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



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

# Configure session storage for ADK using VertexAI Session Service (GCS-backed)
# This provides persistent session storage across container restarts and deployments
session_bucket_name = f"{project_id}-my-agentic-rag-adk-sessions"
session_service_uri = f"gs://{session_bucket_name}"

# Create session bucket if it doesn't exist (for local development)
# In production, this bucket is created by Terraform
create_bucket_if_not_exists(
    bucket_name=session_service_uri,
    project=project_id,
    location="us-central1"
)

logger.log_struct({
    "message": "ADK Session Service Configuration",
    "session_service_uri": session_service_uri,
    "artifacts_bucket_uri": artifacts_bucket_uri,
    "project_id": project_id,
    "note": "Using GCS-backed VertexAI Session Service for persistent session storage"
}, severity="INFO")

provider = TracerProvider()
processor = export.BatchSpanProcessor(CloudTraceLoggingSpanExporter())
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

# Point to the app directory where root_agent is defined
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Session Management Strategy:
# ADK uses GCS-backed VertexAI Session Service for persistent session storage
# This provides:
# - Persistent sessions across container restarts and deployments
# - Scalable storage for multiple concurrent users
# - Automatic session management via GCS lifecycle rules (90-day retention)
# - Cloud Run compatibility for serverless deployments
#
# The index.js WhatsApp bot implements session retrieval/reuse logic by:
# 1. Checking if a session exists for a user via ADK API (getExistingADKSession)
# 2. Reusing existing sessions when found (persistent across restarts)
# 3. Creating new sessions only when needed
#
# Session data is stored in GCS bucket: {project_id}-my-agentic-rag-adk-sessions
# Path structure: {app_name}/{user_id}/session.json


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events for the FastAPI app."""
    # Startup
    print("🚀 FastAPI server starting up...")
    print(f"📦 Session Service: {session_service_uri} (GCS-backed VertexAI Session Service)")
    print(f"📦 Artifact Service: {artifacts_bucket_uri}")
    print(f"🏗️  Agent Directory: {AGENT_DIR}")
    
    yield
    
    # Shutdown
    print("🛑 FastAPI server shutting down...")


# Create the FastAPI app using ADK's get_fast_api_app
# Session storage: GCS-backed VertexAI Session Service (persistent across restarts)
# User state: Managed via user-scoped state (user: prefix)
# Artifacts: GCS bucket for user-scoped artifacts
app = get_fast_api_app(
    agents_dir=AGENT_DIR,
    session_service_uri=session_service_uri,  # GCS-backed persistent sessions
    artifact_service_uri=artifacts_bucket_uri,  # GCS bucket for user-scoped artifacts
    allow_origins=allow_origins,
    web=True,
)
app.title = "my-agentic-rag"
app.description = "API for interacting with the Agent my-agentic-rag"


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



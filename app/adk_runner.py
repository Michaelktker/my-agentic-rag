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

from __future__ import annotations

import asyncio
import logging
from contextvars import ContextVar
from datetime import datetime
from typing import Dict, Any, Optional
import google.auth
from google.cloud import logging as google_cloud_logging
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from app.agent import root_agent

# Context variable to store current session info during execution
current_session_context: ContextVar[Optional[Dict[str, str]]] = ContextVar('current_session_context', default=None)


class CustomADKRunner:
    """
    Custom ADK Runner for enhanced session management and long-running operations.
    
    This runner provides:
    - Session state management
    - Long-running operation resumption
    - Background polling coordination
    """
    
    def __init__(self, app_name: str = "my-agentic-rag"):
        """Initialize the custom ADK runner."""
        self.app_name = app_name
        self.logger = self._setup_logging()
        
        # Initialize session service
        self.session_service = InMemorySessionService()
        
        # Initialize the ADK runner
        self.runner = Runner(
            agent=root_agent,
            app_name=app_name,
            session_service=self.session_service
        )
        
        # Active sessions registry
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        
        self.logger.info(f"✅ Custom ADK Runner initialized for app: {app_name}")
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for the custom runner."""
        try:
            _, project_id = google.auth.default()
            logging_client = google_cloud_logging.Client()
            cloud_logger = logging_client.logger("adk_runner")
            
            # Create local logger that also sends to Cloud Logging
            logger = logging.getLogger("adk_runner")
            logger.setLevel(logging.INFO)
            
            # Add Cloud Logging handler
            handler = google_cloud_logging.handlers.CloudLoggingHandler(logging_client)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
            return logger
            
        except Exception as e:
            # Fallback to console logging
            logger = logging.getLogger("adk_runner")
            logger.setLevel(logging.INFO)
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.warning(f"Could not setup Cloud Logging: {e}")
            return logger
    
    async def create_session(self, user_id: str, session_id: Optional[str] = None) -> str:
        """
        Create a new session for the user.
        
        Args:
            user_id: The user ID (ensure not None)
            session_id: Optional session ID, will be generated if not provided
            
        Returns:
            The session ID
        """
        # Ensure user_id is valid
        if not user_id or user_id == "":
            user_id = "default_user"
            
        if not session_id:
            session_id = f"session_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Create session in ADK session service
        session = await self.session_service.create_session(
            app_name=self.app_name,
            user_id=user_id,
            session_id=session_id
        )
        
        # Track in our registry
        self.active_sessions[session_id] = {
            "user_id": user_id,
            "session_id": session_id,
            "created_at": datetime.now(),
            "session": session
        }
        
        self.logger.info(f"✅ Created session {session_id} for user {user_id}")
        return session_id
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session information."""
        return self.active_sessions.get(session_id)
    
    async def send_function_response(
        self,
        session_id: str,
        operation_id: str,
        result_data: Dict[str, Any],
        function_call_id: str = None,
        function_name: str = "generate_image_flux_pro"
    ) -> Optional[Any]:
        """
        Send a function response back to the agent to resume conversation.
        
        This is the key method for resuming agents after long-running operations.
        """
        try:
            session_info = await self.get_session(session_id)
            if not session_info:
                self.logger.error(f"❌ Session {session_id} not found")
                return None
            
            user_id = session_info["user_id"]
            
            # Create function response content
            function_response = types.Part(
                function_response=types.FunctionResponse(
                    id=function_call_id or operation_id,  # Use actual function call ID if available
                    name=function_name,  # The function that completed
                    response=result_data,
                )
            )
            
            # Create message content
            new_message = types.Content(
                parts=[function_response], 
                role="user"
            )
            
            # Send the response using the ADK runner
            events = self.runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=new_message
            )
            
            self.logger.info(f"✅ Sent function response for operation {operation_id}")
            return events
            
        except Exception as e:
            self.logger.error(f"❌ Error sending function response: {e}")
            return None
    
    async def complete_long_running_operation(
        self,
        session_id: str,
        operation_id: str,
        result_data: Dict[str, Any],
        function_call_id: str = None,
        function_name: str = "generate_image_flux_pro"
    ) -> Optional[Any]:
        """
        Complete a long-running operation and resume the agent.
        
        Args:
            session_id: The session ID
            operation_id: The operation ID
            result_data: The result data from the completed operation
            
        Returns:
            Response stream from the agent
        """
        try:
            self.logger.info(f"🔄 Completing operation {operation_id} for session {session_id}")
            
            # Send function response to resume the agent
            response_stream = await self.send_function_response(
                session_id=session_id,
                operation_id=operation_id,
                result_data=result_data,
                function_call_id=function_call_id,
                function_name=function_name
            )
            
            if response_stream:
                self.logger.info(f"✅ Successfully completed operation {operation_id}")
                return response_stream
            else:
                self.logger.error(f"❌ Failed to complete operation {operation_id}")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ Error completing operation {operation_id}: {e}")
            return None
    
    def get_runner_info(self) -> Dict[str, Any]:
        """Get information about the runner."""
        return {
            "app_name": self.app_name,
            "active_sessions": len(self.active_sessions),
            "session_ids": list(self.active_sessions.keys()),
            "runner_type": "CustomADKRunner",
            "agent_name": getattr(root_agent, 'name', 'unknown')
        }


# Global runner instance
_runner_instance: Optional[CustomADKRunner] = None


async def initialize_runner() -> CustomADKRunner:
    """Initialize and return the global runner instance."""
    global _runner_instance
    if _runner_instance is None:
        _runner_instance = CustomADKRunner()
    return _runner_instance


def get_runner() -> Optional[CustomADKRunner]:
    """Get the global runner instance (sync)."""
    return _runner_instance
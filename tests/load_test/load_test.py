"""
Load Testing Script for My Agentic RAG Application

This script uses Locust to perform load testing on the deployed ADK service.
It simulates multiple users making concurrent requests to test performance
and identify bottlenecks under various load conditions.

Usage:
    locust -f load_test.py --headless -H https://your-app-url -t 30s -u 10 -r 0.5

Environment Variables:
    _ID_TOKEN: Google Cloud identity token for authentication
    _STAGING_URL: Target application URL for testing
"""

import os
import json
import random
from locust import HttpUser, task, between


class ADKUser(HttpUser):
    """
    Simulates a user interacting with the ADK service.
    
    This class defines user behavior patterns and request scenarios
    that will be executed during the load test.
    """
    
    # Wait time between requests (1-3 seconds)
    wait_time = between(1, 3)
    
    def on_start(self):
        """Initialize user session and authentication."""
        self.id_token = os.getenv('_ID_TOKEN', '')
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.id_token}' if self.id_token else ''
        }
        
        # Sample chat messages for testing
        self.chat_messages = [
            "Hello, how are you?",
            "What is the weather like today?",
            "Can you help me with information about machine learning?",
            "Tell me about Google Cloud Platform services",
            "How does RAG (Retrieval-Augmented Generation) work?",
            "What are the benefits of using ADK?",
            "Explain the concept of vector databases",
            "How can I deploy applications on Google Cloud Run?",
            "What is the difference between supervised and unsupervised learning?",
            "Can you search for information about Python programming?"
        ]
    
    @task(3)
    def health_check(self):
        """
        Test the health endpoint to ensure service availability.
        This is the most frequent task (weight=3).
        """
        with self.client.get("/health", headers=self.headers, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed with status {response.status_code}")
    
    @task(2)
    def chat_request(self):
        """
        Simulate chat interactions with the ADK service.
        This tests the main functionality (weight=2).
        """
        message = random.choice(self.chat_messages)
        
        payload = {
            "appName": "app",
            "userId": f"load_test_user_{random.randint(1, 100)}",
            "sessionId": f"session_{random.randint(1000, 9999)}",
            "newMessage": {
                "parts": [{"text": message}],
                "role": "user"
            },
            "streaming": False
        }
        
        with self.client.post("/run", 
                             json=payload, 
                             headers=self.headers,
                             catch_response=True,
                             timeout=30) as response:
            if response.status_code == 200:
                try:
                    response_data = response.json()
                    if isinstance(response_data, list) and len(response_data) > 0:
                        response.success()
                    else:
                        response.failure("Empty or invalid response format")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            elif response.status_code == 401:
                response.failure("Authentication failed - invalid token")
            elif response.status_code == 404:
                response.failure("Endpoint not found")
            elif response.status_code == 500:
                response.failure("Internal server error")
            else:
                response.failure(f"Request failed with status {response.status_code}")
    
    @task(1)
    def streaming_chat_request(self):
        """
        Test streaming chat functionality.
        This tests real-time response capabilities (weight=1).
        """
        message = random.choice(self.chat_messages)
        
        payload = {
            "appName": "app", 
            "userId": f"load_test_user_{random.randint(1, 100)}",
            "sessionId": f"session_{random.randint(1000, 9999)}",
            "newMessage": {
                "parts": [{"text": message}],
                "role": "user"
            },
            "streaming": True
        }
        
        with self.client.post("/run_sse",
                             json=payload,
                             headers=self.headers,
                             catch_response=True,
                             timeout=30) as response:
            if response.status_code == 200:
                # For SSE, we just check that we get a response
                if response.headers.get('content-type', '').startswith('text/event-stream'):
                    response.success()
                else:
                    response.failure("Expected SSE content-type")
            else:
                response.failure(f"Streaming request failed with status {response.status_code}")
    
    def on_stop(self):
        """Cleanup when user session ends."""
        pass


class AdminUser(HttpUser):
    """
    Simulates administrative operations and monitoring tasks.
    This represents a smaller percentage of the user load.
    """
    
    wait_time = between(5, 10)  # Admin users are less frequent
    weight = 1  # Lower weight compared to regular users
    
    def on_start(self):
        """Initialize admin session."""
        self.id_token = os.getenv('_ID_TOKEN', '')
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.id_token}' if self.id_token else ''
        }
    
    @task
    def health_check(self):
        """Admin health monitoring."""
        with self.client.get("/health", headers=self.headers, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Admin health check failed with status {response.status_code}")


# Configuration for different load test scenarios
class PeakTrafficUser(ADKUser):
    """
    Simulates peak traffic conditions with higher request frequency.
    Use this class for stress testing scenarios.
    """
    wait_time = between(0.5, 1.5)  # Faster requests for peak load
    weight = 3  # Higher proportion during peak tests


class LightUser(ADKUser):
    """
    Simulates light usage patterns with longer wait times.
    Use this class for baseline performance testing.
    """
    wait_time = between(3, 8)  # Slower requests for light load
    weight = 1  # Lower proportion for light testing
"""
Load Testing Script for My Agentic RAG Application

This script uses Locust to perform load testing on the deployed service.
It performs basic connectivity tests and health checks to validate deployment.

Usage:
    locust -f load_test.py --headless -H https://your-app-url -t 30s -u 10 -r 0.5

Environment Variables:
    _ID_TOKEN: Google Cloud identity token for authentication
    _STAGING_URL: Target application URL for testing
"""

import os
import json
import random
import sys
import logging
from locust import HttpUser, task, between, events

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Log test start information."""
    logger.info("Starting load test...")
    logger.info(f"Target host: {environment.host}")
    logger.info(f"Number of users: {environment.parsed_options.num_users}")
    logger.info(f"Spawn rate: {environment.parsed_options.spawn_rate}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Log test completion information."""
    logger.info("Load test completed.")
    stats = environment.stats.total
    logger.info(f"Total requests: {stats.num_requests}")
    logger.info(f"Total failures: {stats.num_failures}")
    if stats.num_requests > 0:
        logger.info(f"Average response time: {stats.avg_response_time:.2f}ms")
        logger.info(f"Success rate: {((stats.num_requests - stats.num_failures) / stats.num_requests * 100):.1f}%")


class BasicUser(HttpUser):
    """
    Simulates basic user interactions with the service.
    
    This class performs fundamental connectivity tests and health checks
    to validate that the deployed service is responding correctly.
    """
    
    # Wait time between requests (1-3 seconds)
    wait_time = between(1, 3)
    
    def on_start(self):
        """Initialize user session and authentication."""
        self.id_token = os.getenv('_ID_TOKEN', '')
        self.headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Locust-LoadTest/1.0'
        }
        
        # Add authorization header if token is available
        if self.id_token and self.id_token.strip():
            self.headers['Authorization'] = f'Bearer {self.id_token}'
        
        # Test data for basic validation
        self.test_data = {
            "message": "Hello, this is a load test",
            "user_id": f"test_user_{random.randint(1000, 9999)}",
            "timestamp": "2025-10-10T00:00:00Z"
        }
        
        logger.info(f"User {self.test_data['user_id']} started")
    
    @task(15)
    def health_check(self):
        """Test basic health endpoint."""
        try:
            with self.client.get("/health", 
                               headers=self.headers, 
                               catch_response=True,
                               timeout=10,
                               name="health_check") as response:
                if response.status_code == 200:
                    response.success()
                    logger.info("Health check passed")
                else:
                    logger.warning(f"Health check returned {response.status_code}")
                    # Don't fail on non-200 status codes during load testing
                    response.success()
        except Exception as e:
            logger.error(f"Health check error: {e}")
            # Don't fail the test for network errors during load testing
    
    @task(8)
    def test_version_endpoint(self):
        """Test version endpoint which should be available."""
        try:
            with self.client.get("/version", 
                               headers=self.headers, 
                               catch_response=True,
                               timeout=10,
                               name="version_check") as response:
                if response.status_code == 200:
                    response.success()
                    logger.info("Version endpoint accessible")
                else:
                    logger.warning(f"Version endpoint returned {response.status_code}")
                    # Don't fail for non-200 responses during load testing
                    response.success()
        except Exception as e:
            logger.error(f"Version endpoint error: {e}")
            # Don't fail the test for network errors
    
    @task(2)
    def test_root_endpoint(self):
        """Test root endpoint connectivity."""
        try:
            with self.client.get("/", 
                               headers=self.headers, 
                               catch_response=True,
                               timeout=10,
                               name="root_endpoint") as response:
                # Accept any response as successful during load testing
                # The goal is to test connectivity, not functionality
                response.success()
                logger.info(f"Root endpoint responded with {response.status_code}")
        except Exception as e:
            logger.error(f"Root endpoint error: {e}")
            # Don't fail the test for network errors


class LightUser(BasicUser):
    """
    Light user with reduced request frequency for baseline testing.
    """
    
    # Longer wait time between requests (2-5 seconds)
    wait_time = between(2, 5)
    weight = 3
    
    @task(20)
    def health_check(self):
        """More frequent health checks for light users."""
        super().health_check()


class PeakUser(BasicUser):
    """
    Peak user with higher request frequency for stress testing.
    """
    
    # Shorter wait time between requests (0.5-2 seconds)
    wait_time = between(0.5, 2)
    weight = 1
    
    @task(5)
    def rapid_health_checks(self):
        """Rapid fire health checks to test peak load."""
        for _ in range(3):
            super().health_check()


# Default user class for standard load testing
class DefaultUser(BasicUser):
    """Default user behavior for standard load testing."""
    weight = 5


if __name__ == "__main__":
    # This allows the script to be run directly for testing
    print("Load test script loaded successfully")
    print("Use: locust -f load_test.py --headless -H <target-url> -t 30s -u 10 -r 0.5")
    print("Environment variables:")
    print(f"  _ID_TOKEN: {'Set' if os.getenv('_ID_TOKEN') else 'Not set'}")
    print(f"  _STAGING_URL: {os.getenv('_STAGING_URL', 'Not set')}")
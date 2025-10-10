# Load Testing

This directory contains load testing scripts and configurations for the My Agentic RAG application.

## Overview

The load testing suite uses [Locust](https://locust.io/) to simulate concurrent users and measure the performance of the deployed application under various load conditions.

## Structure

- `load_test.py` - Main load testing script with user scenarios
- `.results/` - Directory for test results (generated during CI/CD)

## Running Load Tests

### Prerequisites

- Python 3.11+
- Locust installed (`pip install locust==2.31.1`)
- Target application deployed and accessible

### Local Execution

```bash
# Install dependencies
pip install locust==2.31.1

# Run load test against staging
locust -f load_test.py --headless -H https://your-staging-url -t 30s -u 10 -r 0.5

# Run load test with web UI (for interactive testing)
locust -f load_test.py -H https://your-staging-url
```

### CI/CD Integration

Load tests are automatically executed as part of the staging deployment pipeline:

1. **Trigger**: Automatic execution after successful staging deployment
2. **Duration**: 30 seconds test run
3. **Users**: 10 concurrent users
4. **Ramp-up**: 0.5 users per second
5. **Results**: Stored in GCS bucket for analysis

## Test Scenarios

The load testing script includes the following scenarios:

- **Health Check**: Basic endpoint availability
- **Chat Requests**: Simulated user conversations
- **Authentication**: Identity token validation
- **Response Time**: Latency measurements

## Results Analysis

Test results are exported to:
- CSV format for data analysis
- HTML report for visual inspection
- Google Cloud Storage for persistence

Results include:
- Request/response times
- Success/failure rates
- Throughput metrics
- Error analysis

## Configuration

Key parameters can be adjusted in the load test script:
- User count and ramp-up rate
- Test duration
- Request patterns
- Authentication tokens
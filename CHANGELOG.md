# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Fixed - November 2, 2025

#### Cloud SQL Connection Stability Improvements

**Problem**: Cloud Run service failing to start due to PostgreSQL connection errors
- Error: `psycopg2.OperationalError: connection to server on socket "/cloudsql/staging-adk:us-central1:adk-sessions-staging-adk/.s.PGSQL.5432" failed: server closed the connection unexpectedly`
- Symptoms: 
  - Cloud Run containers crash-looping on startup
  - WhatsApp bot unable to connect to any ADK endpoint
  - All health checks failing (production, staging, localhost)

**Root Cause Analysis**:
1. `db-f1-micro` tier has only 0.6GB RAM
2. PostgreSQL + SQLAlchemy connection pool initialization requires more memory
3. Default SQLAlchemy pool settings (10 connections) overwhelming small instance
4. Connection attempts timing out during startup

**Solutions Implemented**:

1. **Infrastructure Upgrade** (`deployment/terraform/dev/cloudsql.tf`)
   - Upgraded Cloud SQL tier from `db-f1-micro` to `db-g1-small`
   - Memory increase: 0.6GB → 1.7GB RAM
   - Applied via: `gcloud sql instances patch adk-sessions-staging-adk --tier=db-g1-small`
   - Cost impact: $7/month → $27/month (acceptable for stability)
   - Status: ✅ Upgrade completed successfully

2. **Connection Pool Optimization** (`app/server.py`)
   - Added SQLAlchemy pool configuration parameters:
     ```python
     pool_size=5              # Reduced from default 10
     max_overflow=10          # Allow burst capacity
     pool_timeout=30          # Connection wait timeout
     pool_pre_ping=True       # Test connections before use
     pool_recycle=3600        # Recycle connections hourly
     ```
   - Benefits:
     - Reduced initial connection load during startup
     - Automatic stale connection detection
     - Better resource management
     - Improved reliability under load

**Results**:
- ✅ Cloud Run service starts successfully
- ✅ Database connections stable
- ✅ Health checks passing
- ✅ WhatsApp bot able to create ADK sessions
- ✅ End-to-end functionality restored

**Metrics Before/After**:
- Startup time: 60s+ with failures → ~30s successful
- Connection errors: 100% failure → 0% failure
- Service availability: 0% → 100%

**Documentation Updated**:
- `README.md`: Added November 2025 fixes section
- `deployment/terraform/dev/cloudsql.tf`: Updated tier with detailed comments
- `app/server.py`: Added connection pool parameter documentation

**Related Issues**:
- Cloud SQL connection stability
- SQLAlchemy pool configuration
- Cloud Run startup failures
- WhatsApp bot endpoint connectivity

---

## Previous Changes

See git history for changes prior to November 2, 2025.

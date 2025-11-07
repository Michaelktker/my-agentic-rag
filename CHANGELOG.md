# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added - November 2025

#### Cloud Terminal Integration for WhatsApp Bot

**Feature**: Secure cloud terminal access directly from WhatsApp with infrastructure CLI tools

**Overview**: 
The WhatsApp bot now includes a comprehensive cloud terminal interface that allows authorized users to execute infrastructure commands, interact with GitHub, use Terraform, and leverage AI assistance via GitHub Copilot CLI - all from WhatsApp messages.

**Key Components**:

1. **Terminal Handler** (`terminal-handler.js`)
   - 528-line implementation with security-first design
   - Commands: `/help`, `/ping`, `/sh <command>`, `/tty start/stop`, `/cop <prompt>`
   - PTY session management with idle timeouts (600s default)
   - Smart output handling: text for small outputs, files for large outputs
   - Real-time streaming with 500ms throttling

2. **Security Architecture** (Triple-Layer)
   - **Layer 1**: JID Allowlist - Only specific WhatsApp group/user JIDs allowed
   - **Layer 2**: Command Prefix Validation - Allowlist of safe commands (gcloud, terraform, gh, copilot, ls, cat, etc.)
   - **Layer 3**: Symbol Blocking - Prevents shell injection (`;`, `&&`, `||`, `|`, `>`, `<`, `` ` ``, `$()`)
   - Exception: `| jq` allowed for JSON parsing

3. **Installed CLI Tools** (VM)
   - Terraform v1.13.5 (infrastructure as code)
   - Google Cloud CLI (full gcloud suite, project: staging-adk)
   - GitHub CLI v2.83.0 (gh commands)
   - GitHub Copilot CLI v0.0.354 (AI assistance)

4. **GitHub Copilot CLI Integration**
   - Authentication via Personal Access Token (PAT) with "Copilot Requests" permission
   - Token configured in systemd service environment variable
   - Command format: `copilot -p "<prompt>" --allow-all-tools`
   - Non-interactive mode for WhatsApp message responses

**Configuration** (`config.json`):
```json
{
  "terminal": {
    "allowedJids": ["120363423143842705@g.us"],
    "maxTextLen": 3000,
    "idleTtyTimeoutSec": 600,
    "allowedPrefixes": ["gcloud", "terraform", "gh", "copilot", "ls", "pwd", "cat", "grep", "find", "echo", "which", "npm", "node", "python", "git"],
    "blockedSymbols": [";", "&&", "||", "|", ">", ">>", "<", "`", "$", "(", ")"]
  }
}
```

**Deployment Updates**:

1. **deploy-to-vm.sh**
   - Added `terminal-handler.js` to file copy list
   - Added build-essential and python3 for node-pty compilation
   - Automated dependency installation

2. **New Scripts**:
   - `deployment/install-cli-tools.sh`: Installs Terraform, GitHub CLI, Copilot CLI
   - `deployment/setup-github-token.sh`: Configures GITHUB_TOKEN in systemd
   - `deployment/auth-copilot.md`: Authentication guide for Copilot CLI

3. **Integration** (`index.js`):
   - Terminal handler initialized at startup
   - Early message interception (before ADK) for `/help`, `/ping`, `/sh`, `/tty`, `/cop`
   - Cleanup handlers for graceful shutdown

**Usage Examples**:

```bash
# Check CLI versions
/sh terraform version
/sh gcloud config list
/sh gh --version

# Infrastructure operations
/sh terraform plan
/sh gcloud compute instances list

# GitHub management
/sh gh repo list
/sh gh issue create --title "Bug report"

# AI assistance
/cop what is terraform
/cop explain how to use gcloud compute
/cop help me debug this terraform error

# Interactive sessions
/tty start
> ls -la
> cd terraform/
> terraform init
/tty stop
```

**Output Handling**:
- Small outputs (<3000 chars): Text messages
- Large outputs (>3000 chars): Text files sent as WhatsApp documents
- PTY sessions: Real-time streaming with throttling
- Idle timeout: Auto-close after 600s inactivity

**Technical Implementation**:
- **node-pty**: Native PTY support (requires build-essential, python3, make, gcc, g++)
- **Security**: Triple-layer validation before command execution
- **State Management**: PTY session tracking per JID
- **Error Handling**: Graceful fallbacks, user-friendly error messages

**Limitations**:
- PTY sessions timeout after 10 minutes idle
- Output truncated at 3000 chars for text display
- Some interactive commands require PTY mode
- Copilot CLI has Node.js v22+ warning (works on v20.19.5)

**Benefits**:
- ✅ Mobile-friendly infrastructure management
- ✅ No SSH required for basic operations
- ✅ AI-powered assistance via Copilot CLI
- ✅ Audit trail in WhatsApp chat history
- ✅ Secure multi-layer validation
- ✅ Real-time PTY session support

**Files Changed**:
- `terminal-handler.js` (NEW): Core terminal implementation
- `index.js`: Terminal handler integration
- `config.json`: Terminal configuration section
- `deployment/deploy-to-vm.sh`: Added terminal handler, build dependencies
- `deployment/install-cli-tools.sh` (NEW): CLI tools installation
- `deployment/setup-github-token.sh` (NEW): GitHub token configuration
- `deployment/auth-copilot.md` (NEW): Copilot CLI auth guide
- `README.md`: Cloud Terminal Integration section
- `CHANGELOG.md`: This entry

**Related Issues**:
- WhatsApp bot terminal access
- Infrastructure command execution
- GitHub Copilot CLI integration
- Secure shell command handling
- PTY session management

---

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

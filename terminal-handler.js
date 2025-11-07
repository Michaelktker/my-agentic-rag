/**
 * WhatsApp Cloud Terminal Handler
 * Provides secure terminal command execution capabilities
 * for gcloud, terraform, gh, copilot CLI tools
 */

const { spawn } = require('child_process');
const pty = require('node-pty');
const fs = require('fs/promises');
const path = require('path');
const os = require('os');
const crypto = require('crypto');

class TerminalHandler {
    constructor(logger, config) {
        this.logger = logger;
        this.config = config;
        
        // Terminal configuration
        this.ALLOWED_JIDS = config.terminal.allowedJids || [];
        this.MAX_TEXT_LEN = config.terminal.maxTextLen || 3000;
        this.IDLE_TTY_TIMEOUT_SEC = config.terminal.idleTtyTimeoutSec || 600;
        this.ALLOWED_PREFIXES = config.terminal.allowedPrefixes || [];
        this.BLOCKED_SYMBOLS = config.terminal.blockedSymbols || [];
        
        // Workspace directory - default to project root
        this.WORKSPACE_DIR = config.terminal.workspaceDir || '/workspaces/my-agentic-rag';
        
        // PTY session tracking: Map<jid, { pty, lastActivity, idleTimer }>
        this.ptySessions = new Map();
        
        this.logger.info('🖥️  Terminal Handler initialized');
        this.logger.info(`📋 Allowed JIDs: ${this.ALLOWED_JIDS.join(', ')}`);
        this.logger.info(`📏 Max text length: ${this.MAX_TEXT_LEN} chars`);
        this.logger.info(`⏱️  Idle TTY timeout: ${this.IDLE_TTY_TIMEOUT_SEC}s`);
        this.logger.info(`📂 Workspace directory: ${this.WORKSPACE_DIR}`);
    }

    /**
     * Check if JID is allowed to use terminal commands
     */
    isAllowedJid(jid) {
        return this.ALLOWED_JIDS.includes(jid);
    }

    /**
     * Check if command prefix is allowed
     */
    prefixAllowed(command) {
        const trimmed = command.trim();
        if (!trimmed) return false;
        
        // Extract first word
        const firstWord = trimmed.split(/\s+/)[0];
        
        // Check if it starts with any allowed prefix
        return this.ALLOWED_PREFIXES.some(prefix => firstWord === prefix);
    }

    /**
     * Sanitize command to prevent dangerous operations
     */
    sanitize(command) {
        // Check for blocked symbols
        for (const symbol of this.BLOCKED_SYMBOLS) {
            if (command.includes(symbol)) {
                // Exception: allow "| jq" only
                if (symbol === '|' && command.match(/\|\s*jq(\s|$)/)) {
                    continue;
                }
                return {
                    valid: false,
                    reason: `Blocked symbol detected: ${symbol}`
                };
            }
        }
        
        // Check for backticks
        if (command.includes('`')) {
            return {
                valid: false,
                reason: 'Backticks not allowed'
            };
        }
        
        // Check prefix
        if (!this.prefixAllowed(command)) {
            return {
                valid: false,
                reason: `Command must start with one of: ${this.ALLOWED_PREFIXES.join(', ')}`
            };
        }
        
        return { valid: true };
    }

    /**
     * Send output to WhatsApp - handles text vs file based on size
     */
    async sendOutput(sock, jid, output, commandInfo = {}) {
        try {
            if (!output || output.length === 0) {
                await sock.sendMessage(jid, { text: '(no output)' });
                return;
            }

            // If output fits in text message
            if (output.length <= this.MAX_TEXT_LEN) {
                await sock.sendMessage(jid, { text: output });
                return;
            }

            // Output too large - save to file and send as document
            const timestamp = Date.now();
            const filename = `output-${timestamp}.txt`;
            const filepath = path.join(os.tmpdir(), filename);
            
            await fs.writeFile(filepath, output, 'utf8');
            
            this.logger.info(`📄 Output too large (${output.length} chars), sending as file: ${filename}`);
            
            // Send file
            const fileBuffer = await fs.readFile(filepath);
            await sock.sendMessage(jid, {
                document: fileBuffer,
                fileName: filename,
                mimetype: 'text/plain',
                caption: commandInfo.command ? `Output from: ${commandInfo.command}` : 'Command output'
            });
            
            // Clean up temp file
            await fs.unlink(filepath).catch(err => 
                this.logger.warn(`Failed to delete temp file ${filepath}:`, err)
            );
            
        } catch (error) {
            this.logger.error('Error sending output:', error);
            await sock.sendMessage(jid, { text: `Error sending output: ${error.message}` });
        }
    }

    /**
     * Execute one-shot command (for /sh)
     */
    async execOnce(sock, jid, command) {
        const startTime = Date.now();
        
        this.logger.info(`🔧 Executing command from ${jid}: ${command}`);
        
        // Sanitize
        const sanitizeResult = this.sanitize(command);
        if (!sanitizeResult.valid) {
            this.logger.warn(`🚫 Command blocked: ${sanitizeResult.reason}`);
            await sock.sendMessage(jid, { text: `❌ Blocked: ${sanitizeResult.reason}` });
            return;
        }

        return new Promise((resolve) => {
            let stdout = '';
            let stderr = '';
            
            // Use shell to execute command in workspace directory
            const child = spawn('bash', ['-c', command], {
                cwd: this.WORKSPACE_DIR,
                env: process.env,
                shell: false // we're already using bash
            });

            child.stdout.on('data', (data) => {
                stdout += data.toString();
            });

            child.stderr.on('data', (data) => {
                stderr += data.toString();
            });

            child.on('error', async (error) => {
                const duration = Date.now() - startTime;
                this.logger.error(`❌ Command error (${duration}ms):`, error);
                
                await this.sendOutput(sock, jid, `Error: ${error.message}`, { command });
                resolve();
            });

            child.on('close', async (code) => {
                const duration = Date.now() - startTime;
                const output = stdout + stderr;
                
                // Log execution details
                this.logger.info(`✅ Command completed:`, {
                    command,
                    exitCode: code,
                    duration: `${duration}ms`,
                    outputSize: `${output.length} chars`
                });
                
                // Prepare output with exit code
                let finalOutput = output;
                if (code !== 0) {
                    finalOutput = `❌ Exit code: ${code}\n\n${output}`;
                } else {
                    finalOutput = `✅ Exit code: ${code}\n\n${output}`;
                }
                
                await this.sendOutput(sock, jid, finalOutput, { command, exitCode: code, duration });
                resolve();
            });
        });
    }

    /**
     * Start PTY session for interactive terminal
     */
    async startPty(sock, jid) {
        // Check if already has PTY
        if (this.ptySessions.has(jid)) {
            this.logger.warn(`⚠️  PTY session already exists for ${jid}`);
            await sock.sendMessage(jid, { text: '⚠️  Terminal session already active. Use /tty stop first.' });
            return;
        }

        try {
            this.logger.info(`🚀 Starting PTY session for ${jid}`);
            
            // Create PTY in workspace directory
            const ptyProcess = pty.spawn('bash', [], {
                name: 'xterm-256color',
                cols: 80,
                rows: 24,
                cwd: this.WORKSPACE_DIR,
                env: process.env
            });

            // Buffer for aggregating output
            let outputBuffer = '';
            let throttleTimer = null;

            // Handle PTY output
            ptyProcess.onData((data) => {
                outputBuffer += data;
                
                // Throttle output to avoid spam
                if (throttleTimer) clearTimeout(throttleTimer);
                
                throttleTimer = setTimeout(async () => {
                    if (outputBuffer.length > 0) {
                        // Strip ANSI escape codes for WhatsApp
                        const cleanOutput = outputBuffer.replace(/\x1b\[[0-9;]*m/g, '');
                        await this.sendOutput(sock, jid, cleanOutput, { pty: true });
                        outputBuffer = '';
                    }
                }, 500); // 500ms throttle
                
                // Update last activity
                const session = this.ptySessions.get(jid);
                if (session) {
                    session.lastActivity = Date.now();
                    this.resetIdleTimer(sock, jid);
                }
            });

            // Handle PTY exit
            ptyProcess.onExit(({ exitCode, signal }) => {
                this.logger.info(`PTY exited for ${jid}: code=${exitCode}, signal=${signal}`);
                this.stopPty(sock, jid, `Terminal exited: code=${exitCode}, signal=${signal}`);
            });

            // Store session
            const session = {
                pty: ptyProcess,
                lastActivity: Date.now(),
                idleTimer: null
            };
            this.ptySessions.set(jid, session);
            
            // Set up idle timeout
            this.resetIdleTimer(sock, jid);

            await sock.sendMessage(jid, { 
                text: `✅ Terminal session started\nType commands directly (no / prefix)\nUse /tty stop to end session` 
            });
            
        } catch (error) {
            this.logger.error('Error starting PTY:', error);
            await sock.sendMessage(jid, { text: `❌ Failed to start terminal: ${error.message}` });
        }
    }

    /**
     * Stop PTY session
     */
    async stopPty(sock, jid, reason = 'User requested') {
        const session = this.ptySessions.get(jid);
        if (!session) {
            this.logger.warn(`No PTY session found for ${jid}`);
            await sock.sendMessage(jid, { text: '⚠️  No terminal session active.' });
            return;
        }

        try {
            this.logger.info(`🛑 Stopping PTY session for ${jid}: ${reason}`);
            
            // Clear idle timer
            if (session.idleTimer) {
                clearTimeout(session.idleTimer);
            }
            
            // Kill PTY
            session.pty.kill();
            
            // Remove from map
            this.ptySessions.delete(jid);
            
            await sock.sendMessage(jid, { text: `✅ Terminal session ended: ${reason}` });
            
        } catch (error) {
            this.logger.error('Error stopping PTY:', error);
            await sock.sendMessage(jid, { text: `❌ Error stopping terminal: ${error.message}` });
        }
    }

    /**
     * Reset idle timeout for PTY session
     */
    resetIdleTimer(sock, jid) {
        const session = this.ptySessions.get(jid);
        if (!session) return;

        // Clear existing timer
        if (session.idleTimer) {
            clearTimeout(session.idleTimer);
        }

        // Set new timer
        session.idleTimer = setTimeout(async () => {
            this.logger.info(`⏱️  PTY session idle timeout for ${jid}`);
            await this.stopPty(sock, jid, `Idle timeout (${this.IDLE_TTY_TIMEOUT_SEC}s)`);
        }, this.IDLE_TTY_TIMEOUT_SEC * 1000);
    }

    /**
     * Send data to PTY session
     */
    async sendToPty(sock, jid, data) {
        const session = this.ptySessions.get(jid);
        if (!session) {
            this.logger.warn(`No PTY session for ${jid}, ignoring input`);
            return;
        }

        try {
            session.pty.write(data + '\r'); // Add carriage return
            session.lastActivity = Date.now();
            this.resetIdleTimer(sock, jid);
        } catch (error) {
            this.logger.error('Error writing to PTY:', error);
            await sock.sendMessage(jid, { text: `❌ Error sending to terminal: ${error.message}` });
        }
    }

    /**
     * Execute Copilot CLI command
     */
    async executeCopilot(sock, jid, args) {
        // Check if it's a direct command (like --version, --help)
        const isDirect = args.startsWith('--') || args.startsWith('-');
        
        // For prompt mode, use -p flag and allow all tools for non-interactive use
        const command = isDirect 
            ? `copilot ${args}`
            : `copilot -p "${args.replace(/"/g, '\\"')}" --allow-all-tools`;
        
        this.logger.info(`🤖 Executing Copilot CLI from ${jid}: ${command}`);
        
        await this.execOnce(sock, jid, command);
    }

    /**
     * Handle terminal command routing
     */
    async handleTerminalMessage(sock, message) {
        const jid = message.key.remoteJid;
        
        // Check if JID is allowed
        if (!this.isAllowedJid(jid)) {
            this.logger.debug(`Ignoring terminal command from non-allowed JID: ${jid}`);
            return false; // Not handled
        }

        // Extract message text
        const text = message.message?.conversation || 
                    message.message?.extendedTextMessage?.text || 
                    '';

        if (!text) return false;

        const trimmed = text.trim();

        // Route commands
        if (trimmed === '/help') {
            await this.handleHelp(sock, jid);
            return true;
        }

        if (trimmed === '/ping') {
            await this.handlePing(sock, jid);
            return true;
        }

        if (trimmed.startsWith('/sh ')) {
            const command = trimmed.substring(4);
            await this.execOnce(sock, jid, command);
            return true;
        }

        if (trimmed === '/tty start') {
            await this.startPty(sock, jid);
            return true;
        }

        if (trimmed === '/tty stop') {
            await this.stopPty(sock, jid);
            return true;
        }

        if (trimmed.startsWith('/cop ')) {
            const args = trimmed.substring(5).trim();
            if (args) {
                await this.executeCopilot(sock, jid, args);
            } else {
                await sock.sendMessage(jid, { 
                    text: '❌ Usage: /cop <prompt or command>\nExamples:\n  /cop --version\n  /cop what is terraform\n  /cop explain this code' 
                });
            }
            return true;
        }

        // If PTY session active, send input to it
        const session = this.ptySessions.get(jid);
        if (session) {
            await this.sendToPty(sock, jid, text);
            return true;
        }

        return false; // Not a terminal command
    }

    /**
     * Handle /help command
     */
    async handleHelp(sock, jid) {
        const help = `
🖥️  **WhatsApp Cloud Terminal**

**Available Commands:**

📋 **Information:**
/help - Show this help message
/ping - Check terminal status

🔧 **Command Execution:**
/sh <command> - Execute one-shot command
  Examples:
  • /sh gcloud --version
  • /sh terraform version
  • /sh gh repo list
  • /sh ls -la

🖥️  **Interactive Terminal:**
/tty start - Start interactive PTY shell
/tty stop - Stop PTY session

🤖 **Copilot CLI:**
/cop <prompt or command> - Use Copilot CLI
  Examples:
  • /cop --version (check version)
  • /cop --help (show help)
  • /cop what is terraform (ask question)
  • /cop explain this code (get explanation)
  • /cop help me debug this error (get assistance)

**Allowed Commands:**
${this.ALLOWED_PREFIXES.join(', ')}

**Blocked Symbols:**
${this.BLOCKED_SYMBOLS.join(' ')}
(Exception: '| jq' is allowed)

**Notes:**
• Only works in allowed groups
• PTY sessions auto-timeout after ${this.IDLE_TTY_TIMEOUT_SEC}s
• Large outputs sent as text files
• All commands execute in: ${this.WORKSPACE_DIR}
        `.trim();

        await sock.sendMessage(jid, { text: help });
    }

    /**
     * Handle /ping command
     */
    async handlePing(sock, jid) {
        const project = process.env.PROJECT_ID || this.config.gcs.projectId || 'unknown';
        const region = process.env.REGION || 'us-central1';
        
        const response = `
🏓 **Pong!**

📍 **Project:** ${project}
🌍 **Region:** ${region}
⚙️  **Node:** ${process.version}
🖥️  **Platform:** ${os.platform()} ${os.arch()}
📂 **Workspace:** ${this.WORKSPACE_DIR}
🔧 **Terminal:** Ready

✅ Terminal access enabled for this group
        `.trim();

        await sock.sendMessage(jid, { text: response });
    }

    /**
     * Cleanup all PTY sessions (for shutdown)
     */
    async cleanup(sock) {
        this.logger.info(`🧹 Cleaning up ${this.ptySessions.size} PTY sessions`);
        
        for (const [jid, session] of this.ptySessions.entries()) {
            try {
                if (session.idleTimer) {
                    clearTimeout(session.idleTimer);
                }
                session.pty.kill();
                this.logger.info(`Killed PTY for ${jid}`);
            } catch (error) {
                this.logger.error(`Error killing PTY for ${jid}:`, error);
            }
        }
        
        this.ptySessions.clear();
    }
}

module.exports = TerminalHandler;

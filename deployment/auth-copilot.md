# Authenticating GitHub Copilot CLI on VM

## Steps to Authenticate:

### 1. SSH into the VM
```bash
source /tmp/google-cloud-sdk/google-cloud-sdk/path.bash.inc && \
gcloud compute ssh whatsapp-bot --project=staging-adk --zone=us-central1-a
```

### 2. Start Copilot CLI
```bash
copilot
```

### 3. Use the `/login` command
When Copilot CLI starts, type:
```
/login
```

### 4. Follow the authentication prompts
Copilot will display:
- A device code (e.g., `ABCD-1234`)
- Instructions to visit: https://github.com/login/device

### 5. Complete authentication in browser
1. Open https://github.com/login/device in your browser
2. Enter the device code shown in the terminal
3. Click "Authorize GitHub Copilot CLI"
4. Return to the terminal - authentication should be complete!

### 6. Test Copilot
Try a simple command:
```
what is terraform
```

### 7. Exit and verify
Type `/exit` to close the interactive session, then test via WhatsApp!

## Alternative: Set GITHUB_TOKEN Environment Variable

If you prefer not to use interactive auth, you can set a GitHub token:

```bash
# Get your GitHub token from: https://github.com/settings/tokens
# Required scope: copilot

# Set it for the bot service
sudo mkdir -p /etc/systemd/system/whatsapp-bot.service.d/
sudo tee /etc/systemd/system/whatsapp-bot.service.d/github-token.conf > /dev/null <<EOF
[Service]
Environment="GITHUB_TOKEN=your_token_here"
EOF

sudo systemctl daemon-reload
sudo systemctl restart whatsapp-bot
```

## Note
The VM is running as a service account, so interactive authentication is the recommended approach for Copilot CLI.

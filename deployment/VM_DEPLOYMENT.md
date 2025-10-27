# WhatsApp Bot - VM Deployment Guide

This guide explains how to deploy the WhatsApp bot on Google Compute Engine with systemd service management.

## Prerequisites

- Google Cloud SDK (`gcloud`) installed and configured
- Access to the `staging-adk` or `production-adk` project
- GitHub repository access

## Deployment Steps

### 1. Create the VM (if not already created)

```bash
gcloud compute instances create whatsapp-bot \
  --project=staging-adk \
  --zone=us-central1-a \
  --machine-type=e2-medium \
  --image-family=debian-12 \
  --image-project=debian-cloud \
  --scopes=cloud-platform \
  --tags=whatsapp-bot
```

### 2. Copy the setup script to the VM

```bash
gcloud compute scp deployment/vm-setup.sh whatsapp-bot:~/ \
  --project=staging-adk \
  --zone=us-central1-a
```

### 3. SSH into the VM

```bash
gcloud compute ssh whatsapp-bot \
  --project=staging-adk \
  --zone=us-central1-a
```

### 4. Run the setup script

Once connected via SSH:

```bash
chmod +x ~/vm-setup.sh
./vm-setup.sh
```

This script will:
- ✅ Install Node.js 18
- ✅ Install Git
- ✅ Clone your repository
- ✅ Install npm dependencies
- ✅ Create a systemd service
- ✅ Enable and start the WhatsApp bot service

### 5. Verify the deployment

Check the service status:

```bash
sudo systemctl status whatsapp-bot
```

View live logs:

```bash
sudo journalctl -u whatsapp-bot -f
```

## Service Management Commands

### Check Status
```bash
sudo systemctl status whatsapp-bot
```

### Start the Bot
```bash
sudo systemctl start whatsapp-bot
```

### Stop the Bot
```bash
sudo systemctl stop whatsapp-bot
```

### Restart the Bot
```bash
sudo systemctl restart whatsapp-bot
```

### View Logs
```bash
# Live logs (follow mode)
sudo journalctl -u whatsapp-bot -f

# Last 100 lines
sudo journalctl -u whatsapp-bot -n 100

# Logs from today
sudo journalctl -u whatsapp-bot --since today
```

### Disable Auto-Start
```bash
sudo systemctl stop whatsapp-bot
sudo systemctl disable whatsapp-bot
```

### Enable Auto-Start
```bash
sudo systemctl enable whatsapp-bot
```

## Updating the Application

When you need to update the code:

```bash
# SSH into the VM
gcloud compute ssh whatsapp-bot --project=staging-adk --zone=us-central1-a

# Pull latest changes
cd ~/my-agentic-rag
git pull

# Install any new dependencies
npm install --production

# Restart the service
sudo systemctl restart whatsapp-bot

# Check if it's running
sudo systemctl status whatsapp-bot
```

## Troubleshooting

### Bot Not Starting

1. Check the logs:
   ```bash
   sudo journalctl -u whatsapp-bot -n 50
   ```

2. Check if the process is running:
   ```bash
   ps aux | grep node
   ```

3. Manually run to see errors:
   ```bash
   cd ~/my-agentic-rag
   node index.js
   ```

### WhatsApp Connection Issues

The bot stores session data in Google Cloud Storage. If you see connection issues:

1. Check GCS permissions:
   ```bash
   gcloud auth application-default login
   ```

2. Verify the bucket exists and has the session files

3. Restart the bot:
   ```bash
   sudo systemctl restart whatsapp-bot
   ```

### High Memory Usage

If the VM runs out of memory:

1. Check current memory usage:
   ```bash
   free -h
   htop
   ```

2. Upgrade to a larger machine type:
   ```bash
   # Stop the bot
   sudo systemctl stop whatsapp-bot
   
   # From your local machine:
   gcloud compute instances stop whatsapp-bot --project=staging-adk --zone=us-central1-a
   
   gcloud compute instances set-machine-type whatsapp-bot \
     --machine-type=e2-standard-2 \
     --project=staging-adk \
     --zone=us-central1-a
   
   gcloud compute instances start whatsapp-bot --project=staging-adk --zone=us-central1-a
   
   # SSH back in and start the bot
   sudo systemctl start whatsapp-bot
   ```

## Complete Removal

To completely remove the deployment:

```bash
# SSH into the VM
gcloud compute ssh whatsapp-bot --project=staging-adk --zone=us-central1-a

# Stop and disable the service
sudo systemctl stop whatsapp-bot
sudo systemctl disable whatsapp-bot
sudo rm /etc/systemd/system/whatsapp-bot.service
sudo systemctl daemon-reload

# Delete the application
rm -rf ~/my-agentic-rag

# Exit the VM
exit

# Delete the VM (from your local machine)
gcloud compute instances delete whatsapp-bot \
  --project=staging-adk \
  --zone=us-central1-a
```

## Cost Optimization

### Stop the VM when not in use
```bash
gcloud compute instances stop whatsapp-bot \
  --project=staging-adk \
  --zone=us-central1-a
```

### Start the VM
```bash
gcloud compute instances start whatsapp-bot \
  --project=staging-adk \
  --zone=us-central1-a
```

**Note**: The bot will automatically start when the VM boots up thanks to the systemd service.

## Production Deployment

For production deployment, simply change the project:

```bash
gcloud compute instances create whatsapp-bot \
  --project=production-adk \
  --zone=us-central1-a \
  --machine-type=e2-standard-2 \
  --image-family=debian-12 \
  --image-project=debian-cloud \
  --scopes=cloud-platform \
  --tags=whatsapp-bot
```

Then follow the same setup steps with `--project=production-adk`.

## Monitoring

Set up monitoring and alerts in Google Cloud Console:

1. Go to **Monitoring > Dashboards**
2. Create a new dashboard for the VM
3. Add metrics for:
   - CPU utilization
   - Memory usage
   - Disk I/O
   - Network traffic

## Security Best Practices

1. **Firewall**: The bot doesn't need incoming connections, so no firewall rules needed
2. **Service Account**: VM uses default compute service account with cloud-platform scope
3. **Updates**: Regularly update the VM and dependencies
4. **SSH Keys**: Use gcloud SSH instead of managing SSH keys manually

## Support

For issues, check:
- VM logs: `sudo journalctl -u whatsapp-bot -f`
- WhatsApp connection status in the logs
- ADK endpoint connectivity
- GCS session storage access

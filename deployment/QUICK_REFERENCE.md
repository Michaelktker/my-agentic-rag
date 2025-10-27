# WhatsApp Bot - Quick Command Reference

## Most Used Commands

### View Live Logs
```bash
gcloud compute ssh whatsapp-bot --project=staging-adk --zone=us-central1-a --command='sudo journalctl -u whatsapp-bot -f'
```

### Restart Bot
```bash
gcloud compute ssh whatsapp-bot --project=staging-adk --zone=us-central1-a --command='sudo systemctl restart whatsapp-bot'
```

### Check Status
```bash
gcloud compute ssh whatsapp-bot --project=staging-adk --zone=us-central1-a --command='sudo systemctl status whatsapp-bot'
```

### Deploy Updates
```bash
./deployment/deploy-to-vm.sh
```

### Stop VM (save costs)
```bash
gcloud compute instances stop whatsapp-bot --project=staging-adk --zone=us-central1-a
```

### Start VM
```bash
gcloud compute instances start whatsapp-bot --project=staging-adk --zone=us-central1-a
```

### SSH into VM
```bash
gcloud compute ssh whatsapp-bot --project=staging-adk --zone=us-central1-a
```

---

## Files Created

- `deployment/deploy-to-vm.sh` - Main deployment script
- `deployment/vm-setup.sh` - Initial VM setup script
- `deployment/VM_DEPLOYMENT.md` - Detailed deployment guide
- `deployment/DEPLOYMENT_SUMMARY.md` - Deployment status and commands
- `deployment/QUICK_REFERENCE.md` - This file

---

## What Got Deployed

✅ Node.js 20.19.5 installed on VM
✅ Application files copied to `/home/codespace/whatsapp-bot/`
✅ Dependencies installed (260 packages)
✅ Systemd service created and enabled
✅ Bot running and auto-starts on reboot
✅ Session data stored in Google Cloud Storage

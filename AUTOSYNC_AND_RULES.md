# Auto-Sync and Rule Management Features

## Auto-Sync Configuration

Each agent now has a configurable auto-sync interval that determines how often its firewall configuration should be automatically synchronized with the database.

### Configuration Fields

- **sync_interval_seconds**: Interval in seconds for automatic firewall configuration sync (default: 60 seconds, set to 0 to disable)
- **last_sync**: Timestamp of the last successful sync

### Running the Auto-Sync Daemon

To enable automatic synchronization of agent configurations, run the management command:

```bash
# One-time sync of all agents
python manage.py sync_agents

# Run as a daemon (continuous loop)
python manage.py sync_agents --daemon

# Run as daemon with custom check interval (default is 10 seconds)
python manage.py sync_agents --daemon --interval 5
```

### Recommended Setup

For production, run the sync daemon as a systemd service or via cron:

**Option 1: Systemd Service**

Create `/etc/systemd/system/firewall-sync.service`:

```ini
[Unit]
Description=Firewall Central Auto-Sync Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/firewall-central/web_ui
ExecStart=/path/to/venv/bin/python manage.py sync_agents --daemon
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then enable and start:
```bash
sudo systemctl enable firewall-sync
sudo systemctl start firewall-sync
```

**Option 2: Cron Job**

Add to crontab:
```bash
# Sync agents every minute
* * * * * cd /path/to/firewall-central/web_ui && /path/to/venv/bin/python manage.py sync_agents
```

## Firewall Rule Management

### Adding Services to Zones

1. Navigate to the agent detail page
2. Find the zone you want to modify
3. Click the **+** button next to "Services"
4. Enter the service name (e.g., `http`, `https`, `ssh`)
5. The service will be added to both the agent and the database

### Removing Services from Zones

1. Find the service badge in the zone details
2. Click the **×** icon on the service badge
3. Confirm the removal
4. The service will be removed from both the agent and the database

### Adding Ports to Zones

1. Navigate to the agent detail page
2. Find the zone you want to modify
3. Click the **+** button next to "Ports"
4. Enter the port number (e.g., `8080` or `8080-8090` for ranges)
5. Enter the protocol (`tcp` or `udp`)
6. The port will be opened on both the agent and stored in the database

### Removing Ports from Zones

1. Find the port badge in the zone details
2. Click the **×** icon on the port badge
3. Confirm the removal
4. The port will be closed on both the agent and removed from the database

## API Endpoints

### Add Service
```
POST /agents/<agent_id>/zone/<zone_id>/service/add/
Body: {"service": "http"}
```

### Remove Service
```
POST /agents/<agent_id>/zone/<zone_id>/service/<service>/remove/
```

### Add Port
```
POST /agents/<agent_id>/zone/<zone_id>/port/add/
Body: {"port": "8080", "protocol": "tcp"}
```

### Remove Port
```
POST /agents/<agent_id>/zone/<zone_id>/port/remove/
Body: {"port_spec": "8080/tcp"}
```

### Add Rule (Generic)
```
POST /agents/<agent_id>/rule/add/
Body: {
    "zone_id": "<zone_id>",
    "rule_type": "service|port|rich|forward",
    "service": "http",  // for service type
    "port": "8080",     // for port type
    "protocol": "tcp",  // for port type
    "enabled": true,
    "permanent": true
}
```

### Delete Rule
```
POST /agents/<agent_id>/rule/<rule_id>/delete/
```

## Features

### Auto-Sync Features
- ✅ Configurable per-agent sync intervals
- ✅ Background daemon for continuous synchronization
- ✅ Last sync timestamp tracking
- ✅ Only syncs agents with enabled intervals (> 0)
- ✅ Only syncs agents with 'online' or 'approved' status
- ✅ Automatic connection management

### Rule Management Features
- ✅ Add/remove services from zones
- ✅ Add/remove ports from zones
- ✅ Real-time application to agents
- ✅ Database synchronization
- ✅ User-friendly UI with +/× buttons
- ✅ Confirmation dialogs
- ✅ Success/error feedback
- ✅ Support for SSH, HTTP, and agent-to-server connections

## Notes

- All changes are applied to both the agent (via firewall-cmd) and the database
- Changes are permanent by default
- Failed operations will show detailed error messages
- The sync daemon will skip agents that haven't reached their sync interval yet
- Manual sync via "Sync Firewall Config" button always works regardless of interval

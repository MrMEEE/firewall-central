# Firewalld Central Management - Agents

This directory contains the agent implementations for the Firewalld Central Management system. Agents are components that run on target systems to manage firewalld configurations.

## Agent Types

The system supports three types of agent connections:

### 1. Agent-to-Server Connection (`firewalld_agent.py`)

The agent connects to the management server periodically to check for commands.

**Features:**
- Automatic registration with the server
- Periodic check-ins for pending commands
- Executes firewalld commands locally
- Reports results back to the server
- Handles network interruptions gracefully

**Usage:**
```bash
# Install dependencies
pip install -r requirements.txt

# Run the agent
python firewalld_agent.py --server-url http://192.168.1.100:8001 --hostname myhost --ip 192.168.1.50
```

**Configuration:**
- `--server-url`: URL of the management server
- `--hostname`: Agent hostname (default: system hostname)
- `--ip`: Agent IP address (default: auto-detected)

### 2. Server-to-Agent Connection (`http_agent.py`)

The agent runs an HTTP server that listens for connections from the management server.

**Features:**
- HTTP API for command execution
- Health check endpoint
- Optional API key authentication
- Real-time command execution
- JSON-based communication

**Usage:**
```bash
# Run the HTTP agent
python http_agent.py --port 8444 --api-key my-secret-key
```

**Configuration:**
- `--port`: Port to listen on (default: 8444)
- `--host`: Host to bind to (default: 0.0.0.0)
- `--api-key`: API key for authentication (optional)

**Endpoints:**
- `GET /health` - Health check and system information
- `POST /execute` - Execute firewalld commands

### 3. SSH Connection

Uses standard SSH to connect to remote systems and execute firewalld commands.

**Features:**
- Uses existing SSH infrastructure
- Supports key-based and password authentication
- Direct command execution via SSH
- No additional software required on target systems

**Configuration:**
Configure SSH connection details in the web interface:
- SSH username
- SSH private key path or password
- Target IP address and port

## Supported Commands

All agent types support the following firewalld commands:

- `get_status` - Get firewall status
- `get_zones` - Get all firewall zones and their configurations
- `get_rules` - Get all firewall rules across zones
- `add_service` - Add a service to a zone
- `remove_service` - Remove a service from a zone

## Security Considerations

### Agent-to-Server
- Agents receive unique API keys during registration
- All communication uses HTTPS in production
- Commands are queued and executed asynchronously

### Server-to-Agent (HTTP)
- Optional API key authentication
- Bind to specific interfaces for security
- Use firewall rules to restrict access
- Enable HTTPS for production deployments

### SSH
- Use key-based authentication when possible
- Restrict SSH access using firewall rules
- Use dedicated service accounts with minimal privileges
- Consider using SSH certificates for large deployments

## Installation

### Agent Dependencies
```bash
pip install requests>=2.28.0
```

### System Requirements
- Python 3.7+
- firewalld installed and configured
- systemctl access (for status checks)
- Network connectivity to management server

### Firewall Configuration
Ensure the following ports are accessible:

**For Agent-to-Server:**
- Outbound HTTPS (443) or HTTP (8001) to management server

**For Server-to-Agent:**
- Inbound TCP on agent port (default 8444)

**For SSH:**
- Inbound TCP 22 (or custom SSH port)

## Production Deployment

### Systemd Service (Agent-to-Server)
```ini
[Unit]
Description=Firewalld Central Management Agent
After=network.target firewalld.service

[Service]
Type=simple
User=firewalld-agent
ExecStart=/usr/local/bin/firewalld_agent.py --server-url https://firewall-mgmt.example.com
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```

### Systemd Service (HTTP Agent)
```ini
[Unit]
Description=Firewalld HTTP Agent
After=network.target firewalld.service

[Service]
Type=simple
User=firewalld-agent
ExecStart=/usr/local/bin/http_agent.py --port 8444 --api-key "${API_KEY}"
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Docker Deployment
```dockerfile
FROM python:3.9-slim

RUN apt-get update && apt-get install -y \
    firewalld \
    systemctl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY *.py /app/
WORKDIR /app

# For agent-to-server
ENTRYPOINT ["python", "firewalld_agent.py"]

# For server-to-agent
# EXPOSE 8444
# ENTRYPOINT ["python", "http_agent.py"]
```

## Troubleshooting

### Common Issues

**Agent can't connect to server:**
- Check network connectivity
- Verify server URL and port
- Check firewall rules on both ends
- Verify SSL/TLS configuration

**Commands fail to execute:**
- Ensure firewalld is running: `systemctl status firewalld`
- Check user permissions for firewall-cmd
- Verify firewalld service is enabled
- Check system logs: `journalctl -u firewalld`

**SSH connection fails:**
- Verify SSH service is running
- Check SSH key permissions (600 for private keys)
- Test manual SSH connection
- Verify SSH user has sudo/firewall permissions

### Debugging

Enable debug logging by modifying the agents:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Check firewalld logs:
```bash
journalctl -u firewalld -f
```

Test firewall commands manually:
```bash
firewall-cmd --state
firewall-cmd --get-zones
firewall-cmd --list-all
```

## Contributing

When adding new commands or features:

1. Implement the command in all agent types
2. Add appropriate error handling
3. Update the command documentation
4. Test with different firewalld configurations
5. Update the web interface accordingly

## License

This project is licensed under the MIT License - see the LICENSE file for details.
# Firewalld Central Management System

A comprehensive centralized management system for firewalld with agent-based architecture, secure communication, and intuitive web interface.

## Architecture Overview

The system consists of three main components:

### 1. Agent (`firewalld_agent/`)
- Runs on servers that need firewall management
- Supports both pull and push modes
- Handles all firewalld operations including rich rules
- Secure communication with self-signed certificates

### 2. API Server (`api_server/`)
- Central management server with RESTful API
- Agent registration and authentication
- Certificate management
- Real-time communication with agents

### 3. Web UI (`web_ui/`)
- Django-based web interface
- Whiteboard-style visual network management
- User management with role-based access control
- Real-time status monitoring

## Features

- **Visual Network Management**: Drag-and-drop interface for defining network connections
- **Comprehensive Firewall Control**: Support for all firewalld features including rich rules and masquerade
- **Secure Communication**: Self-signed certificate-based authentication between components
- **Role-Based Access**: Granular user permissions for different server groups
- **Real-time Updates**: Live status monitoring and configuration synchronization
- **Dual Operation Modes**: Support for both agent-initiated (pull) and server-initiated (push) communication

## Quick Start

### Prerequisites
- Python 3.9+
- Redis server
- PostgreSQL database
- Root/sudo access on managed servers

### Installation

1. Clone and setup the project:
```bash
git clone <repository-url>
cd firewalld-central
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. Setup environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Initialize the database:
```bash
cd web_ui
python manage.py migrate
python manage.py createsuperuser
```

4. Start the services:
```bash
# Terminal 1: Start Redis
redis-server

# Terminal 2: Start API Server
cd api_server
python main.py

# Terminal 3: Start Web UI
cd web_ui
python manage.py runserver

# Terminal 4: Start Celery (for background tasks)
cd web_ui
celery -A firewalld_central worker --loglevel=info
```

### Agent Installation

On each server to be managed:

1. Copy the agent files:
```bash
scp -r firewalld_agent/ root@target-server:/opt/firewalld-agent/
```

2. Install dependencies:
```bash
ssh root@target-server
cd /opt/firewalld-agent
pip install -r requirements.txt
```

3. Configure and start the agent:
```bash
# Edit agent configuration
cp config.yaml.example config.yaml
# Configure server URL and mode (pull/push)

# Start the agent
python agent.py
```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/firewalld_central

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key
API_SECRET_KEY=your-api-secret-key

# API Server
API_HOST=0.0.0.0
API_PORT=8000

# Web UI
WEB_HOST=0.0.0.0
WEB_PORT=8080

# SSL/TLS
SSL_CERT_PATH=./certs/server.crt
SSL_KEY_PATH=./certs/server.key
CA_CERT_PATH=./certs/ca.crt
```

### Agent Configuration

Each agent uses a `config.yaml` file:

```yaml
server:
  url: "https://your-central-server:8000"
  mode: "pull"  # or "push"
  poll_interval: 30

security:
  cert_path: "./certs/agent.crt"
  key_path: "./certs/agent.key"
  ca_cert_path: "./certs/ca.crt"

logging:
  level: "INFO"
  file: "/var/log/firewalld-agent.log"
```

## Development

### Running Tests
```bash
pytest
```

### Code Formatting
```bash
black .
flake8 .
mypy .
```

### Pre-commit Hooks
```bash
pre-commit install
```

## API Documentation

Once the API server is running, visit:
- API docs: http://localhost:8000/docs
- Alternative docs: http://localhost:8000/redoc

## Web Interface

Access the web UI at: http://localhost:8080

### Default Admin User
- Username: admin
- Password: (set during createsuperuser)

## Security Considerations

- All communication between components uses TLS with self-signed certificates
- Agents authenticate using client certificates
- Web UI supports role-based access control
- API endpoints require proper authentication tokens
- Firewall rules are validated before application

## Troubleshooting

### Common Issues

1. **Agent connection failed**: Check certificate paths and server URL
2. **Database connection error**: Verify PostgreSQL is running and credentials are correct
3. **Permission denied on firewall operations**: Ensure agent runs with appropriate privileges
4. **Redis connection failed**: Verify Redis server is running

### Log Locations
- API Server: `./logs/api_server.log`
- Web UI: `./logs/web_ui.log`
- Agent: `/var/log/firewalld-agent.log` (configurable)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## License

[Your License Here]

## Support

For issues and questions:
- Create an issue on GitHub
- Check the troubleshooting section
- Review the API documentation
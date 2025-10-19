# firewalld-central API Server

FastAPI-based REST API server for centralized firewalld management.

## Features

- **Agent Registration**: Secure agent registration with certificate management
- **Command Dispatch**: Remote command execution on agents
- **Real-time Status**: Agent status monitoring and updates
- **Rule Management**: Centralized firewall rule configuration
- **Health Monitoring**: API and system health endpoints

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Initialize database:
```bash
alembic upgrade head
```

4. Start server:
```bash
python main.py
```

## Configuration

Environment variables:
- `DATABASE_URL`: Database connection string
- `REDIS_URL`: Redis connection for caching
- `SECRET_KEY`: JWT signing key
- `SSL_ENABLED`: Enable HTTPS (true/false)
- `SSL_CERT_FILE`: SSL certificate path
- `SSL_KEY_FILE`: SSL private key path
- `ALLOWED_ORIGINS`: CORS allowed origins

## API Endpoints

### Agents
- `POST /api/agents/register` - Register new agent
- `GET /api/agents/` - List all agents
- `GET /api/agents/{id}` - Get agent details
- `PUT /api/agents/{id}/status` - Update agent status
- `DELETE /api/agents/{id}` - Remove agent

### Commands
- `POST /api/agents/{id}/commands` - Execute command
- `GET /api/agents/{id}/commands` - List agent commands
- `GET /api/commands/{id}` - Get command status

### Health
- `GET /api/health` - Health check
- `GET /api/version` - API version
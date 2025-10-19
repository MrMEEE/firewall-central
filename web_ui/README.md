# firewalld-central Web UI

Django-based web interface for centralized firewalld management.

## Features

- **Whiteboard Interface**: Visual network topology with drag-and-drop agent positioning
- **Real-time Updates**: WebSocket integration for live status updates
- **User Management**: Role-based access control with permissions
- **Agent Management**: Monitor and control firewalld agents
- **Rule Visualization**: View and manage firewall rules with connection mapping

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure settings:
```bash
cp firewall_central/settings_local.py.example firewall_central/settings_local.py
# Edit settings_local.py with your configuration
```

3. Run migrations:
```bash
python manage.py migrate
```

4. Create superuser:
```bash
python manage.py createsuperuser
```

5. Start development server:
```bash
python manage.py runserver
```

## Configuration

Environment variables:
- `DEBUG`: Set to False for production
- `SECRET_KEY`: Django secret key
- `DATABASE_URL`: Database connection string
- `REDIS_URL`: Redis connection for caching and WebSockets
- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts

## Structure

- `agents/`: Agent management app
- `dashboard/`: Main dashboard and whiteboard interface
- `users/`: User management and authentication
- `templates/`: Django templates
- `static/`: CSS, JavaScript, and static assets
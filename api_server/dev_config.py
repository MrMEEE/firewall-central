# Development configuration for API server
import os
from pathlib import Path

# Use SQLite for development
DATABASE_URL = f"sqlite:///{Path(__file__).parent}/api_server.db"
SECRET_KEY = "dev-secret-key-change-in-production"
DEBUG = True
HOST = "127.0.0.1"
PORT = 8000

# Disable Redis for development
REDIS_URL = None

# SSL disabled for development
SSL_ENABLED = False
SSL_CERT_FILE = None
SSL_KEY_FILE = None

ALLOWED_ORIGINS = ["http://localhost:8001", "http://127.0.0.1:8001"]
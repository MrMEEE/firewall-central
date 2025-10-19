"""
Shared configuration utilities.
"""

import os
import yaml
from typing import Dict, Any, Optional
from pydantic_settings import BaseSettings


class BaseConfig(BaseSettings):
    """Base configuration class with common settings."""
    
    # Security
    secret_key: str = "your-secret-key-change-this-in-production"
    api_secret_key: str = "your-api-secret-key-change-this-in-production"
    
    # Database
    database_url: str = "postgresql://firewalld_user:firewalld_pass@localhost:5432/firewalld_central"
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "./logs/firewalld_central.log"
    
    # SSL/TLS
    ssl_cert_path: str = "./certs/server.crt"
    ssl_key_path: str = "./certs/server.key"
    ca_cert_path: str = "./certs/ca.crt"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


class APIServerConfig(BaseConfig):
    """Configuration for the API server."""
    
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # Agent communication
    agent_timeout: int = 30
    max_agents: int = 1000
    
    # Certificate paths
    certs_dir: str = "./certs"
    
    class Config:
        env_prefix = "API_"


class WebUIConfig(BaseConfig):
    """Configuration for the Django web UI."""
    
    web_host: str = "0.0.0.0"
    web_port: int = 8080
    debug: bool = True
    
    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/1"
    
    # Static files
    static_url: str = "/static/"
    static_root: str = "./staticfiles"
    
    class Config:
        env_prefix = "WEB_"


class AgentConfig(BaseConfig):
    """Configuration for the firewalld agent."""
    
    # Server connection
    server_url: str = "https://localhost:8000"
    mode: str = "pull"  # pull or push
    poll_interval: int = 30
    
    # Agent identification
    agent_id: Optional[str] = None
    hostname: Optional[str] = None
    
    # Networking
    listen_host: str = "0.0.0.0"
    listen_port: int = 9000
    
    # Timeouts and retries
    connection_timeout: int = 10
    max_retries: int = 3
    retry_delay: int = 5
    
    # Firewalld
    firewalld_reload_timeout: int = 30
    
    class Config:
        env_prefix = "AGENT_"


def load_yaml_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from a YAML file."""
    if not os.path.exists(config_path):
        return {}
    
    with open(config_path, 'r') as f:
        return yaml.safe_load(f) or {}


def save_yaml_config(config: Dict[str, Any], config_path: str) -> None:
    """Save configuration to a YAML file."""
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, indent=2)


def ensure_directories(*dirs: str) -> None:
    """Ensure that directories exist, creating them if necessary."""
    for directory in dirs:
        if directory:
            os.makedirs(directory, exist_ok=True)


def get_config_value(config: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Get a configuration value using dot notation (e.g., 'server.host')."""
    keys = key.split('.')
    value = config
    
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return default
    
    return value


def set_config_value(config: Dict[str, Any], key: str, value: Any) -> None:
    """Set a configuration value using dot notation (e.g., 'server.host')."""
    keys = key.split('.')
    current = config
    
    for k in keys[:-1]:
        if k not in current:
            current[k] = {}
        current = current[k]
    
    current[keys[-1]] = value
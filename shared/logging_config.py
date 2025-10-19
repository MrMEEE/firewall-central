"""
Shared logging utilities.
"""

import os
import sys
import logging
import structlog
from datetime import datetime
from typing import Any, Dict


def setup_logging(
    log_level: str = "INFO",
    log_file: str = None,
    component_name: str = "firewalld_central"
) -> None:
    """Setup structured logging for the application."""
    
    # Ensure log directory exists
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(message)s',
        handlers=[]
    )
    
    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    
    # Add file handler if specified
    handlers = [console_handler]
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_handler.setFormatter(console_formatter)
        handlers.append(file_handler)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers = handlers
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Configure component logger
    logger = structlog.get_logger(component_name)
    logger.info("Logging initialized", 
                component=component_name, 
                log_level=log_level,
                log_file=log_file)


def get_logger(name: str = None) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


def log_api_request(
    logger: structlog.BoundLogger,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    user_id: str = None,
    agent_id: str = None,
    **kwargs
) -> None:
    """Log an API request with standard fields."""
    logger.info(
        "API request",
        method=method,
        path=path,
        status_code=status_code,
        duration_ms=duration_ms,
        user_id=user_id,
        agent_id=agent_id,
        **kwargs
    )


def log_agent_activity(
    logger: structlog.BoundLogger,
    agent_id: str,
    action: str,
    success: bool,
    details: Dict[str, Any] = None,
    **kwargs
) -> None:
    """Log agent activity with standard fields."""
    logger.info(
        "Agent activity",
        agent_id=agent_id,
        action=action,
        success=success,
        details=details or {},
        **kwargs
    )


def log_firewall_change(
    logger: structlog.BoundLogger,
    agent_id: str,
    zone: str,
    rule_type: str,
    rule_data: Dict[str, Any],
    action: str,  # add, remove, modify
    success: bool,
    user_id: str = None,
    **kwargs
) -> None:
    """Log firewall configuration changes."""
    logger.info(
        "Firewall configuration change",
        agent_id=agent_id,
        zone=zone,
        rule_type=rule_type,
        rule_data=rule_data,
        action=action,
        success=success,
        user_id=user_id,
        **kwargs
    )


def log_security_event(
    logger: structlog.BoundLogger,
    event_type: str,
    severity: str,  # low, medium, high, critical
    description: str,
    source_ip: str = None,
    user_id: str = None,
    agent_id: str = None,
    additional_data: Dict[str, Any] = None,
    **kwargs
) -> None:
    """Log security-related events."""
    logger.warning(
        "Security event",
        event_type=event_type,
        severity=severity,
        description=description,
        source_ip=source_ip,
        user_id=user_id,
        agent_id=agent_id,
        additional_data=additional_data or {},
        **kwargs
    )


class RequestIDFilter(logging.Filter):
    """Add request ID to log records for tracing."""
    
    def filter(self, record):
        # In a real application, you would get this from context
        # For now, we'll just add a placeholder
        record.request_id = getattr(record, 'request_id', 'unknown')
        return True


class ComponentFilter(logging.Filter):
    """Add component name to log records."""
    
    def __init__(self, component_name: str):
        super().__init__()
        self.component_name = component_name
    
    def filter(self, record):
        record.component = self.component_name
        return True
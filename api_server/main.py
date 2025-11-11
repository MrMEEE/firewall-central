#!/usr/bin/env python3
"""
API Server - Central management server for firewalld agents.

Provides RESTful API for:
- Agent registration and management
- Certificate management
- Command dispatching
- Configuration management
"""

import os
import sys
import asyncio
import signal
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import uuid

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import structlog
import redis.asyncio as redis

# Add parent directory to path for shared imports
sys.path.append(str(Path(__file__).parent.parent))

from shared.models import (
    AgentInfo, AgentRegistration, AgentConfiguration, AgentCommand,
    CommandResult, ApiResponse, FirewallConfiguration, AgentStatus, AgentMode
)
from shared.config import APIServerConfig
from shared.logging_config import setup_logging, get_logger
from shared.crypto import CertificateManager, get_local_ip

from database import DatabaseManager
from agent_manager import AgentManager
from command_dispatcher import CommandDispatcher


# FastAPI app setup
app = FastAPI(
    title="Firewalld Central API",
    description="Central management API for firewalld agents",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Setup CORS middleware (must be added before startup)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Global variables
config: APIServerConfig = None
db_manager: DatabaseManager = None
agent_manager: AgentManager = None
command_dispatcher: CommandDispatcher = None
redis_client: redis.Redis = None
logger = None


@app.on_event("startup")
async def startup_event():
    """Initialize the application."""
    global config, db_manager, agent_manager, command_dispatcher, redis_client, logger
    
    # Load configuration
    config = APIServerConfig()
    
    # Setup logging
    setup_logging(
        log_level=config.log_level,
        log_file=config.log_file,
        component_name="api_server"
    )
    logger = get_logger("api_server")
    
    # Initialize Redis (optional for development)
    try:
        if config.redis_url and config.redis_url.lower() != "none":
            redis_client = redis.from_url(config.redis_url)
            logger.info("Redis connected")
        else:
            redis_client = None
            logger.info("Redis disabled for development")
    except Exception as e:
        logger.warning("Redis connection failed, continuing without Redis", error=str(e))
        redis_client = None
    
    # Initialize database
    db_manager = DatabaseManager(config.database_url)
    await db_manager.initialize()
    
    # Initialize certificate manager (optional for development)
    cert_manager = None
    try:
        if os.path.exists(config.ca_cert_path):
            cert_manager = CertificateManager(
                config.ca_cert_path,
                config.ca_cert_path.replace('.crt', '.key')
            )
            logger.info("Certificate manager initialized")
        else:
            logger.info("Certificate manager disabled (no CA certificate found)")
    except Exception as e:
        logger.warning("Certificate manager initialization failed", error=str(e))
        cert_manager = None
    
    # Initialize managers
    agent_manager = AgentManager(db_manager, cert_manager, redis_client)
    command_dispatcher = CommandDispatcher(db_manager, redis_client)
    
    logger.info("API server started", 
                host=config.api_host, 
                port=config.api_port)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global redis_client, db_manager, logger
    
    if redis_client:
        await redis_client.close()
    
    if db_manager:
        await db_manager.close()
    
    if logger:
        logger.info("API server shutting down")


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Get current user from JWT token."""
    # TODO: Implement JWT validation
    # For now, return a placeholder user
    return "system"


# Agent Management Endpoints

@app.post("/api/agents/register")
async def register_agent(
    registration: AgentRegistration,
    background_tasks: BackgroundTasks
) -> ApiResponse:
    """Register a new agent."""
    try:
        result = await agent_manager.register_agent(registration)
        
        if result["success"]:
            logger.info("Agent registered successfully", 
                       hostname=registration.hostname,
                       ip_address=registration.ip_address)
            
            return ApiResponse(
                success=True,
                message="Agent registered successfully",
                data=result["data"]
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
    
    except Exception as e:
        logger.error("Error registering agent", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/agents")
async def list_agents(
    status_filter: Optional[str] = None,
    user: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """List all registered agents."""
    try:
        agents = await agent_manager.list_agents(status_filter)
        
        return {
            "success": True,
            "agents": agents,
            "count": len(agents)
        }
    
    except Exception as e:
        logger.error("Error listing agents", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/agents/{agent_id}")
async def get_agent(
    agent_id: str,
    user: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get agent details."""
    try:
        agent = await agent_manager.get_agent(agent_id)
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        return {
            "success": True,
            "agent": agent
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting agent", agent_id=agent_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/agents/{agent_id}/heartbeat")
async def agent_heartbeat(
    agent_id: str,
    agent_info: AgentInfo
) -> ApiResponse:
    """Receive heartbeat from agent."""
    try:
        await agent_manager.update_agent_heartbeat(agent_id, agent_info)
        
        return ApiResponse(
            success=True,
            message="Heartbeat received"
        )
    
    except Exception as e:
        logger.error("Error processing heartbeat", 
                    agent_id=agent_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/agents/{agent_id}/commands")
async def get_agent_commands(agent_id: str) -> Dict[str, Any]:
    """Get pending commands for an agent."""
    try:
        commands = await command_dispatcher.get_pending_commands(agent_id)
        
        return {
            "success": True,
            "commands": [cmd.dict() for cmd in commands]
        }
    
    except Exception as e:
        logger.error("Error getting agent commands", 
                    agent_id=agent_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.delete("/api/agents/{agent_id}")
async def delete_agent(
    agent_id: str,
    user: str = Depends(get_current_user)
) -> ApiResponse:
    """Delete an agent."""
    try:
        success = await agent_manager.delete_agent(agent_id)
        
        if success:
            return ApiResponse(
                success=True,
                message="Agent deleted successfully"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error deleting agent", agent_id=agent_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# Command Management Endpoints

@app.post("/api/agents/{agent_id}/commands")
async def send_command_to_agent(
    agent_id: str,
    command_type: str,
    parameters: Dict[str, Any],
    timeout: int = 30,
    user: str = Depends(get_current_user)
) -> ApiResponse:
    """Send a command to an agent."""
    try:
        command = AgentCommand(
            command_id=str(uuid.uuid4()),
            agent_id=agent_id,
            command_type=command_type,
            parameters=parameters,
            timeout=timeout
        )
        
        success = await command_dispatcher.send_command(command)
        
        if success:
            return ApiResponse(
                success=True,
                message="Command sent successfully",
                data={"command_id": command.command_id}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to send command"
            )
    
    except Exception as e:
        logger.error("Error sending command", 
                    agent_id=agent_id, command_type=command_type, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/commands/{command_id}/result")
async def receive_command_result(
    command_id: str,
    result: CommandResult
) -> ApiResponse:
    """Receive command result from agent."""
    try:
        await command_dispatcher.process_command_result(result)
        
        return ApiResponse(
            success=True,
            message="Command result received"
        )
    
    except Exception as e:
        logger.error("Error processing command result", 
                    command_id=command_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/commands/{command_id}")
async def get_command_status(
    command_id: str,
    user: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get command status and result."""
    try:
        command_info = await command_dispatcher.get_command_status(command_id)
        
        if not command_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Command not found"
            )
        
        return {
            "success": True,
            "command": command_info
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting command status", 
                    command_id=command_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# Configuration Management Endpoints

@app.post("/api/agents/{agent_id}/configuration")
async def apply_agent_configuration(
    agent_id: str,
    configuration: FirewallConfiguration,
    user: str = Depends(get_current_user)
) -> ApiResponse:
    """Apply firewall configuration to an agent."""
    try:
        command = AgentCommand(
            command_id=str(uuid.uuid4()),
            agent_id=agent_id,
            command_type="apply_configuration",
            parameters=configuration.dict()
        )
        
        success = await command_dispatcher.send_command(command)
        
        if success:
            return ApiResponse(
                success=True,
                message="Configuration command sent",
                data={"command_id": command.command_id}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to send configuration command"
            )
    
    except Exception as e:
        logger.error("Error applying configuration", 
                    agent_id=agent_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/agents/{agent_id}/status")
async def get_agent_firewall_status(
    agent_id: str,
    user: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get firewall status from an agent."""
    try:
        command = AgentCommand(
            command_id=str(uuid.uuid4()),
            agent_id=agent_id,
            command_type="get_status",
            parameters={}
        )
        
        # Send command and wait for result (simplified for this example)
        success = await command_dispatcher.send_command(command)
        
        if success:
            return {
                "success": True,
                "message": "Status request sent",
                "command_id": command.command_id
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to request status"
            )
    
    except Exception as e:
        logger.error("Error getting agent status", 
                    agent_id=agent_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# Health and Status Endpoints

@app.get("/api/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    try:
        # Check database connection
        db_healthy = await db_manager.health_check()
        
        # Check Redis connection
        redis_healthy = await redis_client.ping()
        
        return {
            "status": "healthy" if db_healthy and redis_healthy else "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "database": "healthy" if db_healthy else "unhealthy",
                "redis": "healthy" if redis_healthy else "unhealthy"
            }
        }
    
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


@app.get("/api/stats")
async def get_stats(user: str = Depends(get_current_user)) -> Dict[str, Any]:
    """Get system statistics."""
    try:
        stats = await agent_manager.get_statistics()
        
        return {
            "success": True,
            "stats": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error("Error getting stats", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# Exception handlers

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    logger.error("Unhandled exception", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "timestamp": datetime.utcnow().isoformat()
        }
    )


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info("Received shutdown signal")
    sys.exit(0)


def main():
    """Main entry point."""
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Load configuration
    config = APIServerConfig()
    
    # Run the server
    uvicorn.run(
        "main:app",
        host=config.api_host,
        port=config.api_port,
        ssl_keyfile=config.ssl_key_path if os.path.exists(config.ssl_key_path) else None,
        ssl_certfile=config.ssl_cert_path if os.path.exists(config.ssl_cert_path) else None,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    main()
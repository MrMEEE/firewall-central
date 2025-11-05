#!/usr/bin/env python3
"""
Development version of API server with simplified configuration
"""
import uvicorn
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

# Simple in-memory storage for development
agents_db: Dict[str, Dict[str, Any]] = {}
commands_queue: Dict[str, List[Dict[str, Any]]] = {}

# Pydantic models for requests
class AgentRegistration(BaseModel):
    hostname: str
    ip_address: str
    firewalld_version: Optional[str] = None
    os_info: Optional[str] = None

class CommandResult(BaseModel):
    command_id: str
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None

app = FastAPI(
    title="firewalld-central API",
    description="Centralized firewalld management API server",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "firewalld-central API Server", "version": "1.0.0"}

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "database_connected": True,  # Simplified for dev
        "redis_connected": False,    # Disabled for dev
        "active_agents": len(agents_db)
    }

@app.get("/api/agents")
async def list_agents():
    return list(agents_db.values())

@app.post("/api/agents/register")
async def register_agent(agent: AgentRegistration):
    """Register a new agent or update existing one"""
    agent_id = f"{agent.hostname}-{agent.ip_address}"
    
    agent_data = {
        "agent_id": agent_id,
        "hostname": agent.hostname,
        "ip_address": agent.ip_address,
        "firewalld_version": agent.firewalld_version,
        "os_info": agent.os_info,
        "status": "online",
        "last_checkin": datetime.now().isoformat(),
        "registered_at": agents_db.get(agent_id, {}).get("registered_at", datetime.now().isoformat())
    }
    
    agents_db[agent_id] = agent_data
    
    # Initialize command queue for this agent if not exists
    if agent_id not in commands_queue:
        commands_queue[agent_id] = []
    
    return {
        "agent_id": agent_id,
        "api_key": f"dev-key-{agent_id}",
        "checkin_interval": 30,
        "message": "Agent registered successfully"
    }

@app.post("/api/agents/{agent_id}/checkin")
async def agent_checkin(agent_id: str):
    """Agent checks in and gets pending commands"""
    if agent_id not in agents_db:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Update last checkin time
    agents_db[agent_id]["last_checkin"] = datetime.now().isoformat()
    agents_db[agent_id]["status"] = "online"
    
    # Get pending commands for this agent
    pending_commands = commands_queue.get(agent_id, [])
    
    return {
        "agent_id": agent_id,
        "status": "ok",
        "commands": pending_commands
    }

@app.post("/api/agents/{agent_id}/results")
async def submit_command_result(agent_id: str, result: CommandResult):
    """Agent submits command execution results"""
    if agent_id not in agents_db:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Remove the completed command from queue
    if agent_id in commands_queue:
        commands_queue[agent_id] = [
            cmd for cmd in commands_queue[agent_id] 
            if cmd.get("command_id") != result.command_id
        ]
    
    return {
        "status": "ok",
        "message": "Result received"
    }

@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get agent details"""
    if agent_id not in agents_db:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return agents_db[agent_id]

if __name__ == "__main__":
    print("Starting firewalld-central API Server (Development Mode)")
    print("API Documentation: http://0.0.0.0:8000/docs")
    uvicorn.run(
        "dev_main:app",
        host="0.0.0.0",
        port=8000,
        reload=False
    )
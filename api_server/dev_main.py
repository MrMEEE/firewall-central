#!/usr/bin/env python3
"""
Development version of API server with simplified configuration
"""
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="firewalld-central API",
    description="Centralized firewalld management API server",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8001", "http://127.0.0.1:8001"],
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
        "active_agents": 0
    }

@app.get("/api/agents")
async def list_agents():
    # Return empty list for development
    return []

if __name__ == "__main__":
    print("Starting firewalld-central API Server (Development Mode)")
    print("API Documentation: http://127.0.0.1:8000/docs")
    uvicorn.run(
        "dev_main:app",
        host="127.0.0.1",
        port=8000,
        reload=False
    )
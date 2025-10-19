from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from ..database import get_db, Agent
from ..schemas import HealthCheck

router = APIRouter()


@router.get("/health", response_model=HealthCheck)
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint"""
    try:
        # Test database connection
        active_agents = db.query(Agent).filter(Agent.status == "online").count()
        database_connected = True
    except Exception:
        database_connected = False
        active_agents = 0
    
    # Test Redis connection (placeholder)
    redis_connected = True  # TODO: Implement Redis health check
    
    return HealthCheck(
        status="healthy" if database_connected else "unhealthy",
        version="1.0.0",
        database_connected=database_connected,
        redis_connected=redis_connected,
        active_agents=active_agents
    )


@router.get("/version")
async def get_version():
    """Get API version"""
    return {"version": "1.0.0", "name": "firewalld-central API"}
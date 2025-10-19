from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from ..database import get_db, Agent
from ..schemas import AgentRegistration, AgentInfo, AgentStatusUpdate
from ..agent_manager import AgentManager

router = APIRouter()
agent_manager = AgentManager()


@router.post("/register", response_model=AgentInfo)
async def register_agent(agent_data: AgentRegistration, db: Session = Depends(get_db)):
    """Register a new agent"""
    try:
        # Check if agent already exists
        existing_agent = db.query(Agent).filter(Agent.hostname == agent_data.hostname).first()
        if existing_agent:
            # Update existing agent
            for key, value in agent_data.dict().items():
                if hasattr(existing_agent, key):
                    setattr(existing_agent, key, value)
            existing_agent.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(existing_agent)
            return existing_agent
        
        # Create new agent
        agent = Agent(**agent_data.dict())
        db.add(agent)
        db.commit()
        db.refresh(agent)
        
        # Generate certificate if requested
        if agent_data.certificate_request:
            cert_pem = await agent_manager.generate_agent_certificate(agent.id)
            agent.certificate_issued = True
            db.commit()
        
        return agent
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[AgentInfo])
async def list_agents(db: Session = Depends(get_db)):
    """List all registered agents"""
    agents = db.query(Agent).all()
    return agents


@router.get("/{agent_id}", response_model=AgentInfo)
async def get_agent(agent_id: str, db: Session = Depends(get_db)):
    """Get specific agent details"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/{agent_id}/status")
async def update_agent_status(
    agent_id: str, 
    status_update: AgentStatusUpdate,
    db: Session = Depends(get_db)
):
    """Update agent status"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent.status = status_update.status
    agent.last_seen = status_update.timestamp
    agent.updated_at = datetime.utcnow()
    
    db.commit()
    
    return {"message": "Status updated successfully"}


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str, db: Session = Depends(get_db)):
    """Delete an agent"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    db.delete(agent)
    db.commit()
    
    return {"message": "Agent deleted successfully"}


@router.get("/{agent_id}/certificate")
async def get_agent_certificate(agent_id: str, db: Session = Depends(get_db)):
    """Get agent certificate"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    if not agent.certificate_issued:
        raise HTTPException(status_code=404, detail="Certificate not issued")
    
    cert_pem = await agent_manager.get_agent_certificate(agent_id)
    if not cert_pem:
        raise HTTPException(status_code=404, detail="Certificate not found")
    
    return {"certificate": cert_pem}


@router.post("/{agent_id}/certificate")
async def issue_agent_certificate(agent_id: str, db: Session = Depends(get_db)):
    """Issue certificate for agent"""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    try:
        cert_pem = await agent_manager.generate_agent_certificate(agent_id)
        agent.certificate_issued = True
        agent.updated_at = datetime.utcnow()
        db.commit()
        
        return {"certificate": cert_pem}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
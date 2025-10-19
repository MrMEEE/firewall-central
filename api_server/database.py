"""
Database manager for the API server.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer, JSON, select, update, delete
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import structlog

from shared.models import AgentInfo, AgentStatus, AgentMode

Base = declarative_base()


class Agent(Base):
    __tablename__ = "agents"
    
    agent_id = Column(String, primary_key=True)
    hostname = Column(String, nullable=False)
    ip_address = Column(String, nullable=False)
    mode = Column(String, nullable=False)  # pull or push
    status = Column(String, nullable=False)  # online, offline, error, pending
    last_seen = Column(DateTime, nullable=False)
    version = Column(String)
    operating_system = Column(String)
    firewalld_version = Column(String)
    certificate_data = Column(Text)  # JSON string
    configuration = Column(JSON)  # Current configuration
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Command(Base):
    __tablename__ = "commands"
    
    command_id = Column(String, primary_key=True)
    agent_id = Column(String, nullable=False)
    command_type = Column(String, nullable=False)
    parameters = Column(JSON, nullable=False)
    timeout = Column(Integer, default=30)
    status = Column(String, default="pending")  # pending, sent, completed, failed, timeout
    result = Column(JSON)  # Command result
    error = Column(Text)  # Error message if failed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    executed_at = Column(DateTime)


class User(Base):
    __tablename__ = "users"
    
    user_id = Column(String, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)  # admin, manager, viewer
    permissions = Column(JSON)  # Agent permissions
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    log_id = Column(String, primary_key=True)
    user_id = Column(String)
    agent_id = Column(String)
    action = Column(String, nullable=False)
    details = Column(JSON)
    ip_address = Column(String)
    user_agent = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)


class DatabaseManager:
    """Manages database operations."""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = None
        self.session_maker = None
        self.logger = structlog.get_logger("database_manager")
    
    async def initialize(self):
        """Initialize database connection and create tables."""
        try:
            # Convert PostgreSQL URL to async version
            if self.database_url.startswith("postgresql://"):
                self.database_url = self.database_url.replace("postgresql://", "postgresql+asyncpg://")
            
            self.engine = create_async_engine(
                self.database_url,
                echo=False,
                pool_size=10,
                max_overflow=20
            )
            
            self.session_maker = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Create tables
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            self.logger.info("Database initialized successfully")
            
        except Exception as e:
            self.logger.error("Failed to initialize database", error=str(e))
            raise
    
    async def close(self):
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()
            self.logger.info("Database connections closed")
    
    async def health_check(self) -> bool:
        """Check database health."""
        try:
            async with self.session_maker() as session:
                result = await session.execute(select(1))
                return True
        except Exception as e:
            self.logger.error("Database health check failed", error=str(e))
            return False
    
    # Agent operations
    
    async def create_agent(self, agent_info: AgentInfo, certificate_data: str = None) -> bool:
        """Create a new agent record."""
        try:
            async with self.session_maker() as session:
                agent = Agent(
                    agent_id=agent_info.agent_id,
                    hostname=agent_info.hostname,
                    ip_address=agent_info.ip_address,
                    mode=agent_info.mode.value,
                    status=agent_info.status.value,
                    last_seen=agent_info.last_seen,
                    version=agent_info.version,
                    operating_system=agent_info.operating_system,
                    firewalld_version=agent_info.firewalld_version,
                    certificate_data=certificate_data
                )
                
                session.add(agent)
                await session.commit()
                
                self.logger.info("Agent created", agent_id=agent_info.agent_id)
                return True
                
        except Exception as e:
            self.logger.error("Failed to create agent", 
                            agent_id=agent_info.agent_id, error=str(e))
            return False
    
    async def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get agent by ID."""
        try:
            async with self.session_maker() as session:
                result = await session.execute(
                    select(Agent).where(Agent.agent_id == agent_id)
                )
                agent = result.scalar_one_or_none()
                
                if agent:
                    return {
                        "agent_id": agent.agent_id,
                        "hostname": agent.hostname,
                        "ip_address": agent.ip_address,
                        "mode": agent.mode,
                        "status": agent.status,
                        "last_seen": agent.last_seen.isoformat() if agent.last_seen else None,
                        "version": agent.version,
                        "operating_system": agent.operating_system,
                        "firewalld_version": agent.firewalld_version,
                        "configuration": agent.configuration,
                        "created_at": agent.created_at.isoformat() if agent.created_at else None,
                        "updated_at": agent.updated_at.isoformat() if agent.updated_at else None
                    }
                return None
                
        except Exception as e:
            self.logger.error("Failed to get agent", agent_id=agent_id, error=str(e))
            return None
    
    async def list_agents(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all agents with optional status filter."""
        try:
            async with self.session_maker() as session:
                query = select(Agent)
                
                if status_filter:
                    query = query.where(Agent.status == status_filter)
                
                result = await session.execute(query)
                agents = result.scalars().all()
                
                return [
                    {
                        "agent_id": agent.agent_id,
                        "hostname": agent.hostname,
                        "ip_address": agent.ip_address,
                        "mode": agent.mode,
                        "status": agent.status,
                        "last_seen": agent.last_seen.isoformat() if agent.last_seen else None,
                        "version": agent.version,
                        "operating_system": agent.operating_system,
                        "firewalld_version": agent.firewalld_version,
                        "created_at": agent.created_at.isoformat() if agent.created_at else None
                    }
                    for agent in agents
                ]
                
        except Exception as e:
            self.logger.error("Failed to list agents", error=str(e))
            return []
    
    async def update_agent_heartbeat(self, agent_id: str, agent_info: AgentInfo) -> bool:
        """Update agent heartbeat information."""
        try:
            async with self.session_maker() as session:
                await session.execute(
                    update(Agent)
                    .where(Agent.agent_id == agent_id)
                    .values(
                        status=agent_info.status.value,
                        last_seen=agent_info.last_seen,
                        version=agent_info.version,
                        operating_system=agent_info.operating_system,
                        firewalld_version=agent_info.firewalld_version,
                        updated_at=datetime.utcnow()
                    )
                )
                await session.commit()
                return True
                
        except Exception as e:
            self.logger.error("Failed to update agent heartbeat", 
                            agent_id=agent_id, error=str(e))
            return False
    
    async def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent."""
        try:
            async with self.session_maker() as session:
                # Delete related commands first
                await session.execute(
                    delete(Command).where(Command.agent_id == agent_id)
                )
                
                # Delete agent
                result = await session.execute(
                    delete(Agent).where(Agent.agent_id == agent_id)
                )
                
                await session.commit()
                
                if result.rowcount > 0:
                    self.logger.info("Agent deleted", agent_id=agent_id)
                    return True
                return False
                
        except Exception as e:
            self.logger.error("Failed to delete agent", agent_id=agent_id, error=str(e))
            return False
    
    async def get_agent_certificate(self, agent_id: str) -> Optional[str]:
        """Get agent certificate data."""
        try:
            async with self.session_maker() as session:
                result = await session.execute(
                    select(Agent.certificate_data).where(Agent.agent_id == agent_id)
                )
                cert_data = result.scalar_one_or_none()
                return cert_data
                
        except Exception as e:
            self.logger.error("Failed to get agent certificate", 
                            agent_id=agent_id, error=str(e))
            return None
    
    async def update_agent_certificate(self, agent_id: str, certificate_data: str) -> bool:
        """Update agent certificate data."""
        try:
            async with self.session_maker() as session:
                await session.execute(
                    update(Agent)
                    .where(Agent.agent_id == agent_id)
                    .values(
                        certificate_data=certificate_data,
                        updated_at=datetime.utcnow()
                    )
                )
                await session.commit()
                return True
                
        except Exception as e:
            self.logger.error("Failed to update agent certificate", 
                            agent_id=agent_id, error=str(e))
            return False
    
    # Command operations
    
    async def create_command(self, command_id: str, agent_id: str, command_type: str, 
                           parameters: Dict[str, Any], timeout: int = 30) -> bool:
        """Create a new command."""
        try:
            async with self.session_maker() as session:
                command = Command(
                    command_id=command_id,
                    agent_id=agent_id,
                    command_type=command_type,
                    parameters=parameters,
                    timeout=timeout
                )
                
                session.add(command)
                await session.commit()
                
                self.logger.info("Command created", 
                               command_id=command_id, agent_id=agent_id)
                return True
                
        except Exception as e:
            self.logger.error("Failed to create command", 
                            command_id=command_id, error=str(e))
            return False
    
    async def get_pending_commands(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get pending commands for an agent."""
        try:
            async with self.session_maker() as session:
                result = await session.execute(
                    select(Command)
                    .where(Command.agent_id == agent_id)
                    .where(Command.status == "pending")
                )
                commands = result.scalars().all()
                
                # Mark commands as sent
                command_ids = [cmd.command_id for cmd in commands]
                if command_ids:
                    await session.execute(
                        update(Command)
                        .where(Command.command_id.in_(command_ids))
                        .values(status="sent", updated_at=datetime.utcnow())
                    )
                    await session.commit()
                
                return [
                    {
                        "command_id": cmd.command_id,
                        "agent_id": cmd.agent_id,
                        "command_type": cmd.command_type,
                        "parameters": cmd.parameters,
                        "timeout": cmd.timeout,
                        "created_at": cmd.created_at.isoformat()
                    }
                    for cmd in commands
                ]
                
        except Exception as e:
            self.logger.error("Failed to get pending commands", 
                            agent_id=agent_id, error=str(e))
            return []
    
    async def update_command_result(self, command_id: str, success: bool, 
                                  result: Optional[Dict[str, Any]] = None, 
                                  error: Optional[str] = None) -> bool:
        """Update command result."""
        try:
            async with self.session_maker() as session:
                status = "completed" if success else "failed"
                
                await session.execute(
                    update(Command)
                    .where(Command.command_id == command_id)
                    .values(
                        status=status,
                        result=result,
                        error=error,
                        executed_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                )
                await session.commit()
                
                self.logger.info("Command result updated", 
                               command_id=command_id, success=success)
                return True
                
        except Exception as e:
            self.logger.error("Failed to update command result", 
                            command_id=command_id, error=str(e))
            return False
    
    async def get_command(self, command_id: str) -> Optional[Dict[str, Any]]:
        """Get command by ID."""
        try:
            async with self.session_maker() as session:
                result = await session.execute(
                    select(Command).where(Command.command_id == command_id)
                )
                command = result.scalar_one_or_none()
                
                if command:
                    return {
                        "command_id": command.command_id,
                        "agent_id": command.agent_id,
                        "command_type": command.command_type,
                        "parameters": command.parameters,
                        "timeout": command.timeout,
                        "status": command.status,
                        "result": command.result,
                        "error": command.error,
                        "created_at": command.created_at.isoformat() if command.created_at else None,
                        "executed_at": command.executed_at.isoformat() if command.executed_at else None
                    }
                return None
                
        except Exception as e:
            self.logger.error("Failed to get command", command_id=command_id, error=str(e))
            return None
    
    async def cleanup_old_commands(self, days: int = 7) -> int:
        """Clean up old commands."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            async with self.session_maker() as session:
                result = await session.execute(
                    delete(Command).where(Command.created_at < cutoff_date)
                )
                await session.commit()
                
                deleted_count = result.rowcount
                self.logger.info("Cleaned up old commands", count=deleted_count)
                return deleted_count
                
        except Exception as e:
            self.logger.error("Failed to cleanup old commands", error=str(e))
            return 0
    
    # Statistics
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get system statistics."""
        try:
            async with self.session_maker() as session:
                # Agent statistics
                agent_result = await session.execute(select(Agent))
                agents = agent_result.scalars().all()
                
                agent_stats = {
                    "total": len(agents),
                    "online": len([a for a in agents if a.status == "online"]),
                    "offline": len([a for a in agents if a.status == "offline"]),
                    "error": len([a for a in agents if a.status == "error"]),
                    "pending": len([a for a in agents if a.status == "pending"])
                }
                
                # Command statistics
                command_result = await session.execute(select(Command))
                commands = command_result.scalars().all()
                
                command_stats = {
                    "total": len(commands),
                    "pending": len([c for c in commands if c.status == "pending"]),
                    "sent": len([c for c in commands if c.status == "sent"]),
                    "completed": len([c for c in commands if c.status == "completed"]),
                    "failed": len([c for c in commands if c.status == "failed"])
                }
                
                return {
                    "agents": agent_stats,
                    "commands": command_stats
                }
                
        except Exception as e:
            self.logger.error("Failed to get statistics", error=str(e))
            return {"agents": {}, "commands": {}}
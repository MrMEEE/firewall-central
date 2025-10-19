"""
Agent Manager - Handles agent registration and management.
"""

import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
import structlog
import redis.asyncio as redis

from shared.models import AgentInfo, AgentRegistration, AgentStatus, AgentMode
from shared.crypto import CertificateManager
from database import DatabaseManager


class AgentManager:
    """Manages agent registration, certificates, and communication."""
    
    def __init__(self, db_manager: DatabaseManager, cert_manager: CertificateManager, redis_client: redis.Redis):
        self.db_manager = db_manager
        self.cert_manager = cert_manager
        self.redis_client = redis_client
        self.logger = structlog.get_logger("agent_manager")
    
    async def register_agent(self, registration: AgentRegistration) -> Dict[str, Any]:
        """Register a new agent."""
        try:
            # Generate unique agent ID
            agent_id = f"{registration.hostname}-{uuid.uuid4().hex[:8]}"
            
            # Check if agent with same hostname already exists
            existing_agents = await self.db_manager.list_agents()
            for agent in existing_agents:
                if agent["hostname"] == registration.hostname:
                    # Update existing agent
                    agent_id = agent["agent_id"]
                    break
            
            # Generate certificates for the agent
            cert_pem, key_pem = self.cert_manager.generate_client_certificate(agent_id)
            
            # Load CA certificate
            with open(self.cert_manager.ca_cert_path, 'rb') as f:
                ca_cert_pem = f.read()
            
            certificate_data = {
                "certificate": cert_pem.decode(),
                "private_key": key_pem.decode(),
                "ca_certificate": ca_cert_pem.decode()
            }
            
            # Create agent info
            agent_info = AgentInfo(
                agent_id=agent_id,
                hostname=registration.hostname,
                ip_address=registration.ip_address,
                mode=registration.mode,
                status=AgentStatus.PENDING,
                last_seen=datetime.utcnow(),
                version="1.0.0",
                operating_system="Unknown",
                firewalld_version="Unknown"
            )
            
            # Save to database
            success = await self.db_manager.create_agent(
                agent_info, 
                json.dumps(certificate_data)
            )
            
            if success:
                # Cache agent status in Redis
                await self.redis_client.setex(
                    f"agent_status:{agent_id}",
                    300,  # 5 minutes
                    agent_info.status.value
                )
                
                self.logger.info("Agent registered successfully", 
                               agent_id=agent_id,
                               hostname=registration.hostname)
                
                return {
                    "success": True,
                    "data": {
                        "agent_id": agent_id,
                        "certificate": certificate_data["certificate"],
                        "private_key": certificate_data["private_key"],
                        "ca_certificate": certificate_data["ca_certificate"]
                    }
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to save agent to database"
                }
                
        except Exception as e:
            self.logger.error("Error registering agent", 
                            hostname=registration.hostname, error=str(e))
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get agent information."""
        try:
            # Try cache first
            cached_status = await self.redis_client.get(f"agent_status:{agent_id}")
            
            # Get from database
            agent = await self.db_manager.get_agent(agent_id)
            
            if agent and cached_status:
                agent["cached_status"] = cached_status.decode()
            
            return agent
            
        except Exception as e:
            self.logger.error("Error getting agent", agent_id=agent_id, error=str(e))
            return None
    
    async def list_agents(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all agents."""
        try:
            agents = await self.db_manager.list_agents(status_filter)
            
            # Enhance with cached status information
            for agent in agents:
                cached_status = await self.redis_client.get(f"agent_status:{agent['agent_id']}")
                if cached_status:
                    agent["cached_status"] = cached_status.decode()
            
            return agents
            
        except Exception as e:
            self.logger.error("Error listing agents", error=str(e))
            return []
    
    async def update_agent_heartbeat(self, agent_id: str, agent_info: AgentInfo) -> bool:
        """Update agent heartbeat information."""
        try:
            # Update database
            success = await self.db_manager.update_agent_heartbeat(agent_id, agent_info)
            
            if success:
                # Update cache
                await self.redis_client.setex(
                    f"agent_status:{agent_id}",
                    300,  # 5 minutes
                    agent_info.status.value
                )
                
                # Store heartbeat timestamp
                await self.redis_client.setex(
                    f"agent_heartbeat:{agent_id}",
                    600,  # 10 minutes
                    agent_info.last_seen.isoformat()
                )
            
            return success
            
        except Exception as e:
            self.logger.error("Error updating agent heartbeat", 
                            agent_id=agent_id, error=str(e))
            return False
    
    async def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent."""
        try:
            # Remove from database
            success = await self.db_manager.delete_agent(agent_id)
            
            if success:
                # Remove from cache
                await self.redis_client.delete(f"agent_status:{agent_id}")
                await self.redis_client.delete(f"agent_heartbeat:{agent_id}")
            
            return success
            
        except Exception as e:
            self.logger.error("Error deleting agent", agent_id=agent_id, error=str(e))
            return False
    
    async def get_agent_certificate(self, agent_id: str) -> Optional[Dict[str, str]]:
        """Get agent certificate data."""
        try:
            cert_data = await self.db_manager.get_agent_certificate(agent_id)
            
            if cert_data:
                return json.loads(cert_data)
            return None
            
        except Exception as e:
            self.logger.error("Error getting agent certificate", 
                            agent_id=agent_id, error=str(e))
            return None
    
    async def regenerate_agent_certificate(self, agent_id: str) -> Optional[Dict[str, str]]:
        """Regenerate certificate for an agent."""
        try:
            # Generate new certificates
            cert_pem, key_pem = self.cert_manager.generate_client_certificate(agent_id)
            
            # Load CA certificate
            with open(self.cert_manager.ca_cert_path, 'rb') as f:
                ca_cert_pem = f.read()
            
            certificate_data = {
                "certificate": cert_pem.decode(),
                "private_key": key_pem.decode(),
                "ca_certificate": ca_cert_pem.decode()
            }
            
            # Update in database
            success = await self.db_manager.update_agent_certificate(
                agent_id,
                json.dumps(certificate_data)
            )
            
            if success:
                self.logger.info("Agent certificate regenerated", agent_id=agent_id)
                return certificate_data
            else:
                return None
                
        except Exception as e:
            self.logger.error("Error regenerating agent certificate", 
                            agent_id=agent_id, error=str(e))
            return None
    
    async def get_online_agents(self) -> List[str]:
        """Get list of online agent IDs."""
        try:
            # Get agents that have sent heartbeat recently
            agent_keys = await self.redis_client.keys("agent_heartbeat:*")
            online_agents = []
            
            for key in agent_keys:
                agent_id = key.decode().split(":", 1)[1]
                status = await self.redis_client.get(f"agent_status:{agent_id}")
                
                if status and status.decode() == "online":
                    online_agents.append(agent_id)
            
            return online_agents
            
        except Exception as e:
            self.logger.error("Error getting online agents", error=str(e))
            return []
    
    async def mark_agent_offline(self, agent_id: str) -> bool:
        """Mark an agent as offline."""
        try:
            # Update cache
            await self.redis_client.setex(
                f"agent_status:{agent_id}",
                300,
                "offline"
            )
            
            # Create agent info for database update
            agent_info = AgentInfo(
                agent_id=agent_id,
                hostname="unknown",
                ip_address="unknown",
                mode=AgentMode.PULL,
                status=AgentStatus.OFFLINE,
                last_seen=datetime.utcnow(),
                version="unknown",
                operating_system="unknown",
                firewalld_version="unknown"
            )
            
            # Update database
            return await self.db_manager.update_agent_heartbeat(agent_id, agent_info)
            
        except Exception as e:
            self.logger.error("Error marking agent offline", 
                            agent_id=agent_id, error=str(e))
            return False
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get agent statistics."""
        try:
            # Get database statistics
            db_stats = await self.db_manager.get_statistics()
            
            # Get cache statistics
            online_agents = await self.get_online_agents()
            
            # Get recent heartbeats
            heartbeat_keys = await self.redis_client.keys("agent_heartbeat:*")
            recent_heartbeats = len(heartbeat_keys)
            
            return {
                "database": db_stats,
                "cache": {
                    "online_agents": len(online_agents),
                    "recent_heartbeats": recent_heartbeats
                }
            }
            
        except Exception as e:
            self.logger.error("Error getting statistics", error=str(e))
            return {}
    
    async def cleanup_stale_agents(self, timeout_minutes: int = 10) -> int:
        """Mark agents as offline if they haven't sent heartbeat recently."""
        try:
            from datetime import timedelta
            
            cutoff_time = datetime.utcnow() - timedelta(minutes=timeout_minutes)
            agents = await self.db_manager.list_agents("online")
            
            stale_count = 0
            
            for agent in agents:
                last_seen = datetime.fromisoformat(agent["last_seen"].replace("Z", "+00:00"))
                if last_seen < cutoff_time:
                    await self.mark_agent_offline(agent["agent_id"])
                    stale_count += 1
            
            if stale_count > 0:
                self.logger.info("Marked stale agents as offline", count=stale_count)
            
            return stale_count
            
        except Exception as e:
            self.logger.error("Error cleaning up stale agents", error=str(e))
            return 0
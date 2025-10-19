"""
Command Dispatcher - Handles command queuing and dispatching to agents.
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
import structlog
import redis.asyncio as redis

from shared.models import AgentCommand, CommandResult
from database import DatabaseManager


class CommandDispatcher:
    """Manages command dispatching to agents."""
    
    def __init__(self, db_manager: DatabaseManager, redis_client: redis.Redis):
        self.db_manager = db_manager
        self.redis_client = redis_client
        self.logger = structlog.get_logger("command_dispatcher")
    
    async def send_command(self, command: AgentCommand) -> bool:
        """Send a command to an agent."""
        try:
            # Store command in database
            success = await self.db_manager.create_command(
                command.command_id,
                command.agent_id,
                command.command_type,
                command.parameters,
                command.timeout
            )
            
            if success:
                # Cache command for quick retrieval
                await self.redis_client.setex(
                    f"command:{command.command_id}",
                    command.timeout + 60,  # Extra time for processing
                    json.dumps(command.dict())
                )
                
                # Add to agent's command queue
                await self.redis_client.lpush(
                    f"agent_commands:{command.agent_id}",
                    command.command_id
                )
                
                self.logger.info("Command sent to agent",
                               command_id=command.command_id,
                               agent_id=command.agent_id,
                               command_type=command.command_type)
                
                return True
            else:
                return False
                
        except Exception as e:
            self.logger.error("Error sending command",
                            command_id=command.command_id,
                            agent_id=command.agent_id,
                            error=str(e))
            return False
    
    async def get_pending_commands(self, agent_id: str) -> List[AgentCommand]:
        """Get pending commands for an agent."""
        try:
            # Get commands from database
            command_data = await self.db_manager.get_pending_commands(agent_id)
            
            commands = []
            for cmd_data in command_data:
                command = AgentCommand(
                    command_id=cmd_data["command_id"],
                    agent_id=cmd_data["agent_id"],
                    command_type=cmd_data["command_type"],
                    parameters=cmd_data["parameters"],
                    timeout=cmd_data["timeout"],
                    created_at=datetime.fromisoformat(cmd_data["created_at"])
                )
                commands.append(command)
            
            return commands
            
        except Exception as e:
            self.logger.error("Error getting pending commands",
                            agent_id=agent_id, error=str(e))
            return []
    
    async def process_command_result(self, result: CommandResult) -> bool:
        """Process a command result from an agent."""
        try:
            # Update command in database
            success = await self.db_manager.update_command_result(
                result.command_id,
                result.success,
                result.result,
                result.error
            )
            
            if success:
                # Remove from Redis cache
                await self.redis_client.delete(f"command:{result.command_id}")
                
                # Remove from agent's command queue
                await self.redis_client.lrem(
                    f"agent_commands:{result.agent_id}",
                    1,
                    result.command_id
                )
                
                self.logger.info("Command result processed",
                               command_id=result.command_id,
                               agent_id=result.agent_id,
                               success=result.success)
                
                return True
            else:
                return False
                
        except Exception as e:
            self.logger.error("Error processing command result",
                            command_id=result.command_id,
                            agent_id=result.agent_id,
                            error=str(e))
            return False
    
    async def get_command_status(self, command_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a command."""
        try:
            # Try cache first
            cached_command = await self.redis_client.get(f"command:{command_id}")
            
            if cached_command:
                command_data = json.loads(cached_command)
                command_data["cached"] = True
                return command_data
            
            # Get from database
            return await self.db_manager.get_command(command_id)
            
        except Exception as e:
            self.logger.error("Error getting command status",
                            command_id=command_id, error=str(e))
            return None
    
    async def cleanup_expired_commands(self) -> int:
        """Clean up expired commands."""
        try:
            # Get all command keys from Redis
            command_keys = await self.redis_client.keys("command:*")
            expired_count = 0
            
            for key in command_keys:
                # Check if key still exists (not expired)
                exists = await self.redis_client.exists(key)
                if not exists:
                    # Command has expired, mark as timeout in database
                    command_id = key.decode().split(":", 1)[1]
                    await self.db_manager.update_command_result(
                        command_id,
                        False,
                        None,
                        "Command timed out"
                    )
                    expired_count += 1
            
            if expired_count > 0:
                self.logger.info("Cleaned up expired commands", count=expired_count)
            
            return expired_count
            
        except Exception as e:
            self.logger.error("Error cleaning up expired commands", error=str(e))
            return 0
    
    async def get_agent_command_queue_length(self, agent_id: str) -> int:
        """Get the length of an agent's command queue."""
        try:
            length = await self.redis_client.llen(f"agent_commands:{agent_id}")
            return length
            
        except Exception as e:
            self.logger.error("Error getting command queue length",
                            agent_id=agent_id, error=str(e))
            return 0
    
    async def clear_agent_command_queue(self, agent_id: str) -> bool:
        """Clear an agent's command queue."""
        try:
            # Get all commands in queue
            command_ids = await self.redis_client.lrange(f"agent_commands:{agent_id}", 0, -1)
            
            # Mark them as failed in database
            for command_id in command_ids:
                await self.db_manager.update_command_result(
                    command_id.decode(),
                    False,
                    None,
                    "Queue cleared by administrator"
                )
            
            # Clear the queue
            await self.redis_client.delete(f"agent_commands:{agent_id}")
            
            self.logger.info("Agent command queue cleared",
                           agent_id=agent_id, count=len(command_ids))
            
            return True
            
        except Exception as e:
            self.logger.error("Error clearing agent command queue",
                            agent_id=agent_id, error=str(e))
            return False
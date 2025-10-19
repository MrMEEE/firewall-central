#!/usr/bin/env python3
"""
Firewalld Agent - Manages local firewall configuration.

This agent can operate in two modes:
1. Pull mode: Periodically contacts the central server for configuration updates
2. Push mode: Exposes an API for the central server to push configurations
"""

import os
import sys
import asyncio
import signal
import socket
import subprocess
from datetime import datetime
from typing import Dict, List, Optional, Any
import httpx
import structlog
from pathlib import Path

# Add parent directory to path for shared imports
sys.path.append(str(Path(__file__).parent.parent))

from shared.models import (
    AgentInfo, AgentMode, AgentStatus, FirewallConfiguration,
    FirewallZoneConfig, AgentCommand, CommandResult, ApiResponse
)
from shared.config import AgentConfig, load_yaml_config
from shared.logging_config import setup_logging, get_logger
from shared.crypto import setup_ssl_context, get_local_ip

from firewalld_manager import FirewalldManager


class FirewalldAgent:
    """Main agent class for firewalld management."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        self.logger = get_logger("firewalld_agent")
        self.firewalld = FirewalldManager()
        self.running = False
        self.agent_id = self._get_agent_id()
        self.ssl_context = None
        
        # Setup logging
        setup_logging(
            log_level=self.config.log_level,
            log_file=self.config.log_file,
            component_name="firewalld_agent"
        )
        
        self.logger.info("Agent initialized", agent_id=self.agent_id, mode=self.config.mode)
    
    def _load_config(self) -> AgentConfig:
        """Load agent configuration."""
        yaml_config = load_yaml_config(self.config_path)
        
        # Override with YAML values
        config_dict = {}
        for key, value in yaml_config.items():
            config_dict[key] = value
        
        return AgentConfig(**config_dict)
    
    def _get_agent_id(self) -> str:
        """Get or generate agent ID."""
        if self.config.agent_id:
            return self.config.agent_id
        
        # Generate based on hostname and MAC address
        hostname = self.config.hostname or socket.gethostname()
        try:
            # Get MAC address of first network interface
            import uuid
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) 
                           for elements in range(0,2*6,2)][::-1])
            agent_id = f"{hostname}-{mac.replace(':', '')[:8]}"
        except:
            agent_id = f"{hostname}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        return agent_id
    
    def _setup_ssl(self) -> None:
        """Setup SSL context for secure communication."""
        if os.path.exists(self.config.ssl_cert_path) and os.path.exists(self.config.ssl_key_path):
            self.ssl_context = setup_ssl_context(
                self.config.ssl_cert_path,
                self.config.ssl_key_path,
                self.config.ca_cert_path if os.path.exists(self.config.ca_cert_path) else None
            )
            self.logger.info("SSL context configured")
        else:
            self.logger.warning("SSL certificates not found, using insecure connection")
    
    async def register_with_server(self) -> bool:
        """Register this agent with the central server."""
        try:
            registration_data = {
                "hostname": socket.gethostname(),
                "ip_address": get_local_ip(),
                "mode": self.config.mode,
                "agent_id": self.agent_id
            }
            
            async with httpx.AsyncClient(verify=False, timeout=self.config.connection_timeout) as client:
                response = await client.post(
                    f"{self.config.server_url}/api/agents/register",
                    json=registration_data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    self.logger.info("Successfully registered with server", 
                                   agent_id=self.agent_id,
                                   server_response=result)
                    
                    # Save any certificates or configuration returned by server
                    if "certificate" in result.get("data", {}):
                        await self._save_certificate(result["data"]["certificate"])
                    
                    return True
                else:
                    self.logger.error("Failed to register with server",
                                    status_code=response.status_code,
                                    response=response.text)
                    return False
                    
        except Exception as e:
            self.logger.error("Error registering with server", error=str(e))
            return False
    
    async def _save_certificate(self, cert_data: Dict[str, str]) -> None:
        """Save certificate data to files."""
        cert_dir = os.path.dirname(self.config.ssl_cert_path)
        os.makedirs(cert_dir, exist_ok=True)
        
        if "certificate" in cert_data:
            with open(self.config.ssl_cert_path, 'w') as f:
                f.write(cert_data["certificate"])
        
        if "private_key" in cert_data:
            with open(self.config.ssl_key_path, 'w') as f:
                f.write(cert_data["private_key"])
            os.chmod(self.config.ssl_key_path, 0o600)
        
        if "ca_certificate" in cert_data:
            with open(self.config.ca_cert_path, 'w') as f:
                f.write(cert_data["ca_certificate"])
        
        self.logger.info("Certificates saved successfully")
    
    async def send_heartbeat(self) -> bool:
        """Send heartbeat to server."""
        try:
            agent_info = AgentInfo(
                agent_id=self.agent_id,
                hostname=socket.gethostname(),
                ip_address=get_local_ip(),
                mode=AgentMode(self.config.mode),
                status=AgentStatus.ONLINE,
                last_seen=datetime.utcnow(),
                version="1.0.0",
                operating_system=self._get_os_info(),
                firewalld_version=self.firewalld.get_version()
            )
            
            async with httpx.AsyncClient(verify=False, timeout=self.config.connection_timeout) as client:
                response = await client.post(
                    f"{self.config.server_url}/api/agents/{self.agent_id}/heartbeat",
                    json=agent_info.dict()
                )
                
                return response.status_code == 200
                
        except Exception as e:
            self.logger.error("Error sending heartbeat", error=str(e))
            return False
    
    def _get_os_info(self) -> str:
        """Get operating system information."""
        try:
            import platform
            return f"{platform.system()} {platform.release()}"
        except:
            return "Unknown"
    
    async def check_for_commands(self) -> List[AgentCommand]:
        """Check for pending commands from the server."""
        try:
            async with httpx.AsyncClient(verify=False, timeout=self.config.connection_timeout) as client:
                response = await client.get(
                    f"{self.config.server_url}/api/agents/{self.agent_id}/commands"
                )
                
                if response.status_code == 200:
                    data = response.json()
                    commands = []
                    for cmd_data in data.get("commands", []):
                        commands.append(AgentCommand(**cmd_data))
                    return commands
                else:
                    return []
                    
        except Exception as e:
            self.logger.error("Error checking for commands", error=str(e))
            return []
    
    async def execute_command(self, command: AgentCommand) -> CommandResult:
        """Execute a command and return the result."""
        self.logger.info("Executing command", 
                        command_id=command.command_id,
                        command_type=command.command_type)
        
        try:
            result_data = None
            
            if command.command_type == "apply_configuration":
                config = FirewallConfiguration(**command.parameters)
                success = await self.firewalld.apply_configuration(config)
                result_data = {"applied": success}
                
            elif command.command_type == "get_status":
                result_data = await self.firewalld.get_status()
                success = True
                
            elif command.command_type == "reload":
                success = await self.firewalld.reload()
                result_data = {"reloaded": success}
                
            elif command.command_type == "add_rule":
                zone = command.parameters.get("zone")
                rule_type = command.parameters.get("rule_type")
                rule_data = command.parameters.get("rule_data")
                success = await self.firewalld.add_rule(zone, rule_type, rule_data)
                result_data = {"rule_added": success}
                
            elif command.command_type == "remove_rule":
                zone = command.parameters.get("zone")
                rule_type = command.parameters.get("rule_type")
                rule_data = command.parameters.get("rule_data")
                success = await self.firewalld.remove_rule(zone, rule_type, rule_data)
                result_data = {"rule_removed": success}
                
            else:
                success = False
                result_data = {"error": f"Unknown command type: {command.command_type}"}
            
            return CommandResult(
                command_id=command.command_id,
                agent_id=self.agent_id,
                success=success,
                result=result_data
            )
            
        except Exception as e:
            self.logger.error("Error executing command",
                            command_id=command.command_id,
                            error=str(e))
            
            return CommandResult(
                command_id=command.command_id,
                agent_id=self.agent_id,
                success=False,
                error=str(e)
            )
    
    async def send_command_result(self, result: CommandResult) -> bool:
        """Send command result back to server."""
        try:
            async with httpx.AsyncClient(verify=False, timeout=self.config.connection_timeout) as client:
                response = await client.post(
                    f"{self.config.server_url}/api/commands/{result.command_id}/result",
                    json=result.dict()
                )
                
                return response.status_code == 200
                
        except Exception as e:
            self.logger.error("Error sending command result", error=str(e))
            return False
    
    async def pull_mode_loop(self) -> None:
        """Main loop for pull mode operation."""
        self.logger.info("Starting pull mode loop")
        
        # Initial registration
        if not await self.register_with_server():
            self.logger.error("Failed to register with server, exiting")
            return
        
        while self.running:
            try:
                # Send heartbeat
                await self.send_heartbeat()
                
                # Check for commands
                commands = await self.check_for_commands()
                
                # Execute commands
                for command in commands:
                    result = await self.execute_command(command)
                    await self.send_command_result(result)
                
                # Wait before next poll
                await asyncio.sleep(self.config.poll_interval)
                
            except Exception as e:
                self.logger.error("Error in pull mode loop", error=str(e))
                await asyncio.sleep(5)  # Short delay before retry
    
    async def start_push_mode_server(self) -> None:
        """Start server for push mode operation."""
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import JSONResponse
        import uvicorn
        
        app = FastAPI(title="Firewalld Agent", version="1.0.0")
        
        @app.post("/api/commands")
        async def receive_command(command: AgentCommand):
            try:
                result = await self.execute_command(command)
                return result.dict()
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.get("/api/status")
        async def get_status():
            try:
                status = await self.firewalld.get_status()
                agent_info = AgentInfo(
                    agent_id=self.agent_id,
                    hostname=socket.gethostname(),
                    ip_address=get_local_ip(),
                    mode=AgentMode.PUSH,
                    status=AgentStatus.ONLINE,
                    last_seen=datetime.utcnow(),
                    version="1.0.0",
                    operating_system=self._get_os_info(),
                    firewalld_version=self.firewalld.get_version()
                )
                
                return {
                    "agent_info": agent_info.dict(),
                    "firewall_status": status
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        # Register with server
        if not await self.register_with_server():
            self.logger.error("Failed to register with server")
        
        self.logger.info("Starting push mode server", 
                        host=self.config.listen_host,
                        port=self.config.listen_port)
        
        config = uvicorn.Config(
            app,
            host=self.config.listen_host,
            port=self.config.listen_port,
            ssl_keyfile=self.config.ssl_key_path if os.path.exists(self.config.ssl_key_path) else None,
            ssl_certfile=self.config.ssl_cert_path if os.path.exists(self.config.ssl_cert_path) else None,
            log_level="info"
        )
        
        server = uvicorn.Server(config)
        await server.serve()
    
    async def start(self) -> None:
        """Start the agent."""
        self.running = True
        self._setup_ssl()
        
        # Check firewalld availability
        if not self.firewalld.is_available():
            self.logger.error("Firewalld is not available on this system")
            return
        
        if self.config.mode == "pull":
            await self.pull_mode_loop()
        elif self.config.mode == "push":
            await self.start_push_mode_server()
        else:
            self.logger.error("Invalid mode specified", mode=self.config.mode)
    
    def stop(self) -> None:
        """Stop the agent."""
        self.logger.info("Stopping agent")
        self.running = False


def signal_handler(agent: FirewalldAgent):
    """Handle shutdown signals."""
    def handler(signum, frame):
        agent.stop()
    return handler


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Firewalld Agent")
    parser.add_argument("-c", "--config", default="config.yaml",
                       help="Configuration file path")
    args = parser.parse_args()
    
    agent = FirewalldAgent(args.config)
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler(agent))
    signal.signal(signal.SIGTERM, signal_handler(agent))
    
    try:
        await agent.start()
    except KeyboardInterrupt:
        agent.stop()
    except Exception as e:
        agent.logger.error("Fatal error", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
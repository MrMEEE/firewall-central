"""
Connection managers for different agent communication types.
"""
import asyncio
import json
import paramiko
import requests
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from .models import Agent, AgentCommand


class BaseConnectionManager:
    """Base class for agent connection managers."""
    
    def __init__(self, agent: Agent):
        self.agent = agent
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test connection to the agent."""
        raise NotImplementedError
    
    async def execute_command(self, command: str, parameters: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute a firewalld command on the agent."""
        raise NotImplementedError
    
    async def get_firewall_status(self) -> Dict[str, Any]:
        """Get current firewall status from the agent."""
        raise NotImplementedError
    
    async def get_zones(self) -> List[Dict[str, Any]]:
        """Get firewall zones from the agent."""
        raise NotImplementedError
    
    async def get_rules(self) -> List[Dict[str, Any]]:
        """Get firewall rules from the agent."""
        raise NotImplementedError
    
    async def get_available_services(self) -> List[str]:
        """Get list of available firewalld services."""
        raise NotImplementedError


class SSHConnectionManager(BaseConnectionManager):
    """SSH-based connection manager."""
    
    def __init__(self, agent: Agent):
        super().__init__(agent)
        self.ssh_client = None
    
    def _get_ssh_connection(self):
        """Get SSH connection to the agent."""
        if self.ssh_client is None:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            connect_kwargs = {
                'hostname': self.agent.ip_address,
                'port': self.agent.port,
                'username': self.agent.ssh_username,
                'timeout': 30,
            }
            
            if self.agent.ssh_key_path:
                connect_kwargs['key_filename'] = self.agent.ssh_key_path
            elif self.agent.ssh_password:
                connect_kwargs['password'] = self.agent.ssh_password
            
            self.ssh_client.connect(**connect_kwargs)
        
        return self.ssh_client
    
    def _execute_ssh_command(self, command: str) -> Tuple[str, str, int]:
        """Execute command via SSH."""
        ssh = self._get_ssh_connection()
        stdin, stdout, stderr = ssh.exec_command(command)
        
        exit_code = stdout.channel.recv_exit_status()
        stdout_text = stdout.read().decode('utf-8', errors='ignore')
        stderr_text = stderr.read().decode('utf-8', errors='ignore')
        
        return stdout_text, stderr_text, exit_code
    
    def _detect_os_info(self) -> Optional[str]:
        """Detect operating system from /etc files."""
        try:
            # Try /etc/os-release first (most modern distros)
            stdout, stderr, exit_code = self._execute_ssh_command('cat /etc/os-release 2>/dev/null')
            if exit_code == 0 and stdout:
                # Parse PRETTY_NAME or NAME and VERSION
                for line in stdout.split('\n'):
                    if line.startswith('PRETTY_NAME='):
                        return line.split('=', 1)[1].strip('"')
                    
            # Try /etc/redhat-release (RHEL, CentOS, Fedora)
            stdout, stderr, exit_code = self._execute_ssh_command('cat /etc/redhat-release 2>/dev/null')
            if exit_code == 0 and stdout:
                return stdout.strip()
            
            # Try /etc/lsb-release (Ubuntu, Debian)
            stdout, stderr, exit_code = self._execute_ssh_command('cat /etc/lsb-release 2>/dev/null')
            if exit_code == 0 and stdout:
                for line in stdout.split('\n'):
                    if line.startswith('DISTRIB_DESCRIPTION='):
                        return line.split('=', 1)[1].strip('"')
            
            # Try /etc/issue as last resort
            stdout, stderr, exit_code = self._execute_ssh_command('cat /etc/issue 2>/dev/null | head -n1')
            if exit_code == 0 and stdout:
                # Clean up escape sequences and extra text
                os_info = stdout.strip().split('\\')[0].strip()
                if os_info and os_info != '':
                    return os_info
            
            return None
        except Exception as e:
            # If detection fails, return None rather than raising
            return None
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test SSH connection to agent."""
        try:
            # Test basic connectivity
            stdout, stderr, exit_code = self._execute_ssh_command('echo "test"')
            
            if exit_code != 0:
                return {
                    'success': False,
                    'error': f'SSH test command failed: {stderr}'
                }
            
            # Test firewalld availability
            stdout, stderr, exit_code = self._execute_ssh_command('systemctl is-active firewalld')
            firewalld_active = stdout.strip() == 'active'
            
            # Test firewall-cmd availability
            stdout, stderr, exit_code = self._execute_ssh_command('which firewall-cmd')
            firewall_cmd_available = exit_code == 0
            
            # Detect OS information
            os_info = self._detect_os_info()
            if os_info:
                # Update agent's operating_system field
                from django.db import connection
                from django.db.utils import OperationalError
                try:
                    self.agent.operating_system = os_info
                    self.agent.save(update_fields=['operating_system'])
                except (OperationalError, Exception):
                    # If save fails, continue without updating
                    pass
            
            return {
                'success': True,
                'connection_type': 'SSH',
                'firewalld_active': firewalld_active,
                'firewall_cmd_available': firewall_cmd_available,
                'operating_system': os_info,
                'message': f'SSH connection successful. Firewalld active: {firewalld_active}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'SSH connection failed: {str(e)}'
            }
    
    async def execute_command(self, command: str, parameters: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute firewalld command via SSH."""
        try:
            # Build firewall-cmd command
            cmd_parts = ['firewall-cmd']
            
            # Normalize command names (handle both hyphen and underscore)
            command = command.replace('-', '_')
            
            if command == 'get_zones':
                cmd_parts.append('--get-zones')
            elif command == 'get_default_zone':
                cmd_parts.append('--get-default-zone')
            elif command == 'list_all':
                cmd_parts.append('--list-all')
            elif command == 'add_service':
                service = parameters.get('service') if parameters else None
                zone = parameters.get('zone') if parameters else None
                permanent = parameters.get('permanent', True) if parameters else True
                if permanent:
                    cmd_parts.append('--permanent')
                if zone:
                    cmd_parts.extend(['--zone', zone])
                if service:
                    cmd_parts.extend(['--add-service', service])
            elif command == 'remove_service':
                service = parameters.get('service') if parameters else None
                zone = parameters.get('zone') if parameters else None
                permanent = parameters.get('permanent', True) if parameters else True
                if permanent:
                    cmd_parts.append('--permanent')
                if zone:
                    cmd_parts.extend(['--zone', zone])
                if service:
                    cmd_parts.extend(['--remove-service', service])
            elif command == 'add_port':
                port = parameters.get('port') if parameters else None
                zone = parameters.get('zone') if parameters else None
                permanent = parameters.get('permanent', True) if parameters else True
                if permanent:
                    cmd_parts.append('--permanent')
                if zone:
                    cmd_parts.extend(['--zone', zone])
                if port:
                    cmd_parts.extend(['--add-port', port])
            elif command == 'remove_port':
                port = parameters.get('port') if parameters else None
                zone = parameters.get('zone') if parameters else None
                permanent = parameters.get('permanent', True) if parameters else True
                if permanent:
                    cmd_parts.append('--permanent')
                if zone:
                    cmd_parts.extend(['--zone', zone])
                if port:
                    cmd_parts.extend(['--remove-port', port])
            elif command == 'new_zone':
                zone = parameters.get('zone') if parameters else None
                permanent = parameters.get('permanent', True) if parameters else True
                if permanent:
                    cmd_parts.append('--permanent')
                if zone:
                    cmd_parts.extend(['--new-zone', zone])
            elif command == 'delete_zone':
                zone = parameters.get('zone') if parameters else None
                permanent = parameters.get('permanent', True) if parameters else True
                if permanent:
                    cmd_parts.append('--permanent')
                if zone:
                    cmd_parts.extend(['--delete-zone', zone])
            elif command == 'reload':
                cmd_parts.append('--reload')
            # Add more commands as needed
            
            firewall_cmd = ' '.join(cmd_parts)
            stdout, stderr, exit_code = self._execute_ssh_command(firewall_cmd)
            
            # If this was a permanent change, reload firewalld to apply changes
            needs_reload = command in ['add_service', 'remove_service', 'add_port', 'remove_port', 'new_zone', 'delete_zone']
            permanent = parameters.get('permanent', True) if parameters else True
            
            if exit_code == 0 and needs_reload and permanent:
                reload_stdout, reload_stderr, reload_exit = self._execute_ssh_command('firewall-cmd --reload')
                if reload_exit != 0:
                    stdout += f"\nReload warning: {reload_stderr}"
            
            # Log the command
            AgentCommand.objects.create(
                agent=self.agent,
                command=command,
                parameters=json.dumps(parameters) if parameters else '',
                result=stdout if exit_code == 0 else stderr,
                status='completed' if exit_code == 0 else 'failed'
            )
            
            return {
                'success': exit_code == 0,
                'output': stdout if exit_code == 0 else stderr,
                'command': firewall_cmd
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_firewall_status(self) -> Dict[str, Any]:
        """Get firewall status via SSH."""
        try:
            stdout, stderr, exit_code = self._execute_ssh_command('firewall-cmd --state')
            
            if exit_code == 0:
                state = stdout.strip()
                return {
                    'success': True,
                    'state': state,
                    'active': state == 'running'
                }
            else:
                return {
                    'success': False,
                    'error': stderr
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_zones(self) -> List[Dict[str, Any]]:
        """Get firewall zones via SSH."""
        try:
            # Detect and update OS info if not already set
            if not self.agent.operating_system or self.agent.operating_system == 'Unknown':
                os_info = self._detect_os_info()
                if os_info:
                    try:
                        from django.db import connection
                        from django.db.utils import OperationalError
                        self.agent.operating_system = os_info
                        self.agent.save(update_fields=['operating_system'])
                    except (OperationalError, Exception):
                        pass
            
            stdout, stderr, exit_code = self._execute_ssh_command('firewall-cmd --get-zones')
            
            if exit_code == 0:
                zones = stdout.strip().split()
                zone_list = []
                
                for zone in zones:
                    # Get detailed info for each zone
                    stdout, stderr, exit_code = self._execute_ssh_command(f'firewall-cmd --zone={zone} --list-all')
                    zone_list.append({
                        'name': zone,
                        'details': stdout if exit_code == 0 else 'Error getting details'
                    })
                
                return zone_list
            else:
                return []
        except Exception as e:
            return []
    
    async def get_rules(self) -> List[Dict[str, Any]]:
        """Get firewall rules via SSH."""
        try:
            rules = []
            zones = await self.get_zones()
            
            for zone_data in zones:
                zone = zone_data['name']
                # Parse the zone details to extract rules
                details = zone_data.get('details', '')
                
                # This is a simplified parser - in reality you'd want more robust parsing
                for line in details.split('\n'):
                    line = line.strip()
                    if line.startswith('services:'):
                        services = line.replace('services:', '').strip().split()
                        for service in services:
                            if service:
                                rules.append({
                                    'type': 'service',
                                    'zone': zone,
                                    'service': service
                                })
                    elif line.startswith('ports:'):
                        ports = line.replace('ports:', '').strip().split()
                        for port in ports:
                            if port:
                                rules.append({
                                    'type': 'port',
                                    'zone': zone,
                                    'port': port
                                })
            
            return rules
        except Exception as e:
            return []
    
    async def get_available_services(self) -> List[str]:
        """Get list of available firewalld services via SSH."""
        try:
            stdout, stderr, exit_code = self._execute_ssh_command('firewall-cmd --get-services')
            
            if exit_code == 0:
                # Services are returned as space-separated list
                services = stdout.strip().split()
                return sorted(services)  # Return sorted list
            else:
                return []
        except Exception as e:
            return []
    
    def close(self):
        """Close SSH connection."""
        if self.ssh_client:
            self.ssh_client.close()
            self.ssh_client = None


class HTTPAgentConnectionManager(BaseConnectionManager):
    """HTTP-based connection manager for agents that listen for connections."""
    
    def __init__(self, agent: Agent):
        super().__init__(agent)
        self.base_url = f"http://{agent.ip_address}:{agent.agent_port}"
        self.headers = {}
        
        if agent.agent_api_key:
            self.headers['Authorization'] = f'Bearer {agent.agent_api_key}'
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test HTTP connection to agent."""
        try:
            response = requests.get(
                f"{self.base_url}/health", 
                headers=self.headers, 
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'connection_type': 'HTTP Agent',
                    'agent_version': data.get('version', 'Unknown'),
                    'firewalld_available': data.get('firewalld_available', False),
                    'message': 'Agent connection successful'
                }
            else:
                return {
                    'success': False,
                    'error': f'Agent returned status code: {response.status_code}'
                }
        except Exception as e:
            return {
                'success': False,
                'error': f'Agent connection failed: {str(e)}'
            }
    
    async def execute_command(self, command: str, parameters: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute command via HTTP agent."""
        try:
            payload = {
                'command': command,
                'parameters': parameters or {}
            }
            
            response = requests.post(
                f"{self.base_url}/execute",
                json=payload,
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Log the command
                AgentCommand.objects.create(
                    agent=self.agent,
                    command=command,
                    parameters=json.dumps(parameters) if parameters else '',
                    result=json.dumps(data.get('output', '')),
                    status='completed' if data.get('success') else 'failed'
                )
                
                return data
            else:
                return {
                    'success': False,
                    'error': f'HTTP request failed with status: {response.status_code}'
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_firewall_status(self) -> Dict[str, Any]:
        """Get firewall status via HTTP agent."""
        return await self.execute_command('get_status')
    
    async def get_zones(self) -> List[Dict[str, Any]]:
        """Get firewall zones via HTTP agent."""
        result = await self.execute_command('get_zones')
        return result.get('output', []) if result.get('success') else []
    
    async def get_rules(self) -> List[Dict[str, Any]]:
        """Get firewall rules via HTTP agent."""
        result = await self.execute_command('get_rules')
        return result.get('output', []) if result.get('success') else []
    
    async def get_available_services(self) -> List[str]:
        """Get list of available firewalld services via HTTP agent."""
        result = await self.execute_command('get_services')
        return result.get('output', []) if result.get('success') else []


class ServerToAgentConnectionManager(HTTPAgentConnectionManager):
    """Server-to-agent connection manager (extends HTTP agent)."""
    pass


class AgentToServerConnectionManager(BaseConnectionManager):
    """Agent-to-server connection manager (agents connect to us)."""
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test if agent has connected recently."""
        if self.agent.last_seen:
            time_diff = datetime.now() - self.agent.last_seen.replace(tzinfo=None)
            if time_diff < timedelta(minutes=5):
                return {
                    'success': True,
                    'connection_type': 'Agent to Server',
                    'last_seen': self.agent.last_seen.isoformat(),
                    'message': 'Agent connected recently'
                }
        
        return {
            'success': False,
            'error': 'Agent has not connected recently or never connected'
        }
    
    async def execute_command(self, command: str, parameters: Optional[Dict] = None) -> Dict[str, Any]:
        """Queue command for agent to execute on next connection."""
        try:
            # Create a pending command
            agent_command = AgentCommand.objects.create(
                agent=self.agent,
                command=command,
                parameters=json.dumps(parameters) if parameters else '',
                status='pending'
            )
            
            return {
                'success': True,
                'message': 'Command queued for agent',
                'command_id': str(agent_command.id)
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_firewall_status(self) -> Dict[str, Any]:
        """Get firewall status (queued command)."""
        return await self.execute_command('get_status')
    
    async def get_zones(self) -> List[Dict[str, Any]]:
        """Get firewall zones (queued command)."""
        result = await self.execute_command('get_zones')
        return []  # Will be available after agent processes the command
    
    async def get_rules(self) -> List[Dict[str, Any]]:
        """Get firewall rules (queued command)."""
        result = await self.execute_command('get_rules')
        return []  # Will be available after agent processes the command
    
    async def get_available_services(self) -> List[str]:
        """Get list of available firewalld services (queued command)."""
        result = await self.execute_command('get_services')
        return []  # Will be available after agent processes the command


def get_connection_manager(agent: Agent) -> BaseConnectionManager:
    """Factory function to get the appropriate connection manager for an agent."""
    if agent.connection_type == 'ssh':
        return SSHConnectionManager(agent)
    elif agent.connection_type == 'server_to_agent':
        return ServerToAgentConnectionManager(agent)
    else:  # agent_to_server
        return AgentToServerConnectionManager(agent)
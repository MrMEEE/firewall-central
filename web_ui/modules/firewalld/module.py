"""
Firewalld security module implementation.
"""

import subprocess
import shutil
from typing import Dict, List, Any
from shared.modules.base import BaseModule, ModuleCapability, ModuleResult


class FirewalldModule(BaseModule):
    """
    Module for managing firewalld firewall configuration.
    """
    
    @property
    def name(self) -> str:
        return "firewalld"
    
    @property
    def display_name(self) -> str:
        return "Firewalld Firewall"
    
    @property
    def description(self) -> str:
        return "Manage firewall zones, services, ports, and rich rules using firewalld"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def capabilities(self) -> List[ModuleCapability]:
        return [ModuleCapability.FIREWALL]
    
    def get_required_packages(self) -> List[str]:
        return ['firewalld', 'python3-firewall']
    
    def check_availability(self) -> bool:
        """Check if firewalld is installed and accessible."""
        # Check if firewall-cmd exists
        if not shutil.which('firewall-cmd'):
            return False
        
        try:
            # Try to run a simple command
            result = subprocess.run(
                ['firewall-cmd', '--state'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def get_available_actions(self) -> List[str]:
        return [
            # Zone management
            'list_zones',
            'get_zones',
            'get_default_zone',
            'set_default_zone',
            'get_active_zones',
            'get_zone_info',
            
            # Service management
            'list_services',
            'add_service',
            'remove_service',
            'query_service',
            
            # Port management
            'list_ports',
            'add_port',
            'remove_port',
            'query_port',
            
            # Rich rules
            'list_rich_rules',
            'add_rich_rule',
            'remove_rich_rule',
            
            # Masquerading
            'query_masquerade',
            'add_masquerade',
            'remove_masquerade',
            
            # Interface management
            'add_interface',
            'remove_interface',
            'change_interface',
            'query_interface',
            
            # Source management
            'add_source',
            'remove_source',
            'query_source',
            
            # Direct rules
            'get_direct_rules',
            'add_direct_rule',
            'remove_direct_rule',
            
            # Configuration
            'reload',
            'complete_reload',
            'runtime_to_permanent',
            'check_config',
            'get_status',
        ]
    
    def execute_action(self, action: str, parameters: Dict[str, Any]) -> ModuleResult:
        """Execute a firewalld action."""
        try:
            if action == 'get_zones':
                return self._get_zones()
            elif action == 'get_default_zone':
                return self._get_default_zone()
            elif action == 'get_active_zones':
                return self._get_active_zones()
            elif action == 'get_zone_info':
                return self._get_zone_info(parameters.get('zone'))
            elif action == 'add_service':
                return self._add_service(
                    parameters.get('zone'),
                    parameters.get('service'),
                    parameters.get('permanent', False)
                )
            elif action == 'remove_service':
                return self._remove_service(
                    parameters.get('zone'),
                    parameters.get('service'),
                    parameters.get('permanent', False)
                )
            elif action == 'add_port':
                return self._add_port(
                    parameters.get('zone'),
                    parameters.get('port'),
                    parameters.get('protocol', 'tcp'),
                    parameters.get('permanent', False)
                )
            elif action == 'remove_port':
                return self._remove_port(
                    parameters.get('zone'),
                    parameters.get('port'),
                    parameters.get('protocol', 'tcp'),
                    parameters.get('permanent', False)
                )
            elif action == 'add_rich_rule':
                return self._add_rich_rule(
                    parameters.get('zone'),
                    parameters.get('rule'),
                    parameters.get('permanent', False)
                )
            elif action == 'remove_rich_rule':
                return self._remove_rich_rule(
                    parameters.get('zone'),
                    parameters.get('rule'),
                    parameters.get('permanent', False)
                )
            elif action == 'reload':
                return self._reload()
            elif action == 'complete_reload':
                return self._complete_reload()
            elif action == 'runtime_to_permanent':
                return self._runtime_to_permanent()
            elif action == 'check_config':
                return self._check_config()
            elif action == 'get_status':
                return self.get_status()
            else:
                return ModuleResult(
                    success=False,
                    message=f"Unknown action: {action}",
                    error=f"Action '{action}' is not supported"
                )
        
        except Exception as e:
            return ModuleResult(
                success=False,
                message=f"Error executing action {action}",
                error=str(e)
            )
    
    def get_status(self) -> Dict[str, Any]:
        """Get current firewalld status."""
        try:
            result = subprocess.run(
                ['firewall-cmd', '--state'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            running = result.returncode == 0 and 'running' in result.stdout.lower()
            
            status = {
                'running': running,
                'default_zone': None,
                'active_zones': [],
            }
            
            if running:
                # Get default zone
                result = subprocess.run(
                    ['firewall-cmd', '--get-default-zone'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    status['default_zone'] = result.stdout.strip()
                
                # Get active zones
                result = subprocess.run(
                    ['firewall-cmd', '--get-active-zones'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    # Parse active zones output
                    zones = []
                    lines = result.stdout.strip().split('\n')
                    current_zone = None
                    for line in lines:
                        line = line.strip()
                        if line and not line.startswith(' '):
                            current_zone = line
                            zones.append(current_zone)
                    status['active_zones'] = zones
            
            return status
        
        except Exception as e:
            return {'error': str(e), 'running': False}
    
    # Helper methods for specific actions
    def _get_zones(self) -> ModuleResult:
        """Get list of all zones."""
        result = subprocess.run(
            ['firewall-cmd', '--get-zones'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            zones = result.stdout.strip().split()
            return ModuleResult(
                success=True,
                message=f"Found {len(zones)} zones",
                data={'zones': zones}
            )
        else:
            return ModuleResult(
                success=False,
                message="Failed to get zones",
                error=result.stderr
            )
    
    def _get_default_zone(self) -> ModuleResult:
        """Get the default zone."""
        result = subprocess.run(
            ['firewall-cmd', '--get-default-zone'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            zone = result.stdout.strip()
            return ModuleResult(
                success=True,
                message=f"Default zone: {zone}",
                data={'default_zone': zone}
            )
        else:
            return ModuleResult(
                success=False,
                message="Failed to get default zone",
                error=result.stderr
            )
    
    def _get_active_zones(self) -> ModuleResult:
        """Get active zones."""
        result = subprocess.run(
            ['firewall-cmd', '--get-active-zones'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            return ModuleResult(
                success=True,
                message="Retrieved active zones",
                data={'active_zones': result.stdout.strip()}
            )
        else:
            return ModuleResult(
                success=False,
                message="Failed to get active zones",
                error=result.stderr
            )
    
    def _get_zone_info(self, zone: str) -> ModuleResult:
        """Get detailed information about a zone."""
        if not zone:
            return ModuleResult(success=False, message="Zone parameter required", error="Missing zone")
        
        result = subprocess.run(
            ['firewall-cmd', '--zone=' + zone, '--list-all'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            return ModuleResult(
                success=True,
                message=f"Retrieved info for zone {zone}",
                data={'zone_info': result.stdout.strip()}
            )
        else:
            return ModuleResult(
                success=False,
                message=f"Failed to get info for zone {zone}",
                error=result.stderr
            )
    
    def _add_service(self, zone: str, service: str, permanent: bool) -> ModuleResult:
        """Add a service to a zone."""
        cmd = ['firewall-cmd']
        if zone:
            cmd.append(f'--zone={zone}')
        if permanent:
            cmd.append('--permanent')
        cmd.extend(['--add-service=' + service])
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            return ModuleResult(
                success=True,
                message=f"Added service {service} to zone {zone or 'default'}",
                data={'service': service, 'zone': zone, 'permanent': permanent}
            )
        else:
            return ModuleResult(
                success=False,
                message=f"Failed to add service {service}",
                error=result.stderr
            )
    
    def _remove_service(self, zone: str, service: str, permanent: bool) -> ModuleResult:
        """Remove a service from a zone."""
        cmd = ['firewall-cmd']
        if zone:
            cmd.append(f'--zone={zone}')
        if permanent:
            cmd.append('--permanent')
        cmd.extend(['--remove-service=' + service])
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            return ModuleResult(
                success=True,
                message=f"Removed service {service} from zone {zone or 'default'}",
                data={'service': service, 'zone': zone, 'permanent': permanent}
            )
        else:
            return ModuleResult(
                success=False,
                message=f"Failed to remove service {service}",
                error=result.stderr
            )
    
    def _add_port(self, zone: str, port: str, protocol: str, permanent: bool) -> ModuleResult:
        """Add a port to a zone."""
        cmd = ['firewall-cmd']
        if zone:
            cmd.append(f'--zone={zone}')
        if permanent:
            cmd.append('--permanent')
        cmd.extend([f'--add-port={port}/{protocol}'])
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            return ModuleResult(
                success=True,
                message=f"Added port {port}/{protocol} to zone {zone or 'default'}",
                data={'port': port, 'protocol': protocol, 'zone': zone, 'permanent': permanent}
            )
        else:
            return ModuleResult(
                success=False,
                message=f"Failed to add port {port}/{protocol}",
                error=result.stderr
            )
    
    def _remove_port(self, zone: str, port: str, protocol: str, permanent: bool) -> ModuleResult:
        """Remove a port from a zone."""
        cmd = ['firewall-cmd']
        if zone:
            cmd.append(f'--zone={zone}')
        if permanent:
            cmd.append('--permanent')
        cmd.extend([f'--remove-port={port}/{protocol}'])
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            return ModuleResult(
                success=True,
                message=f"Removed port {port}/{protocol} from zone {zone or 'default'}",
                data={'port': port, 'protocol': protocol, 'zone': zone, 'permanent': permanent}
            )
        else:
            return ModuleResult(
                success=False,
                message=f"Failed to remove port {port}/{protocol}",
                error=result.stderr
            )
    
    def _add_rich_rule(self, zone: str, rule: str, permanent: bool) -> ModuleResult:
        """Add a rich rule to a zone."""
        cmd = ['firewall-cmd']
        if zone:
            cmd.append(f'--zone={zone}')
        if permanent:
            cmd.append('--permanent')
        cmd.extend(['--add-rich-rule=' + rule])
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            return ModuleResult(
                success=True,
                message=f"Added rich rule to zone {zone or 'default'}",
                data={'rule': rule, 'zone': zone, 'permanent': permanent}
            )
        else:
            return ModuleResult(
                success=False,
                message="Failed to add rich rule",
                error=result.stderr
            )
    
    def _remove_rich_rule(self, zone: str, rule: str, permanent: bool) -> ModuleResult:
        """Remove a rich rule from a zone."""
        cmd = ['firewall-cmd']
        if zone:
            cmd.append(f'--zone={zone}')
        if permanent:
            cmd.append('--permanent')
        cmd.extend(['--remove-rich-rule=' + rule])
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            return ModuleResult(
                success=True,
                message=f"Removed rich rule from zone {zone or 'default'}",
                data={'rule': rule, 'zone': zone, 'permanent': permanent}
            )
        else:
            return ModuleResult(
                success=False,
                message="Failed to remove rich rule",
                error=result.stderr
            )
    
    def _reload(self) -> ModuleResult:
        """Reload firewalld configuration."""
        result = subprocess.run(
            ['firewall-cmd', '--reload'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return ModuleResult(
                success=True,
                message="Firewalld configuration reloaded",
                data={}
            )
        else:
            return ModuleResult(
                success=False,
                message="Failed to reload firewalld",
                error=result.stderr
            )
    
    def _complete_reload(self) -> ModuleResult:
        """Complete reload of firewalld - recreates all zones, interfaces, and rules."""
        result = subprocess.run(
            ['firewall-cmd', '--complete-reload'],
            capture_output=True,
            text=True,
            timeout=15
        )
        
        if result.returncode == 0:
            return ModuleResult(
                success=True,
                message="Firewalld complete reload successful",
                data={'complete': True}
            )
        else:
            return ModuleResult(
                success=False,
                message="Failed to complete reload firewalld",
                error=result.stderr
            )
    
    def _runtime_to_permanent(self) -> ModuleResult:
        """Save runtime configuration to permanent."""
        result = subprocess.run(
            ['firewall-cmd', '--runtime-to-permanent'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return ModuleResult(
                success=True,
                message="Runtime configuration saved to permanent",
                data={'saved': True}
            )
        else:
            return ModuleResult(
                success=False,
                message="Failed to save runtime to permanent",
                error=result.stderr
            )
    
    def _check_config(self) -> ModuleResult:
        """Check firewalld configuration for errors."""
        result = subprocess.run(
            ['firewall-cmd', '--check-config'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            return ModuleResult(
                success=True,
                message="Configuration is valid",
                data={'valid': True}
            )
        else:
            return ModuleResult(
                success=False,
                message="Configuration has errors",
                error=result.stderr,
                data={'valid': False}
            )
    
    def get_configuration_schema(self) -> Dict[str, Any]:
        """Get configuration schema for firewalld module."""
        return {
            "type": "object",
            "properties": {
                "default_zone": {
                    "type": "string",
                    "description": "Default firewall zone"
                },
                "auto_reload": {
                    "type": "boolean",
                    "description": "Automatically reload after changes",
                    "default": True
                }
            }
        }
    
    def get_module_status(self, agent):
        """
        Get the runtime status of firewalld on the agent.
        
        Args:
            agent: The Agent instance
            
        Returns:
            Dict with status information
        """
        import paramiko
        import json
        from io import StringIO
        
        try:
            # For SSH mode, use paramiko directly (synchronous)
            if agent.connection_type == 'ssh':
                ssh_client = paramiko.SSHClient()
                ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                connect_kwargs = {
                    'hostname': agent.ip_address,
                    'port': agent.port,
                    'username': agent.ssh_username,
                    'timeout': 10,
                }
                
                # Handle SSH private key
                if agent.ssh_private_key:
                    try:
                        key_file = StringIO(agent.ssh_private_key)
                        pkey = paramiko.RSAKey.from_private_key(key_file)
                        connect_kwargs['pkey'] = pkey
                    except Exception:
                        try:
                            key_file = StringIO(agent.ssh_private_key)
                            pkey = paramiko.Ed25519Key.from_private_key(key_file)
                            connect_kwargs['pkey'] = pkey
                        except Exception as e:
                            return {
                                'success': False,
                                'running': False,
                                'error': f'Could not load SSH key: {e}'
                            }
                elif agent.ssh_password:
                    connect_kwargs['password'] = agent.ssh_password
                else:
                    return {
                        'success': False,
                        'running': False,
                        'error': 'No SSH credentials configured'
                    }
                
                ssh_client.connect(**connect_kwargs)
                
                # Execute command (tuxsec user talks to rootd service, no sudo needed)
                command = 'tuxsec-cli execute firewalld get_status'
                stdin, stdout, stderr = ssh_client.exec_command(command)
                exit_code = stdout.channel.recv_exit_status()
                stdout_text = stdout.read().decode('utf-8', errors='ignore')
                stderr_text = stderr.read().decode('utf-8', errors='ignore')
                
                ssh_client.close()
                
                if exit_code == 0:
                    try:
                        response = json.loads(stdout_text)
                        
                        # Handle direct rootd response format: {active: bool, status: string}
                        if 'active' in response and 'status' in response:
                            is_running = response.get('active', False)
                            return {
                                'success': True,
                                'running': is_running,
                                'default_zone': None,
                                'active_zones': [],
                                'error': None if is_running else 'FirewallD is not running'
                            }
                        # Handle wrapped response format: {success: bool, result: {...}}
                        elif response.get('success'):
                            status_data = response.get('result', {})
                            return {
                                'success': True,
                                'running': status_data.get('running', False),
                                'default_zone': status_data.get('default_zone'),
                                'active_zones': status_data.get('active_zones', []),
                                'error': None
                            }
                        else:
                            return {
                                'success': False,
                                'running': False,
                                'error': response.get('error', 'Failed to get status')
                            }
                    except json.JSONDecodeError:
                        return {
                            'success': False,
                            'running': False,
                            'error': f'Invalid JSON response: {stdout_text}'
                        }
                else:
                    return {
                        'success': False,
                        'running': False,
                        'error': f'Command failed (exit {exit_code}): {stderr_text}'
                    }
            else:
                # For pull/push modes, we can't easily check status synchronously
                return {
                    'success': False,
                    'running': None,
                    'error': 'Status check not available for pull/push modes'
                }
        except Exception as e:
            return {
                'success': False,
                'running': False,
                'error': f'Failed to check firewalld status: {str(e)}'
            }
    
    def on_enable(self, agent):
        """
        Called when module is enabled for an agent.
        Automatically syncs firewall configuration.
        
        Args:
            agent: The Agent instance
            
        Returns:
            Dict with success message
        """
        from agents.connection_managers import get_connection_manager
        from modules.firewalld.models import FirewallZone, FirewallRule
        from django.db import transaction
        import asyncio
        import threading
        
        def run_in_thread():
            """Run the async call in a separate thread with its own event loop."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                manager = get_connection_manager(agent)
                zones_data = loop.run_until_complete(manager.get_zones())
                return zones_data
            finally:
                loop.close()
        
        try:
            # Run async code in a separate thread to avoid event loop conflicts
            result_container = []
            error_container = []
            
            def thread_target():
                try:
                    result_container.append(run_in_thread())
                except Exception as e:
                    error_container.append(e)
            
            thread = threading.Thread(target=thread_target)
            thread.start()
            thread.join(timeout=30)  # 30 second timeout
            
            if error_container:
                raise error_container[0]
            
            if not result_container:
                return {
                    'success': False,
                    'error': 'Timeout waiting for zone sync'
                }
            
            zones_data = result_container[0]
            
            if not zones_data:
                return {'message': f'Module "{self.display_name}" enabled for {agent.hostname} (no zones found)'}
            
            # Note: We don't clear existing zones here to avoid conflicts with sync daemon
            # The sync daemon will handle zone updates atomically
            # Just return success message
            return {
                'message': f'Module "{self.display_name}" enabled for {agent.hostname}. Zone sync will be handled by the sync daemon.'
            }
            
        except Exception as e:
            raise Exception(f'Failed to sync firewall configuration: {str(e)}')

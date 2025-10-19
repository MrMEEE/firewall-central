#!/usr/bin/env python3
"""
Example firewalld agent that connects to the central management server.

This agent:
1. Registers with the server
2. Periodically checks in for commands
3. Executes firewalld commands
4. Reports results back to the server

Usage:
    python agent.py --server-url http://localhost:8001 --hostname myhost --ip 192.168.1.100
"""

import argparse
import json
import time
import subprocess
import socket
import platform
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional


class FirewalldAgent:
    def __init__(self, server_url: str, hostname: Optional[str] = None, ip_address: Optional[str] = None):
        self.server_url = server_url.rstrip('/')
        self.hostname = hostname or socket.gethostname()
        self.ip_address = ip_address or self._get_local_ip()
        self.agent_id = None
        self.api_key = None
        self.checkin_interval = 30
        self.running = True
        
    def _get_local_ip(self) -> str:
        """Get the local IP address."""
        try:
            # Connect to a remote address to determine local IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"
    
    def _get_firewalld_version(self) -> str:
        """Get firewalld version."""
        try:
            result = subprocess.run(['firewall-cmd', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return "Unknown"
    
    def _is_firewalld_active(self) -> bool:
        """Check if firewalld is active."""
        try:
            result = subprocess.run(['systemctl', 'is-active', 'firewalld'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0 and result.stdout.strip() == 'active'
        except Exception:
            return False
    
    def register(self) -> bool:
        """Register with the management server."""
        print(f"Registering with server at {self.server_url}...")
        
        payload = {
            'hostname': self.hostname,
            'ip_address': self.ip_address,
            'os_info': f"{platform.system()} {platform.release()}",
            'firewalld_version': self._get_firewalld_version()
        }
        
        try:
            response = requests.post(
                f"{self.server_url}/agents/api/register/",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    self.agent_id = data['agent_id']
                    self.api_key = data['api_key']
                    self.checkin_interval = data.get('checkin_interval', 30)
                    print(f"Successfully registered as agent {self.agent_id}")
                    return True
                else:
                    print(f"Registration failed: {data.get('error')}")
            else:
                print(f"Registration failed with HTTP {response.status_code}")
                
        except Exception as e:
            print(f"Registration error: {e}")
        
        return False
    
    def execute_firewall_command(self, command: str, parameters: Dict) -> Dict[str, Any]:
        """Execute a firewalld command."""
        try:
            if command == 'get_status':
                result = subprocess.run(['firewall-cmd', '--state'], 
                                      capture_output=True, text=True, timeout=30)
                return {
                    'success': result.returncode == 0,
                    'output': {
                        'state': result.stdout.strip() if result.returncode == 0 else 'unknown',
                        'active': result.returncode == 0 and result.stdout.strip() == 'running'
                    }
                }
            
            elif command == 'get_zones':
                result = subprocess.run(['firewall-cmd', '--get-zones'], 
                                      capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    zones = result.stdout.strip().split()
                    zone_details = []
                    for zone in zones:
                        zone_result = subprocess.run(['firewall-cmd', f'--zone={zone}', '--list-all'], 
                                                   capture_output=True, text=True, timeout=30)
                        zone_details.append({
                            'name': zone,
                            'details': zone_result.stdout if zone_result.returncode == 0 else 'Error'
                        })
                    return {
                        'success': True,
                        'output': zone_details
                    }
                else:
                    return {
                        'success': False,
                        'output': result.stderr
                    }
            
            elif command == 'get_rules':
                # Get all zones and their rules
                zones_result = subprocess.run(['firewall-cmd', '--get-zones'], 
                                            capture_output=True, text=True, timeout=30)
                if zones_result.returncode != 0:
                    return {'success': False, 'output': 'Failed to get zones'}
                
                all_rules = []
                zones = zones_result.stdout.strip().split()
                
                for zone in zones:
                    zone_result = subprocess.run(['firewall-cmd', f'--zone={zone}', '--list-all'], 
                                               capture_output=True, text=True, timeout=30)
                    if zone_result.returncode == 0:
                        # Parse zone output for rules
                        lines = zone_result.stdout.split('\n')
                        for line in lines:
                            line = line.strip()
                            if line.startswith('services:'):
                                services = line.replace('services:', '').strip().split()
                                for service in services:
                                    if service:
                                        all_rules.append({
                                            'type': 'service',
                                            'zone': zone,
                                            'service': service
                                        })
                            elif line.startswith('ports:'):
                                ports = line.replace('ports:', '').strip().split()
                                for port in ports:
                                    if port:
                                        all_rules.append({
                                            'type': 'port',
                                            'zone': zone,
                                            'port': port
                                        })
                
                return {
                    'success': True,
                    'output': all_rules
                }
            
            elif command == 'add_service':
                service = parameters.get('service')
                zone = parameters.get('zone', '--zone=public')
                permanent = parameters.get('permanent', True)
                
                if not service:
                    return {'success': False, 'output': 'Missing service parameter'}
                
                cmd = ['firewall-cmd']
                if permanent:
                    cmd.append('--permanent')
                if zone and not zone.startswith('--zone='):
                    cmd.extend(['--zone', zone])
                elif zone:
                    cmd.append(zone)
                cmd.extend(['--add-service', service])
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                # If permanent, reload firewall
                if permanent and result.returncode == 0:
                    subprocess.run(['firewall-cmd', '--reload'], timeout=30)
                
                return {
                    'success': result.returncode == 0,
                    'output': result.stdout if result.returncode == 0 else result.stderr
                }
            
            elif command == 'remove_service':
                service = parameters.get('service')
                zone = parameters.get('zone', '--zone=public')
                permanent = parameters.get('permanent', True)
                
                if not service:
                    return {'success': False, 'output': 'Missing service parameter'}
                
                cmd = ['firewall-cmd']
                if permanent:
                    cmd.append('--permanent')
                if zone and not zone.startswith('--zone='):
                    cmd.extend(['--zone', zone])
                elif zone:
                    cmd.append(zone)
                cmd.extend(['--remove-service', service])
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                # If permanent, reload firewall
                if permanent and result.returncode == 0:
                    subprocess.run(['firewall-cmd', '--reload'], timeout=30)
                
                return {
                    'success': result.returncode == 0,
                    'output': result.stdout if result.returncode == 0 else result.stderr
                }
            
            else:
                return {
                    'success': False,
                    'output': f'Unknown command: {command}'
                }
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'output': 'Command timed out'
            }
        except Exception as e:
            return {
                'success': False,
                'output': str(e)
            }
    
    def checkin(self) -> List[Dict]:
        """Check in with the server and get pending commands."""
        if not self.agent_id or not self.api_key:
            return []
        
        payload = {
            'agent_id': self.agent_id,
            'api_key': self.api_key,
            'status': 'online',
            'firewall_status': {
                'active': self._is_firewalld_active(),
                'version': self._get_firewalld_version()
            }
        }
        
        try:
            response = requests.post(
                f"{self.server_url}/agents/api/checkin/",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    return data.get('commands', [])
                else:
                    print(f"Check-in failed: {data.get('error')}")
            else:
                print(f"Check-in failed with HTTP {response.status_code}")
                
        except Exception as e:
            print(f"Check-in error: {e}")
        
        return []
    
    def report_command_results(self, results: List[Dict]):
        """Report command execution results to the server."""
        if not results:
            return
        
        payload = {
            'agent_id': self.agent_id,
            'api_key': self.api_key,
            'status': 'online',
            'command_results': results
        }
        
        try:
            response = requests.post(
                f"{self.server_url}/agents/api/checkin/",
                json=payload,
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"Failed to report results: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"Error reporting results: {e}")
    
    def run(self):
        """Main agent loop."""
        if not self.register():
            print("Failed to register with server. Exiting.")
            return
        
        print(f"Agent running. Check-in interval: {self.checkin_interval} seconds")
        print("Press Ctrl+C to stop")
        
        try:
            while self.running:
                # Check in with server
                commands = self.checkin()
                
                # Execute any pending commands
                results = []
                for cmd in commands:
                    print(f"Executing command: {cmd['command']}")
                    result = self.execute_firewall_command(cmd['command'], cmd['parameters'])
                    results.append({
                        'command_id': cmd['id'],
                        'success': result['success'],
                        'output': result['output']
                    })
                    print(f"Command result: {'Success' if result['success'] else 'Failed'}")
                
                # Report results if any
                if results:
                    self.report_command_results(results)
                
                # Wait for next check-in
                time.sleep(self.checkin_interval)
                
        except KeyboardInterrupt:
            print("\nShutting down agent...")
            self.running = False
        except Exception as e:
            print(f"Agent error: {e}")


def main():
    parser = argparse.ArgumentParser(description='Firewalld Central Management Agent')
    parser.add_argument('--server-url', required=True, 
                       help='URL of the management server (e.g., http://localhost:8001)')
    parser.add_argument('--hostname', 
                       help='Agent hostname (default: system hostname)')
    parser.add_argument('--ip', dest='ip_address',
                       help='Agent IP address (default: auto-detect)')
    
    args = parser.parse_args()
    
    agent = FirewalldAgent(
        server_url=args.server_url,
        hostname=args.hostname,
        ip_address=args.ip_address
    )
    
    agent.run()


if __name__ == '__main__':
    main()
#!/usr/bin/env python3
"""
HTTP Firewalld Agent that listens for connections from the management server.

This agent:
1. Starts an HTTP server on a specified port
2. Provides health check endpoint
3. Accepts and executes firewalld commands
4. Returns command results via HTTP responses

Usage:
    python http_agent.py --port 8444 --api-key my-secret-key
"""

import argparse
import json
import subprocess
import socket
import platform
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
from typing import Dict, Any


class FirewalldHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for firewalld commands."""
    
    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/health':
            self.handle_health_check()
        else:
            self.send_error(404, "Not Found")
    
    def do_POST(self):
        """Handle POST requests."""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/execute':
            self.handle_execute_command()
        else:
            self.send_error(404, "Not Found")
    
    def handle_health_check(self):
        """Handle health check requests."""
        try:
            firewalld_active = self._is_firewalld_active()
            firewall_cmd_available = self._check_firewall_cmd()
            
            response = {
                'status': 'healthy',
                'version': '1.0.0',
                'hostname': socket.gethostname(),
                'firewalld_available': firewalld_active,
                'firewall_cmd_available': firewall_cmd_available,
                'firewalld_version': self._get_firewalld_version(),
                'os_info': f"{platform.system()} {platform.release()}"
            }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            self.send_error(500, f"Health check failed: {str(e)}")
    
    def handle_execute_command(self):
        """Handle command execution requests."""
        try:
            # Check API key
            if not self._check_auth():
                self.send_error(401, "Unauthorized")
                return
            
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error(400, "Empty request body")
                return
            
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body.decode('utf-8'))
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON")
                return
            
            command = data.get('command')
            parameters = data.get('parameters', {})
            
            if not command:
                self.send_error(400, "Missing command")
                return
            
            # Execute the command
            result = self._execute_firewall_command(command, parameters)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode('utf-8'))
            
        except Exception as e:
            self.send_error(500, f"Command execution failed: {str(e)}")
    
    def _check_auth(self) -> bool:
        """Check API key authentication."""
        auth_header = self.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            return token == getattr(self.server, 'api_key', None)
        return not getattr(self.server, 'api_key', None)  # Allow if no API key configured
    
    def _is_firewalld_active(self) -> bool:
        """Check if firewalld is active."""
        try:
            result = subprocess.run(['systemctl', 'is-active', 'firewalld'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0 and result.stdout.strip() == 'active'
        except Exception:
            return False
    
    def _check_firewall_cmd(self) -> bool:
        """Check if firewall-cmd is available."""
        try:
            result = subprocess.run(['which', 'firewall-cmd'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except Exception:
            return False
    
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
    
    def _execute_firewall_command(self, command: str, parameters: Dict) -> Dict[str, Any]:
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
                zone = parameters.get('zone', 'public')
                permanent = parameters.get('permanent', True)
                
                if not service:
                    return {'success': False, 'output': 'Missing service parameter'}
                
                cmd = ['firewall-cmd']
                if permanent:
                    cmd.append('--permanent')
                cmd.extend(['--zone', zone, '--add-service', service])
                
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
                zone = parameters.get('zone', 'public')
                permanent = parameters.get('permanent', True)
                
                if not service:
                    return {'success': False, 'output': 'Missing service parameter'}
                
                cmd = ['firewall-cmd']
                if permanent:
                    cmd.append('--permanent')
                cmd.extend(['--zone', zone, '--remove-service', service])
                
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


class FirewalldHTTPServer(HTTPServer):
    """HTTP server for firewalld agent."""
    
    def __init__(self, server_address, handler_class, api_key=None):
        super().__init__(server_address, handler_class)
        self.api_key = api_key


def main():
    parser = argparse.ArgumentParser(description='Firewalld HTTP Agent')
    parser.add_argument('--port', type=int, default=8444,
                       help='Port to listen on (default: 8444)')
    parser.add_argument('--host', default='0.0.0.0',
                       help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--api-key',
                       help='API key for authentication (optional)')
    
    args = parser.parse_args()
    
    try:
        server = FirewalldHTTPServer((args.host, args.port), FirewalldHTTPHandler, args.api_key)
        
        print(f"Starting Firewalld HTTP Agent on {args.host}:{args.port}")
        if args.api_key:
            print("API key authentication enabled")
        else:
            print("WARNING: No API key configured - authentication disabled")
        
        print("Available endpoints:")
        print("  GET  /health   - Health check")
        print("  POST /execute  - Execute firewalld command")
        print("\nPress Ctrl+C to stop")
        
        server.serve_forever()
        
    except KeyboardInterrupt:
        print("\nShutting down server...")
    except Exception as e:
        print(f"Server error: {e}")


if __name__ == '__main__':
    main()
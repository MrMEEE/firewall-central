"""
API views for agent communication.
"""
import json
import asyncio
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from .models import Agent, AgentCommand
from .connection_managers import get_connection_manager


@csrf_exempt
@require_http_methods(["POST"])
def agent_checkin(request):
    """
    API endpoint for agents to check in with the server.
    
    Expected payload:
    {
        "agent_id": "uuid-string",
        "api_key": "agent-api-key",
        "status": "online",
        "firewall_status": {...},
        "command_results": [...]  # Results from previously queued commands
    }
    """
    try:
        data = json.loads(request.body)
        agent_id = data.get('agent_id')
        api_key = data.get('api_key')
        
        if not agent_id or not api_key:
            return JsonResponse({
                'success': False,
                'error': 'Missing agent_id or api_key'
            }, status=400)
        
        # Find the agent
        try:
            agent = Agent.objects.get(id=agent_id, agent_api_key=api_key)
        except Agent.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Invalid agent credentials'
            }, status=401)
        
        # Update agent status
        agent.status = data.get('status', 'online')
        agent.last_seen = datetime.now()
        agent.save()
        
        # Process command results if provided
        command_results = data.get('command_results', [])
        for result in command_results:
            command_id = result.get('command_id')
            if command_id:
                try:
                    command = AgentCommand.objects.get(id=command_id, agent=agent)
                    command.result = result.get('output', {})
                    command.status = 'completed' if result.get('success') else 'failed'
                    command.completed_at = datetime.now()
                    command.save()
                except AgentCommand.DoesNotExist:
                    pass
        
        # Get pending commands for the agent
        pending_commands = AgentCommand.objects.filter(
            agent=agent,
            status='pending'
        ).order_by('created_at')
        
        commands_data = []
        for command in pending_commands:
            commands_data.append({
                'id': str(command.id),
                'command': command.command_type,
                'parameters': command.parameters
            })
            # Mark as sent
            command.status = 'sent'
            command.save()
        
        return JsonResponse({
            'success': True,
            'commands': commands_data,
            'server_time': datetime.now().isoformat()
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON payload'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def agent_register(request):
    """
    API endpoint for agents to register with the server.
    
    Expected payload:
    {
        "hostname": "agent-hostname",
        "ip_address": "192.168.1.100",
        "os_info": "Ubuntu 22.04",
        "firewalld_version": "1.2.0"
    }
    """
    try:
        data = json.loads(request.body)
        hostname = data.get('hostname')
        ip_address = data.get('ip_address')
        
        if not hostname or not ip_address:
            return JsonResponse({
                'success': False,
                'error': 'Missing hostname or ip_address'
            }, status=400)
        
        # Check if agent already exists
        existing_agent = Agent.objects.filter(
            hostname=hostname,
            ip_address=ip_address
        ).first()
        
        if existing_agent:
            # Update existing agent
            agent = existing_agent
            agent.operating_system = data.get('os_info', agent.operating_system)
            agent.firewalld_version = data.get('firewalld_version', agent.firewalld_version)
            agent.status = 'online'
            agent.last_seen = datetime.now()
        else:
            # Create new agent
            import uuid
            agent = Agent(
                hostname=hostname,
                ip_address=ip_address,
                connection_type='agent_to_server',
                operating_system=data.get('os_info', ''),
                firewalld_version=data.get('firewalld_version', ''),
                status='online',
                last_seen=datetime.now(),
                agent_api_key=str(uuid.uuid4())
            )
        
        agent.save()
        
        return JsonResponse({
            'success': True,
            'agent_id': str(agent.id),
            'api_key': agent.agent_api_key,
            'checkin_interval': 30  # seconds
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON payload'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class AgentCommandAPI(View):
    """API for executing commands on agents."""
    
    def post(self, request, agent_id):
        """Execute a command on an agent."""
        try:
            data = json.loads(request.body)
            command = data.get('command')
            parameters = data.get('parameters', {})
            
            if not command:
                return JsonResponse({
                    'success': False,
                    'error': 'Missing command'
                }, status=400)
            
            # Get the agent
            try:
                agent = Agent.objects.get(id=agent_id)
            except Agent.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Agent not found'
                }, status=404)
            
            # Get connection manager and execute command
            manager = get_connection_manager(agent)
            
            # For synchronous execution (SSH, HTTP), execute immediately
            if agent.connection_type in ['ssh', 'server_to_agent']:
                result = asyncio.run(manager.execute_command(command, parameters))
                return JsonResponse(result)
            else:
                # For agent-to-server, queue the command
                result = asyncio.run(manager.execute_command(command, parameters))
                return JsonResponse(result)
                
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON payload'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
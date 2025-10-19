from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
import json
import httpx
import asyncio
from datetime import datetime

from .models import Agent, FirewallZone, FirewallRule, AgentConnection, AgentCommand
from .forms import AgentForm, AgentQuickAddForm
from .serializers import (
    AgentSerializer, FirewallZoneSerializer, FirewallRuleSerializer,
    AgentConnectionSerializer, AgentCommandSerializer
)


class AgentViewSet(viewsets.ModelViewSet):
    """ViewSet for managing agents."""
    queryset = Agent.objects.all()
    serializer_class = AgentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Agent.objects.all()
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset


class FirewallZoneViewSet(viewsets.ModelViewSet):
    """ViewSet for managing firewall zones."""
    serializer_class = FirewallZoneSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        agent_id = self.kwargs['agent_id']
        return FirewallZone.objects.filter(agent_id=agent_id)
    
    def perform_create(self, serializer):
        agent_id = self.kwargs['agent_id']
        agent = get_object_or_404(Agent, id=agent_id)
        serializer.save(agent=agent)


class FirewallRuleViewSet(viewsets.ModelViewSet):
    """ViewSet for managing firewall rules."""
    serializer_class = FirewallRuleSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        agent_id = self.kwargs['agent_id']
        return FirewallRule.objects.filter(agent_id=agent_id)
    
    def perform_create(self, serializer):
        agent_id = self.kwargs['agent_id']
        agent = get_object_or_404(Agent, id=agent_id)
        serializer.save(agent=agent, created_by=self.request.user)


class AgentCommandViewSet(viewsets.ModelViewSet):
    """ViewSet for managing agent commands."""
    serializer_class = AgentCommandSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        agent_id = self.kwargs['agent_id']
        return AgentCommand.objects.filter(agent_id=agent_id)
    
    def perform_create(self, serializer):
        agent_id = self.kwargs['agent_id']
        agent = get_object_or_404(Agent, id=agent_id)
        serializer.save(agent=agent, created_by=self.request.user)


class ConnectionListCreateView(APIView):
    """View for listing and creating agent connections."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        connections = AgentConnection.objects.all()
        serializer = AgentConnectionSerializer(connections, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        serializer = AgentConnectionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(created_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ConnectionDetailView(APIView):
    """View for retrieving, updating, and deleting agent connections."""
    permission_classes = [IsAuthenticated]
    
    def get_object(self, connection_id):
        return get_object_or_404(AgentConnection, id=connection_id)
    
    def get(self, request, connection_id):
        connection = self.get_object(connection_id)
        serializer = AgentConnectionSerializer(connection)
        return Response(serializer.data)
    
    def put(self, request, connection_id):
        connection = self.get_object(connection_id)
        serializer = AgentConnectionSerializer(connection, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, connection_id):
        connection = self.get_object(connection_id)
        connection.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def agent_status(request, agent_id):
    """Get real-time status from an agent."""
    agent = get_object_or_404(Agent, id=agent_id)
    
    try:
        # Send status request to agent
        if agent.mode == 'push':
            # Direct communication with agent
            async def get_status():
                async with httpx.AsyncClient() as client:
                    url = f"https://{agent.ip_address}:{agent.port}/api/status"
                    response = await client.get(url, timeout=10, verify=False)
                    return response.json()
            
            # Run async function
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(get_status())
            loop.close()
            
            return JsonResponse(result)
        else:
            # For pull mode, create a command and wait for result
            command = AgentCommand.objects.create(
                agent=agent,
                command_type='get_status',
                parameters={},
                created_by=request.user
            )
            
            return JsonResponse({
                'status': 'command_queued',
                'command_id': str(command.id),
                'message': 'Status request queued for agent'
            })
            
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'status': 'error'
        }, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_agent(request, agent_id):
    """Approve a pending agent."""
    agent = get_object_or_404(Agent, id=agent_id)
    
    if agent.status != 'pending':
        return JsonResponse({
            'error': 'Agent is not in pending status'
        }, status=400)
    
    agent.status = 'approved'
    agent.save()
    
    return JsonResponse({
        'message': 'Agent approved successfully',
        'agent_id': str(agent.id)
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reject_agent(request, agent_id):
    """Reject a pending agent."""
    agent = get_object_or_404(Agent, id=agent_id)
    
    if agent.status != 'pending':
        return JsonResponse({
            'error': 'Agent is not in pending status'
        }, status=400)
    
    agent.status = 'rejected'
    agent.save()
    
    return JsonResponse({
        'message': 'Agent rejected',
        'agent_id': str(agent.id)
    })


# Template views for the web interface
@login_required
def agent_list(request):
    """List view for agents."""
    agents = Agent.objects.all()
    return render(request, 'agents/list.html', {'agents': agents})


@login_required
def agent_detail(request, agent_id):
    """Detail view for a specific agent."""
    agent = get_object_or_404(Agent, id=agent_id)
    zones = agent.zones.all()
    rules = agent.rules.all()
    commands = agent.commands.all()[:10]  # Last 10 commands
    
    return render(request, 'agents/detail.html', {
        'agent': agent,
        'zones': zones,
        'rules': rules,
        'commands': commands,
    })


@login_required
def agent_create(request):
    """Create a new agent."""
    if request.method == 'POST':
        form = AgentForm(request.POST)
        if form.is_valid():
            agent = form.save()
            messages.success(request, f'Agent {agent.hostname} created successfully!')
            return redirect('agent-detail', agent_id=agent.id)
    else:
        form = AgentForm()
    
    return render(request, 'agents/create.html', {'form': form})


@login_required
def agent_edit(request, agent_id):
    """Edit an existing agent."""
    agent = get_object_or_404(Agent, id=agent_id)
    
    if request.method == 'POST':
        form = AgentForm(request.POST, instance=agent)
        if form.is_valid():
            agent = form.save()
            messages.success(request, f'Agent {agent.hostname} updated successfully!')
            return redirect('agent-detail', agent_id=agent.id)
    else:
        form = AgentForm(instance=agent)
    
    return render(request, 'agents/edit.html', {
        'form': form, 
        'agent': agent
    })


@login_required
def agent_quick_add(request):
    """Quick add form for agents with auto-detection."""
    if request.method == 'POST':
        form = AgentQuickAddForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            
            # Create agent with basic info
            agent = Agent.objects.create(
                hostname=data['hostname'],
                ip_address=data['ip_address'],
                connection_type=data['connection_type'] if data['connection_type'] != 'auto' else 'ssh',
                ssh_username=data.get('ssh_username', 'root'),
                description=data.get('description', ''),
            )
            
            # Set appropriate ports based on connection type
            if agent.connection_type == 'ssh':
                agent.port = 22
            elif agent.connection_type == 'server_to_agent':
                agent.port = 8444
            else:  # agent_to_server
                agent.port = 8443
            
            agent.save()
            
            messages.success(request, f'Agent {agent.hostname} added successfully!')
            return redirect('agent-detail', agent_id=agent.id)
    else:
        form = AgentQuickAddForm()
    
    return render(request, 'agents/quick_add.html', {'form': form})


@login_required
@require_http_methods(['POST'])
def agent_test_connection(request, agent_id):
    """Test connection to an agent."""
    agent = get_object_or_404(Agent, id=agent_id)
    
    try:
        # Import connection managers
        from .connection_managers import get_connection_manager
        
        # Get the appropriate connection manager
        manager = get_connection_manager(agent)
        
        # Test the connection
        result = asyncio.run(manager.test_connection())
        
        # Close connection if needed (for SSH)
        if hasattr(manager, 'close') and callable(getattr(manager, 'close')):
            manager.close()
        
        return JsonResponse(result)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Connection test failed: {str(e)}'
        })


def test_ssh_connection(agent):
    """Test SSH connection to agent."""
    import paramiko
    
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        connect_kwargs = {
            'hostname': agent.ip_address,
            'port': agent.port,
            'username': agent.ssh_username,
            'timeout': 10,
        }
        
        if agent.ssh_key_path:
            connect_kwargs['key_filename'] = agent.ssh_key_path
        elif agent.ssh_password:
            connect_kwargs['password'] = agent.ssh_password
        
        ssh.connect(**connect_kwargs)
        
        # Test firewalld availability
        stdin, stdout, stderr = ssh.exec_command('systemctl is-active firewalld')
        firewalld_status = stdout.read().decode().strip()
        
        ssh.close()
        
        return {
            'success': True,
            'connection_type': 'SSH',
            'firewalld_active': firewalld_status == 'active',
            'message': f'SSH connection successful. Firewalld status: {firewalld_status}'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'SSH connection failed: {str(e)}'
        }


def test_agent_connection(agent):
    """Test HTTP connection to agent."""
    import requests
    
    try:
        url = f"http://{agent.ip_address}:{agent.agent_port}/health"
        headers = {}
        
        if agent.agent_api_key:
            headers['Authorization'] = f'Bearer {agent.agent_api_key}'
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return {
                'success': True,
                'connection_type': 'HTTP Agent',
                'agent_version': data.get('version', 'Unknown'),
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


def test_server_connection(agent):
    """Test if agent has connected to server recently."""
    from datetime import datetime, timedelta
    
    if agent.last_seen:
        time_diff = datetime.now() - agent.last_seen.replace(tzinfo=None)
        if time_diff < timedelta(minutes=5):
            return {
                'success': True,
                'connection_type': 'Agent to Server',
                'last_seen': agent.last_seen.isoformat(),
                'message': 'Agent connected recently'
            }
    
    return {
        'success': False,
        'error': 'Agent has not connected recently or never connected'
    }
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
from .connection_managers import get_connection_manager


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


@login_required
def agent_zones_data(request, agent_id):
    """Get agent zones and rules data for dynamic updates."""
    agent = get_object_or_404(Agent, id=agent_id)
    zones = agent.zones.all()
    
    zones_data = []
    for zone in zones:
        zones_data.append({
            'id': zone.id,
            'name': zone.name,
            'services': zone.services,
            'ports': zone.ports,
            'interfaces': zone.interfaces,
            'sources': zone.sources,
            'masquerade': zone.masquerade,
            'target': zone.target,
            'description': zone.description,
        })
    
    # Also get all rules grouped by service/port name
    rules = agent.rules.all()
    rules_by_name = {}
    
    for rule in rules:
        if rule.rule_type == 'service':
            key = f"service:{rule.service}"
            name = rule.service
        elif rule.rule_type == 'port':
            key = f"port:{rule.port}/{rule.protocol}"
            name = f"{rule.port}/{rule.protocol}"
        else:
            continue
            
        if key not in rules_by_name:
            rules_by_name[key] = {
                'name': name,
                'type': rule.rule_type,
                'zones': [],
                'count': 0
            }
        
        rules_by_name[key]['zones'].append({
            'zone_id': rule.zone.id,
            'zone_name': rule.zone.name,
            'rule_id': str(rule.id)
        })
        rules_by_name[key]['count'] += 1
    
    return JsonResponse({
        'success': True,
        'zones': zones_data,
        'rules_grouped': list(rules_by_name.values()),
        'last_sync': agent.last_sync.isoformat() if agent.last_sync else None,
        'zones_count': zones.count()
    })


@login_required
def agent_available_services(request, agent_id):
    """Get list of available firewalld services for this agent."""
    agent = get_object_or_404(Agent, id=agent_id)
    
    return JsonResponse({
        'success': True,
        'services': agent.available_services if agent.available_services else []
    })


@login_required
@require_http_methods(['POST'])
def agent_sync_firewall(request, agent_id):
    """Bidirectional sync: Push interface changes to agent, then pull current state."""
    agent = get_object_or_404(Agent, id=agent_id)
    
    try:
        # Get the appropriate connection manager
        manager = get_connection_manager(agent)
        
        # STEP 1: Apply all pending changes from interface to agent
        zones_in_db = FirewallZone.objects.filter(agent=agent)
        
        for zone in zones_in_db:
            # Ensure zone exists on agent (get_zones will tell us)
            pass  # We'll verify after getting zones
        
        # STEP 2: Get current state from agent
        zones_data = asyncio.run(manager.get_zones())
        
        if not zones_data:
            return JsonResponse({
                'success': False,
                'error': 'Failed to retrieve zones from agent'
            })
        
        # STEP 2.5: Get available services from agent and store them
        try:
            available_services = asyncio.run(manager.get_available_services())
            if available_services:
                agent.available_services = available_services
                # Don't save yet, we'll save at the end
        except:
            # If we can't get services, just continue with empty list
            pass
        
        # STEP 3: Build a map of what's on the agent
        agent_zones = {}
        for zone_info in zones_data:
            zone_name = zone_info.get('name', '')
            zone_details = zone_info.get('details', '')
            
            if not zone_name:
                continue
            
            # Parse zone details
            services = []
            ports = []
            interfaces = []
            sources = []
            masquerade = False
            target = 'default'
            
            for line in zone_details.split('\n'):
                line = line.strip()
                if line.startswith('services:'):
                    services = [s for s in line.replace('services:', '').strip().split() if s]
                elif line.startswith('ports:'):
                    ports = [p for p in line.replace('ports:', '').strip().split() if p]
                elif line.startswith('interfaces:'):
                    interfaces = [i for i in line.replace('interfaces:', '').strip().split() if i]
                elif line.startswith('sources:'):
                    sources = [s for s in line.replace('sources:', '').strip().split() if s]
                elif line.startswith('masquerade:'):
                    masquerade = 'yes' in line.lower()
                elif line.startswith('target:'):
                    target = line.replace('target:', '').strip()
            
            agent_zones[zone_name] = {
                'target': target,
                'interfaces': interfaces,
                'sources': sources,
                'services': services,
                'ports': ports,
                'masquerade': masquerade
            }
        
        # STEP 4: Sync interface changes to agent
        changes_applied = 0
        for zone in zones_in_db:
            if zone.name not in agent_zones:
                # Zone doesn't exist on agent, skip (we'll handle zone creation separately)
                continue
            
            agent_zone = agent_zones[zone.name]
            
            # Sync services: add missing ones to agent
            for service in zone.services:
                if service not in agent_zone['services']:
                    try:
                        asyncio.run(manager.execute_command('add-service', {
                            'service': service,
                            'zone': zone.name
                        }))
                        changes_applied += 1
                    except:
                        pass  # Continue even if one fails
            
            # Sync ports: add missing ones to agent
            for port_spec in zone.ports:
                if port_spec not in agent_zone['ports']:
                    try:
                        asyncio.run(manager.execute_command('add-port', {
                            'port': port_spec,
                            'zone': zone.name
                        }))
                        changes_applied += 1
                    except:
                        pass
        
        # STEP 5: Re-fetch zones after applying changes
        zones_data = asyncio.run(manager.get_zones())
        
        # STEP 6: Clear and rebuild database with current agent state
        FirewallZone.objects.filter(agent=agent).delete()
        
        zones_created = 0
        rules_created = 0
        
        # Process each zone
        for zone_info in zones_data:
            zone_name = zone_info.get('name', '')
            zone_details = zone_info.get('details', '')
            
            if not zone_name:
                continue
            
            # Parse zone details
            services = []
            ports = []
            interfaces = []
            sources = []
            masquerade = False
            target = 'default'
            
            for line in zone_details.split('\n'):
                line = line.strip()
                if line.startswith('services:'):
                    services = [s for s in line.replace('services:', '').strip().split() if s]
                elif line.startswith('ports:'):
                    ports = [p for p in line.replace('ports:', '').strip().split() if p]
                elif line.startswith('interfaces:'):
                    interfaces = [i for i in line.replace('interfaces:', '').strip().split() if i]
                elif line.startswith('sources:'):
                    sources = [s for s in line.replace('sources:', '').strip().split() if s]
                elif line.startswith('masquerade:'):
                    masquerade = 'yes' in line.lower()
                elif line.startswith('target:'):
                    target = line.replace('target:', '').strip()
            
            # Create zone
            zone = FirewallZone.objects.create(
                agent=agent,
                name=zone_name,
                target=target,
                interfaces=interfaces,
                sources=sources,
                services=services,
                ports=ports,
                masquerade=masquerade
            )
            zones_created += 1
            
            # Create rules for services
            for service in services:
                FirewallRule.objects.create(
                    agent=agent,
                    zone=zone,
                    rule_type='service',
                    service=service,
                    enabled=True,
                    permanent=True,
                    created_by=request.user
                )
                rules_created += 1
            
            # Create rules for ports
            for port_spec in ports:
                # Parse port specification (e.g., "80/tcp", "8080-8090/udp")
                if '/' in port_spec:
                    port, protocol = port_spec.split('/', 1)
                else:
                    port, protocol = port_spec, 'tcp'
                
                FirewallRule.objects.create(
                    agent=agent,
                    zone=zone,
                    rule_type='port',
                    port=port,
                    protocol=protocol,
                    enabled=True,
                    permanent=True,
                    created_by=request.user
                )
                rules_created += 1
        
        # Close connection if needed
        if hasattr(manager, 'close') and callable(getattr(manager, 'close')):
            manager.close()
        
        # Update agent status and sync time
        agent.last_seen = datetime.now()
        agent.last_sync = datetime.now()
        agent.status = 'online'
        agent.save()
        
        message = f'Successfully synced {zones_created} zones and {rules_created} rules'
        if changes_applied > 0:
            message += f'. Applied {changes_applied} changes to agent'
        
        return JsonResponse({
            'success': True,
            'message': message,
            'zones_created': zones_created,
            'rules_created': rules_created,
            'changes_applied': changes_applied
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Sync failed: {str(e)}'
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


@login_required
@require_http_methods(['POST'])
def rule_add(request, agent_id):
    """Add a new firewall rule to an agent."""
    agent = get_object_or_404(Agent, id=agent_id)
    
    try:
        data = json.loads(request.body)
        zone_id = data.get('zone_id')
        rule_type = data.get('rule_type')
        
        zone = get_object_or_404(FirewallZone, id=zone_id, agent=agent)
        
        # Create the rule
        rule_data = {
            'agent': agent,
            'zone': zone,
            'rule_type': rule_type,
            'enabled': data.get('enabled', True),
            'permanent': data.get('permanent', True),
            'created_by': request.user
        }
        
        # Add type-specific fields
        if rule_type == 'service':
            rule_data['service'] = data.get('service', '')
        elif rule_type == 'port':
            rule_data['port'] = data.get('port', '')
            rule_data['protocol'] = data.get('protocol', 'tcp')
        elif rule_type == 'rich':
            rule_data['rich_rule'] = data.get('rich_rule', '')
        elif rule_type == 'forward':
            rule_data['port'] = data.get('port', '')
            rule_data['protocol'] = data.get('protocol', 'tcp')
            rule_data['to_port'] = data.get('to_port', '')
            rule_data['to_addr'] = data.get('to_addr', '')
        
        rule = FirewallRule.objects.create(**rule_data)
        
        # Apply the rule to the agent if connection is available
        manager = get_connection_manager(agent)
        
        # Build firewall command based on rule type
        if rule_type == 'service':
            command = f'add-service'
            parameters = {'service': rule.service, 'zone': zone.name}
        elif rule_type == 'port':
            command = f'add-port'
            parameters = {'port': f"{rule.port}/{rule.protocol}", 'zone': zone.name}
        else:
            command = None
            parameters = {}
        
        if command:
            result = asyncio.run(manager.execute_command(command, parameters))
        
        return JsonResponse({
            'success': True,
            'message': f'Rule added successfully',
            'rule_id': str(rule.id)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Failed to add rule: {str(e)}'
        })


@login_required
@require_http_methods(['POST'])
def rule_delete(request, agent_id, rule_id):
    """Delete a firewall rule from an agent."""
    agent = get_object_or_404(Agent, id=agent_id)
    rule = get_object_or_404(FirewallRule, id=rule_id, agent=agent)
    
    try:
        # Apply the deletion to the agent if connection is available
        manager = get_connection_manager(agent)
        
        # Build firewall command based on rule type
        if rule.rule_type == 'service':
            command = f'remove-service'
            parameters = {'service': rule.service, 'zone': rule.zone.name}
        elif rule.rule_type == 'port':
            command = f'remove-port'
            parameters = {'port': f"{rule.port}/{rule.protocol}", 'zone': rule.zone.name}
        else:
            command = None
            parameters = {}
        
        if command:
            result = asyncio.run(manager.execute_command(command, parameters))
        
        # Delete from database
        rule.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Rule deleted successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Failed to delete rule: {str(e)}'
        })


@login_required
@require_http_methods(['POST'])
def rules_bulk_delete(request, agent_id):
    """Delete multiple firewall rules (bulk delete by service/port name)."""
    agent = get_object_or_404(Agent, id=agent_id)
    
    try:
        data = json.loads(request.body)
        rule_ids = data.get('rule_ids', [])
        name = data.get('name', '')
        rule_type = data.get('type', '')
        
        if not rule_ids:
            return JsonResponse({
                'success': False,
                'error': 'No rule IDs provided'
            })
        
        # Get all rules
        rules = FirewallRule.objects.filter(id__in=rule_ids, agent=agent)
        
        if not rules.exists():
            return JsonResponse({
                'success': False,
                'error': 'No matching rules found'
            })
        
        # Get connection manager
        manager = get_connection_manager(agent)
        deleted_count = 0
        errors = []
        
        # Delete each rule
        for rule in rules:
            try:
                # Build firewall command based on rule type
                if rule.rule_type == 'service':
                    command = 'remove-service'
                    parameters = {'service': rule.service, 'zone': rule.zone.name}
                    # Also remove from zone.services
                    if rule.service in rule.zone.services:
                        rule.zone.services.remove(rule.service)
                        rule.zone.save()
                elif rule.rule_type == 'port':
                    command = 'remove-port'
                    port_spec = f"{rule.port}/{rule.protocol}"
                    parameters = {'port': port_spec, 'zone': rule.zone.name}
                    # Also remove from zone.ports
                    if port_spec in rule.zone.ports:
                        rule.zone.ports.remove(port_spec)
                        rule.zone.save()
                else:
                    continue
                
                # Execute command on agent
                try:
                    asyncio.run(manager.execute_command(command, parameters))
                except Exception as cmd_error:
                    errors.append(f"Zone {rule.zone.name}: {str(cmd_error)}")
                
                # Delete from database
                rule.delete()
                deleted_count += 1
                
            except Exception as e:
                errors.append(f"Rule {rule.id}: {str(e)}")
                continue
        
        # Close connection if needed
        if hasattr(manager, 'close') and callable(getattr(manager, 'close')):
            manager.close()
        
        message = f'Successfully deleted {deleted_count} rule(s)'
        if errors:
            message += f'. Errors: {"; ".join(errors[:3])}'
        
        return JsonResponse({
            'success': True,
            'message': message,
            'deleted_count': deleted_count,
            'errors': errors if errors else None
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Failed to delete rules: {str(e)}'
        })


@login_required
@require_http_methods(['POST'])
def zone_add_service(request, agent_id, zone_id):
    """Add a service to a firewall zone."""
    agent = get_object_or_404(Agent, id=agent_id)
    zone = get_object_or_404(FirewallZone, id=zone_id, agent=agent)
    
    try:
        data = json.loads(request.body)
        service = data.get('service', '')
        
        if not service:
            return JsonResponse({
                'success': False,
                'error': 'Service name is required'
            })
        
        # Add service to zone
        if service not in zone.services:
            zone.services.append(service)
            zone.save()
        
        # Create a rule for the service
        rule = FirewallRule.objects.create(
            agent=agent,
            zone=zone,
            rule_type='service',
            service=service,
            enabled=True,
            permanent=True,
            created_by=request.user
        )
        
        # Apply to agent
        manager = get_connection_manager(agent)
        result = asyncio.run(manager.execute_command('add-service', {
            'service': service,
            'zone': zone.name
        }))
        
        return JsonResponse({
            'success': True,
            'message': f'Service {service} added to zone {zone.name}'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Failed to add service: {str(e)}'
        })


@login_required
@require_http_methods(['POST'])
def zone_remove_service(request, agent_id, zone_id, service):
    """Remove a service from a firewall zone."""
    agent = get_object_or_404(Agent, id=agent_id)
    zone = get_object_or_404(FirewallZone, id=zone_id, agent=agent)
    
    try:
        # Remove service from zone
        if service in zone.services:
            zone.services.remove(service)
            zone.save()
        
        # Delete associated rules
        FirewallRule.objects.filter(
            agent=agent,
            zone=zone,
            rule_type='service',
            service=service
        ).delete()
        
        # Apply to agent
        manager = get_connection_manager(agent)
        result = asyncio.run(manager.execute_command('remove-service', {
            'service': service,
            'zone': zone.name
        }))
        
        return JsonResponse({
            'success': True,
            'message': f'Service {service} removed from zone {zone.name}'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Failed to remove service: {str(e)}'
        })


@login_required
@require_http_methods(['POST'])
def zone_add_port(request, agent_id, zone_id):
    """Add a port to a firewall zone."""
    agent = get_object_or_404(Agent, id=agent_id)
    zone = get_object_or_404(FirewallZone, id=zone_id, agent=agent)
    
    try:
        data = json.loads(request.body)
        port = data.get('port', '')
        protocol = data.get('protocol', 'tcp')
        port_spec = f"{port}/{protocol}"
        
        if not port:
            return JsonResponse({
                'success': False,
                'error': 'Port is required'
            })
        
        # Add port to zone
        if port_spec not in zone.ports:
            zone.ports.append(port_spec)
            zone.save()
        
        # Create a rule for the port
        rule = FirewallRule.objects.create(
            agent=agent,
            zone=zone,
            rule_type='port',
            port=port,
            protocol=protocol,
            enabled=True,
            permanent=True,
            created_by=request.user
        )
        
        # Apply to agent
        manager = get_connection_manager(agent)
        result = asyncio.run(manager.execute_command('add-port', {
            'port': port_spec,
            'zone': zone.name
        }))
        
        return JsonResponse({
            'success': True,
            'message': f'Port {port_spec} added to zone {zone.name}'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Failed to add port: {str(e)}'
        })


@login_required
@require_http_methods(['POST'])
def zone_remove_port(request, agent_id, zone_id):
    """Remove a port from a firewall zone."""
    agent = get_object_or_404(Agent, id=agent_id)
    zone = get_object_or_404(FirewallZone, id=zone_id, agent=agent)
    
    try:
        data = json.loads(request.body)
        port_spec = data.get('port_spec', '')  # e.g., "80/tcp"
        
        if not port_spec:
            return JsonResponse({
                'success': False,
                'error': 'Port specification is required'
            })
        
        # Parse port specification
        if '/' in port_spec:
            port, protocol = port_spec.split('/', 1)
        else:
            port, protocol = port_spec, 'tcp'
        
        # Remove port from zone
        if port_spec in zone.ports:
            zone.ports.remove(port_spec)
            zone.save()
        
        # Delete associated rules
        FirewallRule.objects.filter(
            agent=agent,
            zone=zone,
            rule_type='port',
            port=port,
            protocol=protocol
        ).delete()
        
        # Apply to agent
        manager = get_connection_manager(agent)
        result = asyncio.run(manager.execute_command('remove-port', {
            'port': port_spec,
            'zone': zone.name
        }))
        
        return JsonResponse({
            'success': True,
            'message': f'Port {port_spec} removed from zone {zone.name}'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Failed to remove port: {str(e)}'
        })


@login_required
@require_http_methods(['POST'])
def zone_create(request, agent_id):
    """Create a new firewall zone."""
    agent = get_object_or_404(Agent, id=agent_id)
    
    try:
        data = json.loads(request.body)
        zone_name = data.get('name', '').strip()
        target = data.get('target', 'default')
        
        if not zone_name:
            return JsonResponse({
                'success': False,
                'error': 'Zone name is required'
            })
        
        # Check if zone already exists
        if FirewallZone.objects.filter(agent=agent, name=zone_name).exists():
            return JsonResponse({
                'success': False,
                'error': f'Zone "{zone_name}" already exists'
            })
        
        # Create zone on agent first
        manager = get_connection_manager(agent)
        
        try:
            # Use firewall-cmd to create new zone
            result = asyncio.run(manager.execute_command('new-zone', {
                'zone': zone_name
            }))
            
            # Set target if specified
            if target and target != 'default':
                asyncio.run(manager.execute_command('set-target', {
                    'zone': zone_name,
                    'target': target
                }))
                
        except Exception as cmd_error:
            return JsonResponse({
                'success': False,
                'error': f'Failed to create zone on agent: {str(cmd_error)}'
            })
        
        # Create zone in database
        zone = FirewallZone.objects.create(
            agent=agent,
            name=zone_name,
            target=target,
            interfaces=[],
            sources=[],
            services=[],
            ports=[],
            masquerade=False
        )
        
        # Close connection if needed
        if hasattr(manager, 'close') and callable(getattr(manager, 'close')):
            manager.close()
        
        return JsonResponse({
            'success': True,
            'message': f'Zone "{zone_name}" created successfully',
            'zone_id': zone.id
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Failed to create zone: {str(e)}'
        })


@login_required
@require_http_methods(['POST'])
def zone_delete(request, agent_id, zone_id):
    """Delete a firewall zone."""
    agent = get_object_or_404(Agent, id=agent_id)
    zone = get_object_or_404(FirewallZone, id=zone_id, agent=agent)
    
    try:
        zone_name = zone.name
        
        # Delete zone from agent first
        manager = get_connection_manager(agent)
        
        try:
            result = asyncio.run(manager.execute_command('delete-zone', {
                'zone': zone_name
            }))
        except Exception as cmd_error:
            return JsonResponse({
                'success': False,
                'error': f'Failed to delete zone from agent: {str(cmd_error)}'
            })
        
        # Delete from database (this will cascade delete all rules)
        zone.delete()
        
        # Close connection if needed
        if hasattr(manager, 'close') and callable(getattr(manager, 'close')):
            manager.close()
        
        return JsonResponse({
            'success': True,
            'message': f'Zone "{zone_name}" deleted successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Failed to delete zone: {str(e)}'
        })


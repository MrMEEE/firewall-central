from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from datetime import datetime, timedelta

from agents.models import Agent, AgentConnection, FirewallRule, AgentCommand
from .models import WhiteboardState, UserPreferences


@login_required
def dashboard_home(request):
    """Main dashboard view."""
    # Get statistics
    total_agents = Agent.objects.count()
    online_agents = Agent.objects.filter(status='online').count()
    pending_agents = Agent.objects.filter(status='pending').count()
    recent_commands = AgentCommand.objects.order_by('-created_at')[:5]
    
    context = {
        'total_agents': total_agents,
        'online_agents': online_agents,
        'pending_agents': pending_agents,
        'recent_commands': recent_commands,
    }
    
    return render(request, 'dashboard/home.html', context)


@login_required
def whiteboard(request):
    """Whiteboard view for visual agent management."""
    agents = Agent.objects.all()
    connections = AgentConnection.objects.all()
    
    # Get user's whiteboard state
    whiteboard_state, created = WhiteboardState.objects.get_or_create(
        user=request.user,
        defaults={'zoom': 1.0, 'center_x': 0.0, 'center_y': 0.0}
    )
    
    context = {
        'agents': agents,
        'connections': connections,
        'whiteboard_state': whiteboard_state,
    }
    
    return render(request, 'dashboard/whiteboard.html', context)


@login_required
def agent_list(request):
    """Agent list view."""
    agents = Agent.objects.all().order_by('hostname')
    
    # Filter by status if specified
    status_filter = request.GET.get('status')
    if status_filter:
        agents = agents.filter(status=status_filter)
    
    context = {
        'agents': agents,
        'status_filter': status_filter,
    }
    
    return render(request, 'dashboard/agent_list.html', context)


@login_required
def agent_detail(request, agent_id):
    """Agent detail view."""
    agent = get_object_or_404(Agent, id=agent_id)
    zones = agent.zones.all()
    rules = agent.rules.all()
    recent_commands = agent.commands.order_by('-created_at')[:10]
    
    context = {
        'agent': agent,
        'zones': zones,
        'rules': rules,
        'recent_commands': recent_commands,
    }
    
    return render(request, 'dashboard/agent_detail.html', context)


@login_required
@csrf_exempt
@require_http_methods(["GET", "POST"])
def whiteboard_state_api(request):
    """API endpoint for whiteboard state."""
    whiteboard_state, created = WhiteboardState.objects.get_or_create(
        user=request.user,
        defaults={'zoom': 1.0, 'center_x': 0.0, 'center_y': 0.0}
    )
    
    if request.method == 'GET':
        return JsonResponse({
            'zoom': whiteboard_state.zoom,
            'center_x': whiteboard_state.center_x,
            'center_y': whiteboard_state.center_y,
        })
    
    elif request.method == 'POST':
        data = json.loads(request.body)
        
        if 'zoom' in data:
            whiteboard_state.zoom = data['zoom']
        if 'center_x' in data:
            whiteboard_state.center_x = data['center_x']
        if 'center_y' in data:
            whiteboard_state.center_y = data['center_y']
        
        whiteboard_state.save()
        
        return JsonResponse({'status': 'success'})


@login_required
@csrf_exempt
@require_http_methods(["GET", "POST"])
def agent_positions_api(request):
    """API endpoint for agent positions."""
    if request.method == 'GET':
        agents = Agent.objects.all()
        positions = []
        
        for agent in agents:
            positions.append({
                'id': str(agent.id),
                'hostname': agent.hostname,
                'x': agent.position_x,
                'y': agent.position_y,
                'status': agent.status,
                'ip_address': agent.ip_address,
            })
        
        return JsonResponse({'agents': positions})
    
    elif request.method == 'POST':
        data = json.loads(request.body)
        
        for agent_data in data.get('agents', []):
            try:
                agent = Agent.objects.get(id=agent_data['id'])
                agent.position_x = agent_data['x']
                agent.position_y = agent_data['y']
                agent.save()
            except Agent.DoesNotExist:
                continue
        
        return JsonResponse({'status': 'success'})


@login_required
def connections_api(request):
    """API endpoint for agent connections."""
    connections = AgentConnection.objects.all()
    connection_data = []
    
    for conn in connections:
        connection_data.append({
            'id': str(conn.id),
            'source_agent_id': str(conn.source_agent.id),
            'target_agent_id': str(conn.target_agent.id),
            'source_port': conn.source_port,
            'target_port': conn.target_port,
            'protocol': conn.protocol,
            'service': conn.service,
            'description': conn.description,
            'color': conn.color,
        })
    
    return JsonResponse({'connections': connection_data})


@login_required
def stats_api(request):
    """API endpoint for dashboard statistics."""
    # Agent statistics
    total_agents = Agent.objects.count()
    online_agents = Agent.objects.filter(status='online').count()
    offline_agents = Agent.objects.filter(status='offline').count()
    pending_agents = Agent.objects.filter(status='pending').count()
    error_agents = Agent.objects.filter(status='error').count()
    
    # Rule statistics
    total_rules = FirewallRule.objects.count()
    enabled_rules = FirewallRule.objects.filter(enabled=True).count()
    
    # Command statistics
    total_commands = AgentCommand.objects.count()
    pending_commands = AgentCommand.objects.filter(status='pending').count()
    failed_commands = AgentCommand.objects.filter(status='failed').count()
    
    # Recent activity
    recent_commands = AgentCommand.objects.order_by('-created_at')[:5]
    recent_command_data = []
    
    for cmd in recent_commands:
        recent_command_data.append({
            'id': str(cmd.id),
            'agent_hostname': cmd.agent.hostname,
            'command_type': cmd.command_type,
            'status': cmd.status,
            'created_at': cmd.created_at.isoformat(),
        })
    
    # Last 24 hours activity
    yesterday = datetime.now() - timedelta(days=1)
    commands_24h = AgentCommand.objects.filter(created_at__gte=yesterday).count()
    
    return JsonResponse({
        'agents': {
            'total': total_agents,
            'online': online_agents,
            'offline': offline_agents,
            'pending': pending_agents,
            'error': error_agents,
        },
        'rules': {
            'total': total_rules,
            'enabled': enabled_rules,
        },
        'commands': {
            'total': total_commands,
            'pending': pending_commands,
            'failed': failed_commands,
            'last_24h': commands_24h,
        },
        'recent_activity': recent_command_data,
    })
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from agents.models import Agent, AgentCommand


class DashboardConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time dashboard updates."""
    
    async def connect(self):
        self.room_group_name = 'dashboard'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json['type']
        
        if message_type == 'agent_position_update':
            await self.handle_agent_position_update(text_data_json)
    
    async def handle_agent_position_update(self, data):
        """Handle agent position updates on whiteboard."""
        agent_id = data['agent_id']
        x = data['x']
        y = data['y']
        
        # Update agent position in database
        await self.update_agent_position(agent_id, x, y)
        
        # Broadcast to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'agent_position_update',
                'agent_id': agent_id,
                'x': x,
                'y': y,
            }
        )
    
    async def agent_position_update(self, event):
        """Send agent position update to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'agent_position_update',
            'agent_id': event['agent_id'],
            'x': event['x'],
            'y': event['y'],
        }))
    
    async def agent_status_update(self, event):
        """Send agent status update to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'agent_status_update',
            'agent_id': event['agent_id'],
            'status': event['status'],
            'last_seen': event['last_seen'],
        }))
    
    async def command_update(self, event):
        """Send command update to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'command_update',
            'command_id': event['command_id'],
            'agent_id': event['agent_id'],
            'status': event['status'],
        }))
    
    @database_sync_to_async
    def update_agent_position(self, agent_id, x, y):
        """Update agent position in database."""
        try:
            agent = Agent.objects.get(id=agent_id)
            agent.position_x = x
            agent.position_y = y
            agent.save()
        except Agent.DoesNotExist:
            pass


class AgentConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for individual agent updates."""
    
    async def connect(self):
        self.agent_id = self.scope['url_route']['kwargs']['agent_id']
        self.room_group_name = f'agent_{self.agent_id}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json['type']
        
        if message_type == 'execute_command':
            await self.handle_execute_command(text_data_json)
    
    async def handle_execute_command(self, data):
        """Handle command execution request."""
        command_type = data['command_type']
        parameters = data.get('parameters', {})
        
        # Create command in database
        command = await self.create_command(self.agent_id, command_type, parameters)
        
        # Broadcast command creation
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'command_created',
                'command_id': str(command.id),
                'command_type': command_type,
                'status': 'pending',
            }
        )
    
    async def command_created(self, event):
        """Send command creation notification to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'command_created',
            'command_id': event['command_id'],
            'command_type': event['command_type'],
            'status': event['status'],
        }))
    
    async def command_result(self, event):
        """Send command result to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'command_result',
            'command_id': event['command_id'],
            'status': event['status'],
            'result': event['result'],
            'error': event.get('error'),
        }))
    
    @database_sync_to_async
    def create_command(self, agent_id, command_type, parameters):
        """Create a new command in database."""
        agent = Agent.objects.get(id=agent_id)
        command = AgentCommand.objects.create(
            agent=agent,
            command_type=command_type,
            parameters=parameters
        )
        return command
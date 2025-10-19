from rest_framework import serializers
from .models import Agent, FirewallZone, FirewallRule, AgentConnection, AgentCommand


class AgentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Agent
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'last_seen']


class FirewallZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = FirewallZone
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class FirewallRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = FirewallRule
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'created_by']


class AgentConnectionSerializer(serializers.ModelSerializer):
    source_agent_hostname = serializers.CharField(source='source_agent.hostname', read_only=True)
    target_agent_hostname = serializers.CharField(source='target_agent.hostname', read_only=True)
    
    class Meta:
        model = AgentConnection
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'created_by']


class AgentCommandSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentCommand
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'executed_at', 'completed_at', 'created_by']
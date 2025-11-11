from django.db import models
from django.contrib.auth.models import User
import uuid


class Agent(models.Model):
    CONNECTION_TYPES = [
        ('agent_to_server', 'Agent connects to Server'),
        ('server_to_agent', 'Server connects to Agent'),
        ('ssh', 'SSH Connection'),
    ]
    
    AGENT_MODES = [
        ('push', 'Push Mode'),
        ('pull', 'Pull Mode'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('offline', 'Offline'),
        ('online', 'Online'),
        ('error', 'Error'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hostname = models.CharField(max_length=255, unique=True)
    ip_address = models.GenericIPAddressField()
    port = models.IntegerField(default=8443)
    connection_type = models.CharField(max_length=20, choices=CONNECTION_TYPES, default='agent_to_server')
    mode = models.CharField(max_length=10, choices=AGENT_MODES, default='push')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    last_seen = models.DateTimeField(null=True, blank=True)
    certificate = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # SSH connection fields
    ssh_username = models.CharField(max_length=100, blank=True, help_text="Username for SSH connections")
    ssh_key_path = models.CharField(max_length=500, blank=True, help_text="Path to SSH private key")
    ssh_password = models.CharField(max_length=255, blank=True, help_text="SSH password (use key-based auth when possible)")
    
    # Agent endpoint fields (for server_to_agent connections)
    agent_port = models.IntegerField(default=8444, help_text="Port where agent listens for connections")
    agent_api_key = models.CharField(max_length=255, blank=True, help_text="API key for agent authentication")
    
    # Position for whiteboard interface
    position_x = models.FloatField(default=0)
    position_y = models.FloatField(default=0)
    
    # Agent metadata
    version = models.CharField(max_length=50, blank=True)
    operating_system = models.CharField(max_length=100, blank=True)
    firewalld_version = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    
    # Auto-sync configuration
    sync_interval_seconds = models.IntegerField(
        default=60,
        help_text="Interval in seconds for automatic firewall configuration sync (0 to disable)"
    )
    last_sync = models.DateTimeField(null=True, blank=True, help_text="Last time firewall config was synced")
    
    # Available firewalld services on this agent
    available_services = models.JSONField(
        default=list,
        blank=True,
        help_text="List of available firewalld services on this agent"
    )
    
    class Meta:
        ordering = ['hostname']
    
    def __str__(self):
        return f"{self.hostname} ({self.ip_address})"
    
    @property
    def os_info(self):
        """Return formatted OS information"""
        if self.operating_system:
            return self.operating_system
        return "Unknown"
    
    def get_connection_endpoint(self):
        """Get the connection endpoint based on connection type"""
        if self.connection_type == 'server_to_agent':
            return f"{self.ip_address}:{self.agent_port}"
        elif self.connection_type == 'ssh':
            return f"{self.ssh_username}@{self.ip_address}:{self.port}"
        else:  # agent_to_server
            return f"Server listens for {self.hostname}"


class FirewallZone(models.Model):
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='zones')
    name = models.CharField(max_length=100)
    target = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    interfaces = models.JSONField(default=list)
    sources = models.JSONField(default=list)
    services = models.JSONField(default=list)
    ports = models.JSONField(default=list)
    masquerade = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['agent', 'name']
    
    def __str__(self):
        return f"{self.agent.hostname} - {self.name}"


class FirewallRule(models.Model):
    RULE_TYPES = [
        ('service', 'Service'),
        ('port', 'Port'),
        ('rich', 'Rich Rule'),
        ('forward', 'Forward Port'),
        ('masquerade', 'Masquerade'),
        ('source_port', 'Source Port'),
        ('icmp_block', 'ICMP Block'),
    ]
    
    PROTOCOLS = [
        ('tcp', 'TCP'),
        ('udp', 'UDP'),
        ('icmp', 'ICMP'),
        ('sctp', 'SCTP'),
        ('dccp', 'DCCP'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='rules')
    zone = models.ForeignKey(FirewallZone, on_delete=models.CASCADE, related_name='rules')
    rule_type = models.CharField(max_length=20, choices=RULE_TYPES)
    
    # Service rule fields
    service = models.CharField(max_length=100, blank=True)
    
    # Port rule fields
    port = models.CharField(max_length=20, blank=True)
    protocol = models.CharField(max_length=10, choices=PROTOCOLS, blank=True)
    
    # Rich rule fields
    rich_rule = models.TextField(blank=True)
    
    # Forward port fields
    to_port = models.CharField(max_length=20, blank=True)
    to_addr = models.GenericIPAddressField(null=True, blank=True)
    
    # Common fields
    source = models.CharField(max_length=100, blank=True)
    destination = models.CharField(max_length=100, blank=True)
    enabled = models.BooleanField(default=True)
    permanent = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.agent.hostname} - {self.zone.name} - {self.rule_type}"


class AgentConnection(models.Model):
    """Represents a connection between two agents for network visualization."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='outgoing_connections')
    target_agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='incoming_connections')
    
    # Connection details
    source_port = models.CharField(max_length=20, blank=True)
    target_port = models.CharField(max_length=20, blank=True)
    protocol = models.CharField(max_length=10, blank=True)
    service = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    
    # Visual properties
    color = models.CharField(max_length=7, default='#007bff')  # Hex color
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        unique_together = ['source_agent', 'target_agent', 'source_port', 'target_port']
    
    def __str__(self):
        return f"{self.source_agent.hostname} -> {self.target_agent.hostname}"


class AgentCommand(models.Model):
    """Track commands sent to agents."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('timeout', 'Timeout'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='commands')
    command_type = models.CharField(max_length=50)
    parameters = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    result = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    timeout = models.IntegerField(default=30)
    
    created_at = models.DateTimeField(auto_now_add=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.agent.hostname} - {self.command_type} - {self.status}"
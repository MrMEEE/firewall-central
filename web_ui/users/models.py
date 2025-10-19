from django.db import models
from django.contrib.auth.models import User
from agents.models import Agent


class UserProfile(models.Model):
    """Extended user profile."""
    ROLE_CHOICES = [
        ('admin', 'Administrator'),
        ('manager', 'Manager'),
        ('viewer', 'Viewer'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='viewer')
    phone = models.CharField(max_length=20, blank=True)
    department = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.role}"


class UserAgentPermission(models.Model):
    """Defines which agents a user can access."""
    PERMISSION_CHOICES = [
        ('view', 'View Only'),
        ('modify', 'View and Modify'),
        ('admin', 'Full Admin'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='agent_permissions')
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='user_permissions')
    permission_level = models.CharField(max_length=20, choices=PERMISSION_CHOICES, default='view')
    granted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='granted_permissions')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'agent']
    
    def __str__(self):
        return f"{self.user.username} - {self.agent.hostname} - {self.permission_level}"
from django.db import models
from django.contrib.auth.models import User
import uuid


class WhiteboardState(models.Model):
    """Store whiteboard state for users."""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    zoom = models.FloatField(default=1.0)
    center_x = models.FloatField(default=0.0)
    center_y = models.FloatField(default=0.0)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Whiteboard state for {self.user.username}"


class UserPreferences(models.Model):
    """Store user preferences."""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    theme = models.CharField(max_length=20, choices=[
        ('light', 'Light'),
        ('dark', 'Dark'),
    ], default='light')
    auto_refresh = models.BooleanField(default=True)
    refresh_interval = models.IntegerField(default=30)  # seconds
    show_offline_agents = models.BooleanField(default=True)
    notifications_enabled = models.BooleanField(default=True)
    
    def __str__(self):
        return f"Preferences for {self.user.username}"
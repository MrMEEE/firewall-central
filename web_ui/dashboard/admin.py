from django.contrib import admin
from .models import WhiteboardState, UserPreferences


@admin.register(WhiteboardState)
class WhiteboardStateAdmin(admin.ModelAdmin):
    list_display = ['user', 'zoom', 'center_x', 'center_y', 'updated_at']
    search_fields = ['user__username']


@admin.register(UserPreferences)
class UserPreferencesAdmin(admin.ModelAdmin):
    list_display = ['user', 'theme', 'auto_refresh', 'refresh_interval', 'notifications_enabled']
    list_filter = ['theme', 'auto_refresh', 'notifications_enabled']
    search_fields = ['user__username']
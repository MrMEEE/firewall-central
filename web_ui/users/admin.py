from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile, UserAgentPermission


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)


@admin.register(UserAgentPermission)
class UserAgentPermissionAdmin(admin.ModelAdmin):
    list_display = ['user', 'agent', 'permission_level', 'granted_by', 'created_at']
    list_filter = ['permission_level', 'created_at']
    search_fields = ['user__username', 'agent__hostname']


# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
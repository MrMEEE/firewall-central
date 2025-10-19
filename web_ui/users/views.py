from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from agents.models import Agent
from .models import UserProfile, UserAgentPermission
from .forms import UserForm, UserProfileForm, UserAgentPermissionForm


def is_admin(user):
    """Check if user is admin."""
    try:
        return user.userprofile.role == 'admin'
    except:
        return user.is_superuser


@login_required
@user_passes_test(is_admin)
def user_list(request):
    """List all users."""
    users = User.objects.all().select_related('userprofile')
    return render(request, 'users/list.html', {'users': users})


@login_required
@user_passes_test(is_admin)
def user_create(request):
    """Create a new user."""
    if request.method == 'POST':
        user_form = UserForm(request.POST)
        profile_form = UserProfileForm(request.POST)
        
        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save()
            profile = profile_form.save(commit=False)
            profile.user = user
            profile.save()
            
            messages.success(request, 'User created successfully.')
            return redirect('user-detail', user_id=user.id)
    else:
        user_form = UserForm()
        profile_form = UserProfileForm()
    
    return render(request, 'users/create.html', {
        'user_form': user_form,
        'profile_form': profile_form
    })


@login_required
def user_detail(request, user_id):
    """User detail view."""
    user = get_object_or_404(User, id=user_id)
    
    # Check permissions
    if not (request.user == user or is_admin(request.user)):
        messages.error(request, 'Permission denied.')
        return redirect('dashboard-home')
    
    try:
        profile = user.userprofile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=user)
    
    permissions = UserAgentPermission.objects.filter(user=user).select_related('agent')
    
    return render(request, 'users/detail.html', {
        'user': user,
        'profile': profile,
        'permissions': permissions
    })


@login_required
def user_edit(request, user_id):
    """Edit user."""
    user = get_object_or_404(User, id=user_id)
    
    # Check permissions
    if not (request.user == user or is_admin(request.user)):
        messages.error(request, 'Permission denied.')
        return redirect('dashboard-home')
    
    try:
        profile = user.userprofile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=user)
    
    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=user)
        profile_form = UserProfileForm(request.POST, instance=profile)
        
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            
            messages.success(request, 'Profile updated successfully.')
            return redirect('user-detail', user_id=user.id)
    else:
        user_form = UserForm(instance=user)
        profile_form = UserProfileForm(instance=profile)
    
    return render(request, 'users/edit.html', {
        'user': user,
        'user_form': user_form,
        'profile_form': profile_form
    })


@login_required
@user_passes_test(is_admin)
def user_permissions(request, user_id):
    """Manage user agent permissions."""
    user = get_object_or_404(User, id=user_id)
    agents = Agent.objects.all()
    permissions = UserAgentPermission.objects.filter(user=user).select_related('agent')
    
    if request.method == 'POST':
        # Handle permission updates
        for agent in agents:
            permission_level = request.POST.get(f'permission_{agent.id}')
            
            if permission_level:
                permission, created = UserAgentPermission.objects.get_or_create(
                    user=user,
                    agent=agent,
                    defaults={
                        'permission_level': permission_level,
                        'granted_by': request.user
                    }
                )
                
                if not created:
                    permission.permission_level = permission_level
                    permission.granted_by = request.user
                    permission.save()
            else:
                # Remove permission if not set
                UserAgentPermission.objects.filter(user=user, agent=agent).delete()
        
        messages.success(request, 'Permissions updated successfully.')
        return redirect('user-detail', user_id=user.id)
    
    # Create a mapping of agent permissions for the template
    permission_map = {p.agent.id: p.permission_level for p in permissions}
    
    return render(request, 'users/permissions.html', {
        'user': user,
        'agents': agents,
        'permission_map': permission_map
    })


@login_required
def user_profile(request):
    """User's own profile view."""
    return redirect('user-detail', user_id=request.user.id)
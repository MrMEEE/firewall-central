from django import forms
from django.contrib.auth.models import User
from .models import UserProfile, UserAgentPermission


class UserForm(forms.ModelForm):
    """Form for creating/editing users."""
    password = forms.CharField(widget=forms.PasswordInput(), required=False)
    password_confirm = forms.CharField(widget=forms.PasswordInput(), required=False)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'is_active']
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        
        if password and password != password_confirm:
            raise forms.ValidationError("Passwords don't match")
        
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        
        if password:
            user.set_password(password)
        
        if commit:
            user.save()
        
        return user


class UserProfileForm(forms.ModelForm):
    """Form for user profile."""
    class Meta:
        model = UserProfile
        fields = ['role', 'phone', 'department']
        widgets = {
            'role': forms.Select(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.TextInput(attrs={'class': 'form-control'}),
        }


class UserAgentPermissionForm(forms.ModelForm):
    """Form for user agent permissions."""
    class Meta:
        model = UserAgentPermission
        fields = ['agent', 'permission_level']
        widgets = {
            'agent': forms.Select(attrs={'class': 'form-control'}),
            'permission_level': forms.Select(attrs={'class': 'form-control'}),
        }
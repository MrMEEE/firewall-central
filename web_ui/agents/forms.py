from django import forms
from .models import Agent


class AgentForm(forms.ModelForm):
    """Form for creating and editing agents"""
    
    class Meta:
        model = Agent
        fields = [
            'hostname', 'ip_address', 'connection_type', 'mode', 'port',
            'ssh_username', 'ssh_key_path', 'ssh_password',
            'agent_port', 'agent_api_key', 'sync_interval_seconds', 'description'
        ]
        widgets = {
            'hostname': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter hostname'
            }),
            'ip_address': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '192.168.1.100'
            }),
            'connection_type': forms.Select(attrs={
                'class': 'form-select',
                'id': 'connection_type'
            }),
            'mode': forms.Select(attrs={
                'class': 'form-select'
            }),
            'port': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '22 (SSH) or 8443 (HTTPS)'
            }),
            'ssh_username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'root'
            }),
            'ssh_key_path': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '/path/to/private/key'
            }),
            'ssh_password': forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': 'SSH password (optional if using key)'
            }),
            'agent_port': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '8444'
            }),
            'agent_api_key': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'API key for agent authentication'
            }),
            'sync_interval_seconds': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '60',
                'min': '0',
                'help_text': 'Auto-sync interval in seconds (0 to disable)'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional description of this agent'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set default ports based on connection type
        if not self.instance.pk:  # New instance
            self.initial['port'] = 22  # Default to SSH port
            self.initial['agent_port'] = 8444
            self.initial['sync_interval_seconds'] = 60  # Default 60 seconds

    def clean(self):
        cleaned_data = super().clean()
        connection_type = cleaned_data.get('connection_type')
        ssh_username = cleaned_data.get('ssh_username')
        ssh_key_path = cleaned_data.get('ssh_key_path')
        ssh_password = cleaned_data.get('ssh_password')
        agent_api_key = cleaned_data.get('agent_api_key')

        # Validation for SSH connections
        if connection_type == 'ssh':
            if not ssh_username:
                raise forms.ValidationError("SSH username is required for SSH connections.")
            
            if not ssh_key_path and not ssh_password:
                raise forms.ValidationError(
                    "Either SSH key path or SSH password is required for SSH connections."
                )

        # Validation for server-to-agent connections
        if connection_type == 'server_to_agent':
            if not agent_api_key:
                raise forms.ValidationError(
                    "API key is required for server-to-agent connections."
                )

        return cleaned_data


class AgentQuickAddForm(forms.Form):
    """Quick form for adding agents with automatic detection"""
    
    CONNECTION_CHOICES = [
        ('auto', 'Auto-detect'),
        ('ssh', 'SSH Connection'),
        ('agent_to_server', 'Agent connects to Server'),
        ('server_to_agent', 'Server connects to Agent'),
    ]
    
    hostname = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'hostname.domain.com'
        })
    )
    
    ip_address = forms.GenericIPAddressField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '192.168.1.100'
        })
    )
    
    connection_type = forms.ChoiceField(
        choices=CONNECTION_CHOICES,
        initial='auto',
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    ssh_username = forms.CharField(
        max_length=100,
        required=False,
        initial='root',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'root'
        })
    )
    
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Optional description'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        connection_type = cleaned_data.get('connection_type')
        ssh_username = cleaned_data.get('ssh_username')

        if connection_type == 'ssh' and not ssh_username:
            raise forms.ValidationError("SSH username is required for SSH connections.")

        return cleaned_data
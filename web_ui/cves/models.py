"""
CVE Dashboard models.
"""
from django.db import models
from django.contrib.auth.models import User
import uuid


class CVESource(models.Model):
    """Represents a CVE data source (Red Hat, NVD, etc.)."""
    SOURCE_TYPES = [
        ('redhat', 'Red Hat Security Data'),
        ('nvd', 'NVD / NIST'),
        ('custom', 'Custom'),
    ]
    name = models.CharField(max_length=100)
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES, default='custom')
    api_url = models.URLField(blank=True)
    enabled = models.BooleanField(default=True)
    last_sync = models.DateTimeField(null=True, blank=True)
    default_days_back = models.PositiveIntegerField(
        default=365,
        help_text='Fetch CVEs published in the last N days (0 = all time)'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class CVE(models.Model):
    """A single CVE entry fetched from one or more sources."""
    SEVERITY_CHOICES = [
        ('critical', 'Critical'),
        ('important', 'Important'),
        ('moderate', 'Moderate'),
        ('low', 'Low'),
        ('none', 'None'),
        ('unknown', 'Unknown'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cve_id = models.CharField(max_length=30, db_index=True)
    source = models.ForeignKey(CVESource, on_delete=models.SET_NULL, null=True, related_name='cves')
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='unknown')
    cvss3_score = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    cvss3_vector = models.CharField(max_length=200, blank=True)
    public_date = models.DateTimeField(null=True, blank=True)
    description = models.TextField(blank=True)
    affected_packages = models.JSONField(default=list)
    advisories = models.JSONField(default=list)
    cwe = models.CharField(max_length=100, blank=True)
    bugzilla = models.CharField(max_length=50, blank=True)
    bugzilla_description = models.TextField(blank=True)
    resource_url = models.URLField(blank=True)
    raw_data = models.JSONField(default=dict)

    # Extended detail fields fetched from individual CVE API
    affected_releases = models.JSONField(default=list, blank=True)
    package_state = models.JSONField(default=list, blank=True)
    cvss2_score = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    cvss2_vector = models.CharField(max_length=200, blank=True)
    references = models.JSONField(default=list, blank=True)
    statement = models.TextField(blank=True)
    mitigation = models.TextField(blank=True)
    upstream_fix = models.CharField(max_length=200, blank=True)
    details = models.TextField(blank=True)
    details_fetched = models.BooleanField(default=False)

    acknowledged = models.BooleanField(default=False)
    acknowledged_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='acknowledged_cves'
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledgement_note = models.TextField(blank=True)

    affected_agents = models.ManyToManyField(
        'agents.Agent', blank=True, related_name='cves'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['cve_id', 'source']
        ordering = ['-public_date', '-cvss3_score']
        indexes = [
            models.Index(fields=['severity']),
            models.Index(fields=['acknowledged']),
            models.Index(fields=['public_date']),
        ]

    def __str__(self):
        return self.cve_id

    @property
    def severity_color(self):
        return {
            'critical': 'danger',
            'important': 'warning',
            'moderate': 'info',
            'low': 'secondary',
            'none': 'light',
            'unknown': 'dark',
        }.get(self.severity, 'dark')


class CVEDashboardWidget(models.Model):
    """A widget/box on the CVE dashboard, owned by a user."""
    WIDGET_TYPES = [
        ('cve_table', 'CVE Table'),
        ('severity_chart', 'Severity Distribution Chart'),
        ('timeline_chart', 'Timeline Chart'),
        ('unacked_count', 'Unacknowledged Count'),
        ('top_packages', 'Top Affected Packages'),
    ]

    SIZE_CHOICES = [
        ('full', 'Full Width'),
        ('half', 'Half Width'),
        ('quarter', 'Quarter Width'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cve_widgets')
    widget_type = models.CharField(max_length=30, choices=WIDGET_TYPES)
    title = models.CharField(max_length=100)
    position = models.PositiveIntegerField(default=0)
    size = models.CharField(max_length=10, choices=SIZE_CHOICES, default='half')
    config = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['user', 'position']

    def __str__(self):
        return f"{self.user.username} - {self.title}"


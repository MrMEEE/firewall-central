from django.contrib import admin
from .models import CVE, CVESource, CVEDashboardWidget


@admin.register(CVESource)
class CVESourceAdmin(admin.ModelAdmin):
    list_display = ['name', 'source_type', 'enabled', 'last_sync']
    list_filter = ['source_type', 'enabled']


@admin.register(CVE)
class CVEAdmin(admin.ModelAdmin):
    list_display = ['cve_id', 'severity', 'cvss3_score', 'public_date', 'acknowledged', 'source']
    list_filter = ['severity', 'acknowledged', 'source']
    search_fields = ['cve_id', 'description', 'bugzilla_description']
    readonly_fields = ['acknowledged_by', 'acknowledged_at']


@admin.register(CVEDashboardWidget)
class CVEDashboardWidgetAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'widget_type', 'position']


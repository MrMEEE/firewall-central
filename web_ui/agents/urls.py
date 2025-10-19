from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import api_views

router = DefaultRouter()
router.register(r'', views.AgentViewSet)
router.register(r'(?P<agent_id>[^/.]+)/zones', views.FirewallZoneViewSet, basename='agent-zones')
router.register(r'(?P<agent_id>[^/.]+)/rules', views.FirewallRuleViewSet, basename='agent-rules')
router.register(r'(?P<agent_id>[^/.]+)/commands', views.AgentCommandViewSet, basename='agent-commands')

urlpatterns = [
    # API routes
    path('api/', include(router.urls)),
    path('api/<uuid:agent_id>/status/', views.agent_status, name='agent-status'),
    path('api/<uuid:agent_id>/approve/', views.approve_agent, name='approve-agent'),
    path('api/<uuid:agent_id>/reject/', views.reject_agent, name='reject-agent'),
    path('api/connections/', views.ConnectionListCreateView.as_view(), name='connections'),
    path('api/connections/<uuid:connection_id>/', views.ConnectionDetailView.as_view(), name='connection-detail'),
    
    # Agent communication API endpoints
    path('api/checkin/', api_views.agent_checkin, name='api-agent-checkin'),
    path('api/register/', api_views.agent_register, name='api-agent-register'),
    path('api/<uuid:agent_id>/execute/', api_views.AgentCommandAPI.as_view(), name='api-agent-execute'),
    
    # Web interface routes
    path('', views.agent_list, name='agent-list'),
    path('create/', views.agent_create, name='agent-create'),
    path('quick-add/', views.agent_quick_add, name='agent-quick-add'),
    path('<uuid:agent_id>/', views.agent_detail, name='agent-detail'),
    path('<uuid:agent_id>/edit/', views.agent_edit, name='agent-edit'),
    path('<uuid:agent_id>/test-connection/', views.agent_test_connection, name='agent-test-connection'),
]
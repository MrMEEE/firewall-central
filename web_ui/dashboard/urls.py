from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_home, name='dashboard-home'),
    path('whiteboard/', views.whiteboard, name='whiteboard'),
    path('agents/', views.agent_list, name='agent-list'),
    path('agents/<uuid:agent_id>/', views.agent_detail, name='agent-detail'),
    path('api/whiteboard/state/', views.whiteboard_state_api, name='whiteboard-state-api'),
    path('api/agents/positions/', views.agent_positions_api, name='agent-positions-api'),
    path('api/connections/', views.connections_api, name='connections-api'),
    path('api/stats/', views.stats_api, name='stats-api'),
]
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/dashboard/$', consumers.DashboardConsumer.as_asgi()),
    re_path(r'ws/agents/(?P<agent_id>\w+)/$', consumers.AgentConsumer.as_asgi()),
]
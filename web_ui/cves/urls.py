from django.urls import path
from . import views

app_name = 'cves'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('list/', views.cve_list, name='cve_list'),
    path('detail/<uuid:cve_id>/', views.cve_detail, name='cve_detail'),
    path('sources/', views.sources_list, name='sources'),
    # Widget API
    path('api/widget/<uuid:widget_id>/', views.api_widget_data, name='widget_data'),
    path('api/widget/add/', views.add_widget, name='add_widget'),
    path('api/widget/layout/', views.update_widget_layout, name='update_widget_layout'),
    path('api/widget/<uuid:widget_id>/remove/', views.remove_widget, name='remove_widget'),
    # CVE actions
    path('api/<uuid:cve_id>/acknowledge/', views.acknowledge_cve, name='acknowledge'),
    path('api/<uuid:cve_id>/unacknowledge/', views.unacknowledge_cve, name='unacknowledge'),
    # Sync
    path('api/sync/<int:source_id>/', views.sync_now, name='sync_now'),
]

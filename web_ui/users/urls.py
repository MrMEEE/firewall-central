from django.urls import path
from . import views

urlpatterns = [
    path('', views.user_list, name='user-list'),
    path('create/', views.user_create, name='user-create'),
    path('<int:user_id>/', views.user_detail, name='user-detail'),
    path('<int:user_id>/edit/', views.user_edit, name='user-edit'),
    path('<int:user_id>/permissions/', views.user_permissions, name='user-permissions'),
    path('profile/', views.user_profile, name='user-profile'),
]
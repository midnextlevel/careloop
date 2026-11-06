from django.urls import path
from . import views
from .deployment import deployment

urlpatterns = [
    path('deployment/', deployment, name='deployment'),
    path('welcome/', views.welcome, name='welcome'),
    path('setup/', views.setup, name='setup'),
    path('profile/', views.profile, name='profile'),
    path('development/login/', views.development_login, name='development-login'),
    path('', views.timeline, name='timeline'),
    path('entries/new/', views.new_entry, name='new'),
    path('entries/<uuid:pk>/', views.detail, name='detail'),
    path('entries/<uuid:pk>/photos/<uuid:photo_id>/', views.photo, name='photo'),
    path('entries/<uuid:pk>/edit/', views.edit, name='edit'),
    path('entries/<uuid:pk>/publish/', views.publish, name='publish'),
    path('entries/<uuid:pk>/comments/', views.comment, name='comment'),
    path('entries/<uuid:pk>/access/', views.entry_access, name='entry-access'),
    path('access/', views.access_settings, name='access-settings'),
    path('team/', views.members, name='members'),
    path('team/<int:pk>/', views.members, name='member-edit'),
    path('sw.js', views.service_worker, name='sw'),
    path('install/', views.install, name='install'),
]

from django.urls import include, path
from journal import views

urlpatterns = [
    path('login/', views.login_page, name='login'),
    path('accounts/', include('allauth.urls')),
    path('', include('journal.urls')),
]

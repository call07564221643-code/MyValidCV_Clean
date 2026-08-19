from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('management/', views.management_dashboard, name='management_dashboard'),
    path('owner/', RedirectView.as_view(pattern_name='owner_console', permanent=False), name='owner_console_redirect'),
]

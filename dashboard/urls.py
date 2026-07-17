from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('owner/', views.owner_console, name='owner_console'),
]

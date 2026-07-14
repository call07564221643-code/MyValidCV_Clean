from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('social/login/<str:provider>/', views.social_login_start, name='social_login_start'),
    path('logout/', views.logout_view, name='logout'),
    path('settings/', views.settings_view, name='account_settings'),
]

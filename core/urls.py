from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('analyse/', views.analyse, name='analyse'),
    path('results/', views.results_preview, name='results'),
]

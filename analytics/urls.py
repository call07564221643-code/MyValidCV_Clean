from django.urls import path

from . import views


urlpatterns = [
    path("health/", views.website_health, name="website_health"),
]

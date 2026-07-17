from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('assistant/', views.assistant_reply, name='assistant_reply'),
    # Preserve legacy links while keeping ATS pages as the single analysis flow.
    path('analyse/', RedirectView.as_view(pattern_name='ats_analyse', permanent=True), name='analyse'),
    path('results/', RedirectView.as_view(url='/#composer', permanent=False), name='results'),
]

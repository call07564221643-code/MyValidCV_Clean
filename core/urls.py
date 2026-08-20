from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('assistant/', views.assistant_reply, name='assistant_reply'),
    path('feedback/', views.submit_feedback, name='submit_feedback'),
    path('robots.txt', views.robots_txt, name='robots_txt'),
    path('sitemap.xml', views.sitemap_xml, name='sitemap_xml'),
    path('privacy/analytics-consent/', views.analytics_consent, name='analytics_consent'),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    # Preserve legacy links while keeping ATS pages as the single analysis flow.
    path('analyse/', RedirectView.as_view(pattern_name='ats_analyse', permanent=True), name='analyse'),
    path('results/', RedirectView.as_view(url='/#composer', permanent=False), name='results'),
]

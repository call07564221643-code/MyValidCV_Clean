"""Main URL configuration for MyValidCV."""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

admin.site.site_header = 'MyValidCV Admin'
admin.site.site_title = 'MyValidCV Admin'
admin.site.index_title = 'MyValidCV Control Panel'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('', include('accounts.urls')),
    path('', include('payments.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('ats/', include('ats.urls')),
    path('accounts/', include('allauth.urls')),
    path('analytics/', include('analytics.urls')),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

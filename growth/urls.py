from django.urls import path

from . import views


urlpatterns = [
    path("", views.partner_dashboard, name="partner_dashboard"),
    path("affiliate-guide/", views.affiliate_guide, name="affiliate_guide"),
    path("apply/", views.affiliate_apply, name="affiliate_apply"),
    path("affiliate/<int:partner_id>/agreement/accept/", views.accept_affiliate_agreement, name="accept_affiliate_agreement"),
]

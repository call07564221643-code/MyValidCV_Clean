from django.urls import path

from . import views


urlpatterns = [
    path("affiliate/<int:partner_id>/payout/review/", views.affiliate_payout_review, name="affiliate_payout_review"),
    path("affiliate/<int:partner_id>/payout/", views.save_affiliate_payout, name="save_affiliate_payout"),
    path("", views.partner_dashboard, name="partner_dashboard"),
    path("affiliate-guide/", views.affiliate_guide, name="affiliate_guide"),
    path("apply/", views.affiliate_apply, name="affiliate_apply"),
    path("application/", views.affiliate_application_status, name="affiliate_application_status"),
    path("owner/affiliates/", views.affiliate_owner_dashboard, name="affiliate_owner_dashboard"),
    path("affiliate/<int:partner_id>/agreement/accept/", views.accept_affiliate_agreement, name="accept_affiliate_agreement"),
]

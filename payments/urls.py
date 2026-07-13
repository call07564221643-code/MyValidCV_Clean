from django.urls import path

from . import views


urlpatterns = [
    path("pricing/", views.pricing, name="pricing"),
    path("checkout/<slug:plan_code>/", views.start_checkout, name="start_checkout"),
    path("stripe/checkout/<slug:plan_code>/", views.start_stripe_checkout, name="start_stripe_checkout"),
    path("stripe/mock/<str:checkout_reference>/", views.stripe_mock_checkout, name="stripe_mock_checkout"),
    path("stripe/success/<str:checkout_reference>/", views.stripe_success, name="stripe_success"),
    path("receipt/<str:checkout_reference>/", views.payment_receipt, name="payment_receipt"),
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
    path("sumup/return/<str:checkout_reference>/", views.sumup_return, name="sumup_return"),
    path("sumup/webhook/", views.sumup_webhook, name="sumup_webhook"),
]

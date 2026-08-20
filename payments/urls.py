from django.urls import path

from . import views


urlpatterns = [
    # Public catalogue. Checkout creation below is protected in the view.
    path("pricing/", views.pricing, name="pricing"),
    # Browser payment stages: authenticated POST -> provider -> verified return.
    path("checkout/<slug:plan_code>/", views.start_checkout, name="start_checkout"),
    path("stripe/mock/<str:checkout_reference>/", views.stripe_mock_checkout, name="stripe_mock_checkout"),
    path("checkout/success/<str:checkout_reference>/", views.stripe_success, name="checkout_success"),
    path("receipt/<str:checkout_reference>/", views.payment_receipt, name="payment_receipt"),
    # Provider-to-server callbacks do not use user sessions; their views must
    # independently authenticate the provider payload before changing access.
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
    path("sumup/return/<str:checkout_reference>/", views.sumup_return, name="sumup_return"),
    path("sumup/webhook/", views.sumup_webhook, name="sumup_webhook"),
    path("sumup/test/<slug:plan_code>/", views.start_sumup_sandbox_test, name="sumup_sandbox_test"),
]

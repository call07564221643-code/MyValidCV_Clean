from django.db.models.signals import post_save
from django.dispatch import receiver

from payments.models import PaymentTransaction, Refund

from .services import reverse_referral_commission


@receiver(post_save, sender=Refund)
def reverse_commission_after_processed_refund(sender, instance, **kwargs):
    if instance.status == "processed":
        reverse_referral_commission(instance.transaction, "Customer payment refunded")


@receiver(post_save, sender=PaymentTransaction)
def reverse_commission_after_transaction_refund(sender, instance, **kwargs):
    if instance.status == "refunded":
        reverse_referral_commission(instance, "Payment transaction marked refunded")

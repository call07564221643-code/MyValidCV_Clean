from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("subscriptions", "0001_initial")]
    operations = [
        migrations.AddField(
            model_name="subscriptionplan",
            name="stripe_price_id",
            field=models.CharField(blank=True, help_text="Optional Stripe Price ID. If blank, Checkout creates recurring price data from this plan.", max_length=120),
        ),
        migrations.AddField(
            model_name="customersubscription",
            name="stripe_customer_id",
            field=models.CharField(blank=True, db_index=True, max_length=120),
        ),
        migrations.AddField(
            model_name="customersubscription",
            name="stripe_subscription_id",
            field=models.CharField(blank=True, db_index=True, max_length=120),
        ),
    ]

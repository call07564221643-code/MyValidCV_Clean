from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("payments", "0003_invoice_invoice_status_date_idx_and_more")]
    operations = [
        migrations.AddField(
            model_name="paymentwebhooklog",
            name="event_id",
            field=models.CharField(blank=True, max_length=120, null=True, unique=True),
        ),
    ]

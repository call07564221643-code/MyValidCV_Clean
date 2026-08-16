from django.conf import settings
from django.db import migrations


def backfill_cv_storage(apps, schema_editor):
    User = apps.get_model(settings.AUTH_USER_MODEL.split(".")[0], settings.AUTH_USER_MODEL.split(".")[1])
    CV = apps.get_model("ats", "CV")
    CVStorage = apps.get_model("ats", "CVStorage")

    for user in User.objects.all().iterator():
        storage, _created = CVStorage.objects.get_or_create(user_id=user.id)
        CV.objects.filter(user_id=user.id, storage__isnull=True).update(storage=storage)


def reverse_backfill(apps, schema_editor):
    CV = apps.get_model("ats", "CV")
    CV.objects.update(storage=None)


class Migration(migrations.Migration):

    dependencies = [
        ("ats", "0005_atsresult_metrics_atsresult_public_id_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_cv_storage, reverse_backfill),
    ]

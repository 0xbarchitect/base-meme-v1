# Generated by Django 5.0.6 on 2024-08-24 04:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("console", "0013_blacklist_frozen_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="position",
            name="investment",
            field=models.FloatField(null=True),
        ),
        migrations.AddField(
            model_name="position",
            name="returns",
            field=models.FloatField(null=True),
        ),
    ]

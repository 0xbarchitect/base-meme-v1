# Generated by Django 5.0.6 on 2024-08-24 04:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("console", "0015_executor_pnl"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pnl",
            name="timestamp",
            field=models.CharField(max_length=20, unique=True),
        ),
    ]

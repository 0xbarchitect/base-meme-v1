# Generated by Django 5.0.6 on 2024-07-08 05:05

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('console', '0002_rename_amount0diff_block_amount0_diff_and_more'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Swap_Event',
            new_name='SwapEvent',
        ),
    ]

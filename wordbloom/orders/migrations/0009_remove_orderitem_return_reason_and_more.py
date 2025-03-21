# Generated by Django 5.1.3 on 2025-02-26 04:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0008_remove_orderitem_is_returned_orderitem_return_reason_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='orderitem',
            name='return_reason',
        ),
        migrations.RemoveField(
            model_name='orderitem',
            name='return_status',
        ),
        migrations.RemoveField(
            model_name='orderitem',
            name='returned_at',
        ),
        migrations.AddField(
            model_name='orderitem',
            name='is_returned',
            field=models.BooleanField(default=False),
        ),
    ]

# Generated by Django 5.1.3 on 2025-02-25 13:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0006_remove_ordermain_category_discount_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='ordermain',
            name='discount_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]

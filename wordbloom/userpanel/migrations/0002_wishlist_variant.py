# Generated by Django 5.1.3 on 2025-01-28 12:14

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0002_remove_product_discounted_price_and_more'),
        ('userpanel', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='wishlist',
            name='variant',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='products.productvariant'),
        ),
    ]

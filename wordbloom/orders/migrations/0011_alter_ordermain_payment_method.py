# Generated by Django 5.1.3 on 2025-03-19 09:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0010_shippingaddress_ordermain_shipping_address'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ordermain',
            name='payment_method',
            field=models.CharField(choices=[('COD', 'Cash on Delivery'), ('Razorpay', 'Razorpay'), ('Wallet', 'Wallet')], max_length=50),
        ),
    ]

# orders/management/commands/test_razorpay.py
from django.core.management.base import BaseCommand
from django.conf import settings
import razorpay

class Command(BaseCommand):
    help = 'Test Razorpay connection and credentials'

    def handle(self, *args, **options):
        try:
            # Initialize client
            client = razorpay.Client(
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
            )
            
            # Try to create a test order
            test_order = {
                'amount': 100,  # 1 rupee in paise
                'currency': 'INR',
                'receipt': 'test_receipt_id',
                'notes': {'purpose': 'testing'}
            }
            
            # Create order
            response = client.order.create(test_order)
            
            self.stdout.write(self.style.SUCCESS(f'Successfully connected to Razorpay'))
            self.stdout.write(f'Test order created with ID: {response["id"]}')
            
            # Try to fetch the created order
            fetched_order = client.order.fetch(response['id'])
            self.stdout.write(f'Successfully fetched order details: {fetched_order}')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
            self.stdout.write(self.style.ERROR('Full error details:'))
            import traceback
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
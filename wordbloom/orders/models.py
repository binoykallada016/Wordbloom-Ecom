# from django.db import models
# from accounts.models import User
# from products.models import ProductVariant
# from userpanel.models import UserAddress
# from django.utils import timezone

# PAYMENT_METHOD_CHOICES = [
#     ('COD', 'Cash on Delivery'),
#     ('Razorpay', 'Razorpay'),
#     ('Wallet', 'Wallet'),
#     # Add other payment methods if needed
# ]

# class ShippingAddress(models.Model):    
#     name = models.CharField(max_length=100)
#     phone_number = models.CharField(max_length=15)
#     house_name = models.CharField(max_length=100)
#     street_name = models.CharField(max_length=100)
#     district = models.CharField(max_length=100)
#     state = models.CharField(max_length=100)
#     country = models.CharField(max_length=100)
#     pin_number = models.CharField(max_length=10)
#     created_at = models.DateTimeField(auto_now_add=True)
    
#     def __str__(self):
#         return f"{self.name}'s address at {self.house_name}, {self.street_name}"

#     def get_full_address(self):
#         return f"{self.house_name}, {self.street_name}, {self.district}, {self.state}, {self.country} - {self.pin_number}"


# class OrderMain(models.Model):
#     ORDER_STATUS_CHOICES = [
#         ('Pending', 'Pending'),
#         ('Payment_Pending', 'Payment Pending'),
#         ('Confirmed', 'Confirmed'),
#         ('Shipped', 'Shipped'),
#         ('Delivered', 'Delivered'),
#         ('Cancelled', 'Cancelled'),
#         ('Return_Initiated', 'Return Initiated'),
#         ('Return_Approved', 'Return Approved'),
#         ('Return_Rejected', 'Return Rejected'),
#     ]
#     PAYMENT_STATUS_CHOICES = [
#         ('Pending', 'Pending'),
#         ('Success', 'Success'),
#         ('Failed', 'Failed')
#     ]
#     user = models.ForeignKey(User, on_delete=models.CASCADE)
#     address = models.ForeignKey(UserAddress, on_delete=models.SET_NULL, null=True)
#     shipping_address = models.ForeignKey(ShippingAddress, on_delete=models.PROTECT, null=True)
#     total_amount = models.DecimalField(max_digits=10, decimal_places=2)
#     order_status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='Pending')
#     payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES)
#     payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='Pending')
#     payment_id = models.CharField(max_length=100, null=True, blank=True)
#     razorpay_order_id = models.CharField(max_length=100, null=True, blank=True)
#     order_id = models.CharField(max_length=50, unique=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

#     @property
#     def estimated_delivery_date(self):
#         return self.created_at + timezone.timedelta(days=7)

#     def __str__(self):
#         return f"Order {self.order_id} by {self.user.username}"

#     def get_total_cost(self):
#         return sum(item.get_cost() for item in self.items.all())

#     def refund_amount(self):
#         return sum(item.get_cost() for item in self.items.filter(is_cancelled=False))
    

# class OrderItem(models.Model):
#     order = models.ForeignKey(OrderMain, on_delete=models.CASCADE, related_name='items')
#     product_variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True)
#     quantity = models.PositiveIntegerField()
#     price = models.DecimalField(max_digits=10, decimal_places=2)
#     is_cancelled = models.BooleanField(default=False)
#     is_returned = models.BooleanField(default=False)

#     def get_cost(self):
#         return self.price * self.quantity
#     @property
#     def total_cost(self):
#         return self.quantity * self.price

#     def __str__(self):
#         return f"{self.quantity} x {self.product_variant} in Order {self.order.order_id}"

# class ReturnRequest(models.Model):
#     RETURN_STATUS_CHOICES = [
#         ('Pending', 'Pending'),
#         ('Approved', 'Approved'),
#         ('Rejected', 'Rejected'),
#     ]
#     order = models.ForeignKey(OrderMain, on_delete=models.CASCADE)
#     item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, null=True, blank=True)
#     reason = models.TextField()
#     status = models.CharField(max_length=20, choices=RETURN_STATUS_CHOICES, default='Pending')
#     created_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"Return request for Order {self.order.order_id}" 



from django.db import models
from accounts.models import User
from products.models import ProductVariant
from userpanel.models import UserAddress
from django.utils import timezone

PAYMENT_METHOD_CHOICES = [
    ('COD', 'Cash on Delivery'),
    ('Razorpay', 'Razorpay'),
    ('Wallet', 'Wallet'),
]

class ShippingAddress(models.Model):    
    name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=15)
    house_name = models.CharField(max_length=100)
    street_name = models.CharField(max_length=100)
    district = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    pin_number = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name}'s address at {self.house_name}, {self.street_name}"

    def get_full_address(self):
        return f"{self.house_name}, {self.street_name}, {self.district}, {self.state}, {self.country} - {self.pin_number}"


class OrderMain(models.Model):
    ORDER_STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Payment_Pending', 'Payment Pending'),
        ('Confirmed', 'Confirmed'),
        ('Shipped', 'Shipped'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled'),
        ('Return_Initiated', 'Return Initiated'),
        ('Return_Approved', 'Return Approved'),
        ('Return_Rejected', 'Return Rejected'),
    ]
    PAYMENT_STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Success', 'Success'),
        ('Failed', 'Failed')
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    address = models.ForeignKey(UserAddress, on_delete=models.SET_NULL, null=True)
    shipping_address = models.ForeignKey(ShippingAddress, on_delete=models.PROTECT, null=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    order_status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='Pending')
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='Pending')
    payment_id = models.CharField(max_length=100, null=True, blank=True)
    razorpay_order_id = models.CharField(max_length=100, null=True, blank=True)
    order_id = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    @property
    def estimated_delivery_date(self):
        return self.created_at + timezone.timedelta(days=7)

    def __str__(self):
        return f"Order {self.order_id} by {self.user.username}"

    def get_total_cost(self):
        return sum(item.get_cost() for item in self.items.all())

    def refund_amount(self):
        return sum(item.get_cost() for item in self.items.filter(is_cancelled=False))
    

class OrderItem(models.Model):
    order = models.ForeignKey(OrderMain, on_delete=models.CASCADE, related_name='items')
    product_variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_cancelled = models.BooleanField(default=False)
    is_returned = models.BooleanField(default=False)
    is_refunded = models.BooleanField(default=False)
    refunded_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def get_cost(self):
        return self.price * self.quantity
    
    @property
    def total_cost(self):
        return self.quantity * self.price

    def __str__(self):
        return f"{self.quantity} x {self.product_variant} in Order {self.order.order_id}"

class ReturnRequest(models.Model):
    RETURN_STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]
    order = models.ForeignKey(OrderMain, on_delete=models.CASCADE)
    item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, null=True, blank=True)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=RETURN_STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)
    refunded_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    refunded_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Return request for Order {self.order.order_id}" 


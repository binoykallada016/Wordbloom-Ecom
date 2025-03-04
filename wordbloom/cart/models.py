from django.db import models
from accounts.models import User
from products.models import Product, ProductVariant
from coupons.models import Coupon

class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Cart of {self.user}"

    def get_total_price(self):
        return sum(item.sub_total() for item in self.items.all())

    def get_discount_amount(self):
        if self.coupon:
            discount = self.coupon.discount
            max_discount = self.coupon.maximum_amount
            total_price = self.get_total_price()
            discount_amount = (total_price * discount) / 100
            return min(discount_amount, max_discount)
        return 0

    def get_total_price_after_discount(self):
        return self.get_total_price() - self.get_discount_amount()

class CartItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')    
    quantity = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)    

    def sub_total(self):
        variant_price = self.variant.discounted_price if self.variant.discounted_price else self.variant.price
        return variant_price * self.quantity


    def __str__(self):
        return f"{self.quantity} of {self.product} in {self.cart}"


    def is_valid_quantity(self):
        """
        Check if the current quantity is within the variant's available stock
        """
        return self.quantity <= self.variant.stock
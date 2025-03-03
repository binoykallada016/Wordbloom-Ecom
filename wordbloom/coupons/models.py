
from django.db import models
from accounts.models import User
from orders.models import OrderMain
from django.utils import timezone

# Create your models here.
class Coupon(models.Model):
    coupon_name = models.CharField(max_length=100, null=False)
    minimum_amount = models.IntegerField(null=False)
    discount = models.IntegerField(null=False)
    maximum_amount = models.IntegerField(null=False, default=0)
    expiry_date = models.DateField(null=False)
    coupon_code = models.CharField(max_length=50, null=False, unique=True)
    status = models.BooleanField(default=True)

    def __str__(self):
        return self.coupon_code

    def is_valid(self, total_amount):
        now = timezone.now().date()
        return (
            self.status
            and self.expiry_date >= now
            and total_amount >= self.minimum_amount
        )

class UserCoupon(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, null=True)
    used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    order = models.ForeignKey(OrderMain, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return f"{self.user.email} - {self.coupon.coupon_code}"



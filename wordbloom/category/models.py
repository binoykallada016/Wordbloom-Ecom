# from django.db import models
# from django.utils.text import slugify

# class Category(models.Model):
#     name = models.CharField(max_length=255, unique=True)
#     slug = models.SlugField(max_length=255, unique=True, blank=True)
#     description = models.TextField()
#     is_active = models.BooleanField(default=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     def save(self, *args, **kwargs):
#         if not self.slug:
#             self.slug = slugify(self.name)
#         super(Category, self).save(*args, **kwargs)

#     def __str__(self):
#         return self.name
    

# class CategoryOffer(models.Model):
#     DISCOUNT_TYPE_CHOICES = [
#         ('Percentage', 'Percentage'),
#         ('Flat', 'Flat'),
#     ]
#     category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='offers')
#     offer_name = models.CharField(max_length=255)
#     discount_type = models.CharField(max_length=50, choices=DISCOUNT_TYPE_CHOICES)
#     discount_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
#     minimum_purchase_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
#     start_date = models.DateTimeField()
#     end_date = models.DateTimeField()
#     is_active = models.BooleanField(default=True)
#     is_available = models.BooleanField(default=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         verbose_name = "Category Offer"
#         verbose_name_plural = "Category Offers"

#     def __str__(self):
#         return f"{self.offer_name} - {self.category.name}"



from django.db import models
from django.utils.text import slugify

class Category(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super(Category, self).save(*args, **kwargs)

    def __str__(self):
        return self.name
    

class CategoryOffer(models.Model):
    DISCOUNT_TYPE_CHOICES = [
        ('Percentage', 'Percentage'),
        ('Flat', 'Flat'),
    ]
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='offers')
    offer_name = models.CharField(max_length=255)
    discount_type = models.CharField(max_length=50, choices=DISCOUNT_TYPE_CHOICES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    minimum_purchase_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Category Offer"
        verbose_name_plural = "Category Offers"

    def __str__(self):
        return f"{self.offer_name} - {self.category.name}"

    def calculate_discount(self, original_price):
        if not self.is_active:
            return 0
        
        if self.minimum_purchase_amount and original_price < self.minimum_purchase_amount:
            return 0
            
        if self.discount_type == 'Percentage':
            return (original_price * self.discount_value) / 100
        return self.discount_value  # For 'Flat' discount type
from django.db import models
from cloudinary.models import CloudinaryField
from category.models import Category
from django.utils import timezone
from authors.models import Author
from category.models import CategoryOffer

class Product(models.Model):
    product_id = models.AutoField(primary_key=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    product_name = models.CharField(max_length=200)
    product_description = models.TextField()
    language = models.CharField(max_length=50, default='en')
    publication_date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.product_name

class ProductVariant(models.Model):
    FORMAT_CHOICES = (
        ('Paperback', 'Paperback'),
        ('Hardcover', 'Hardcover'),
        ('eBook', 'eBook'),
    )    
    product = models.ForeignKey(Product, related_name='variants', on_delete=models.CASCADE)
    format = models.CharField(max_length=50, choices=FORMAT_CHOICES)
    isbn = models.CharField(max_length=13, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discounted_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock = models.IntegerField()
    page_count = models.IntegerField(default=100)
    is_active = models.BooleanField(default=True)

    def get_primary_image(self):
        return self.images.filter(is_primary=True).first()
    
    
    def __str__(self):
        return f"{self.product.product_name} - {self.format}"
    
    def get_effective_price(self):
    # Get product discount price (if any)
        if self.discounted_price is not None:
            product_effective_price = self.discounted_price
            product_discount = self.price - self.discounted_price
        else:
            product_effective_price = self.price
            product_discount = 0

        # Check for category offer
        try:
            category_offer = self.product.category.offers.filter(
                is_active=True, 
                start_date__lte=timezone.now(),
                end_date__gte=timezone.now()
            ).first()
            
            if category_offer:
                category_discount = category_offer.calculate_discount(self.price)
                category_effective_price = self.price - category_discount
            else:
                category_effective_price = self.price
                category_discount = 0
        except Exception:
            category_effective_price = self.price
            category_discount = 0

        # Return price with maximum discount
        if category_effective_price < product_effective_price:
            return category_effective_price
        else:
            return product_effective_price
        
    def get_discount_info(self):
    # Get product discount price (if any)
        if self.discounted_price is not None:
            product_effective_price = self.discounted_price
            product_discount = self.price - self.discounted_price
        else:
            product_effective_price = self.price
            product_discount = 0

        # Check for category offer
        try:
            category_offer = self.product.category.offers.filter(
                is_active=True, 
                start_date__lte=timezone.now(),
                end_date__gte=timezone.now()
            ).first()
            
            if category_offer:
                category_discount = category_offer.calculate_discount(self.price)
                category_effective_price = self.price - category_discount
                category_offer_name = category_offer.offer_name
            else:
                category_effective_price = self.price
                category_discount = 0
                category_offer_name = None
        except Exception:
            category_effective_price = self.price
            category_discount = 0
            category_offer_name = None

        # Determine which discount to display
        if category_effective_price < product_effective_price:
            return {
                'type': 'category',
                'offer_name': category_offer_name,
                'original_price': self.price,
                'effective_price': category_effective_price,
                'discount_amount': category_discount
            }
        else:
            return {
                'type': 'product',
                'original_price': self.price,
                'effective_price': product_effective_price,
                'discount_amount': product_discount
            }

class VariantImage(models.Model):
    image_id = models.AutoField(primary_key=True)
    variant = models.ForeignKey(ProductVariant, related_name='images', on_delete=models.CASCADE)
    image = CloudinaryField('image')
    is_primary = models.BooleanField(default=False)
    display_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order']

    def __str__(self):
        return f"Image for {self.variant.product.product_name} - {self.variant.format}"
    
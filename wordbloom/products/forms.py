from django import forms
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from .models import Product, ProductVariant, VariantImage, Author

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'product_name',
            'product_description',
            'category',
            'author',
            'language',
            'publication_date',
        ]
        widgets = {
            'publication_date': forms.DateInput(attrs={'type': 'date'}),
            'product_description': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['author'].queryset = Author.objects.filter(is_active=True)
        for field_name, field in self.fields.items():
            if field.required:
                field.label = f"{field.label}*"

class ProductVariantForm(forms.ModelForm):
    price = forms.DecimalField(validators=[MinValueValidator(0)])
    # discounted_price = forms.DecimalField(validators=[MinValueValidator(0)])
    discounted_price = forms.DecimalField(required=False)
    stock = forms.IntegerField(validators=[MinValueValidator(0)])
    page_count = forms.IntegerField(validators=[MinValueValidator(1)])

    class Meta:
        model = ProductVariant
        fields = [
            'format',
            'isbn',
            'price',
            'discounted_price',
            'stock',
            'page_count',
            'is_active',
        ]
        widgets = {
            'price': forms.NumberInput(attrs={'min': '0', 'step': '0.01'}),
            'discounted_price': forms.NumberInput(attrs={'min': '0', 'step': '0.01'}),
            'stock': forms.NumberInput(attrs={'min': '0'}),
            'page_count': forms.NumberInput(attrs={'min': '1'}),
        }

    def clean_isbn(self):
        isbn = self.cleaned_data.get('isbn')
        if isbn:
            isbn = isbn.replace('-', '').replace(' ', '')
            if not isbn.isdigit():
                raise ValidationError("ISBN should contain only digits")
            
            if len(isbn) != 13:
                raise ValidationError("ISBN must be 13 digits long")
                
            if ProductVariant.objects.filter(isbn=isbn).exclude(
                pk=self.instance.pk if self.instance else None
            ).exists():
                raise ValidationError("This ISBN is already in use")
        return isbn    

    def clean(self):
        cleaned_data = super().clean()
        price = cleaned_data.get('price')
        discounted_price = cleaned_data.get('discounted_price')
        stock = cleaned_data.get('stock')

        if price and discounted_price:
            if discounted_price >= price:
                raise ValidationError({
                    'discounted_price': "Discounted price must be less than regular price"
                })

        if stock is not None and stock < 0:
            raise ValidationError({
                'stock': "Stock cannot be negative"
            })

        return cleaned_data



class VariantImageForm(forms.ModelForm):
    display_order = forms.IntegerField(validators=[MinValueValidator(0)])

    class Meta:
        model = VariantImage
        fields = ['image', 'is_primary', 'display_order']
        widgets = {
            'display_order': forms.NumberInput(attrs={'min': '0'}),
        }

    def clean_is_primary(self):
        is_primary = self.cleaned_data.get('is_primary')
        if self.instance.pk is None:  # New image
            if is_primary and self.instance.variant.images.filter(is_primary=True).exists():
                raise ValidationError("Another image is already set as primary for this variant")
        return is_primary
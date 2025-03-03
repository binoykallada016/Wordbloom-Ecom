from django import forms
from django.core.exceptions import ValidationError
from products.models import ProductVariant

class AddToCartForm(forms.Form):
    variant_id = forms.IntegerField()
    quantity = forms.IntegerField(min_value=1, max_value=5)

    def clean_variant_id(self):
        variant_id = self.cleaned_data.get('variant_id')
        try:
            variant = ProductVariant.objects.get(id=variant_id, is_active=True)
            return variant_id
        except ProductVariant.DoesNotExist:
            raise ValidationError("Selected variant is not available.")

    def clean_quantity(self):
        variant_id = self.cleaned_data.get('variant_id')
        quantity = self.cleaned_data.get('quantity')
        
        if variant_id:
            try:
                variant = ProductVariant.objects.get(id=variant_id)
                if quantity > variant.stock:
                    raise ValidationError(f"Only {variant.stock} items available in stock.")
            except ProductVariant.DoesNotExist:
                pass
        
        return quantity

class UpdateCartForm(forms.Form):
    item_id = forms.IntegerField()
    quantity = forms.IntegerField(min_value=1, max_value=5, required=False)
    action = forms.ChoiceField(choices=[('update', 'Update'), ('remove', 'Remove')])
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import CouponForm
from .models import Coupon
from cart.models import Cart
from django.utils import timezone
from utils.decorators import admin_required
from django.http import JsonResponse
import random
import string
import json
from decimal import Decimal
from django.conf import settings

# Create your views here.
@admin_required
def list_coupon(request):
    coupons = Coupon.objects.all()
    return render(request, 'adminside/coupon/list_coupon.html', {'coupons': coupons})

@admin_required
def create_coupon(request):
    if request.method == 'POST':
        form = CouponForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('coupons:list-coupon')
    else:
        form = CouponForm()
    return render(request, 'adminside/coupon/create_edit_coupon.html', {'form': form})

def generate_coupon_code(request):
    if request.method == "GET":
        length = 8  # Length of the coupon code
        characters = string.ascii_uppercase + string.digits
        coupon_code = ''.join(random.choice(characters) for _ in range(length))
        return JsonResponse({'coupon_code': coupon_code})


@admin_required
def edit_coupon(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)
    if request.method == 'POST':
        form = CouponForm(request.POST, instance=coupon)
        if form.is_valid():
            form.save()
            return redirect('coupons:list-coupon')
    else:
        form = CouponForm(instance=coupon)
    return render(request, 'adminside/coupon/create_edit_coupon.html', {'form': form})

@admin_required
def coupon_status(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)
    coupon.status = not coupon.status
    coupon.save()
    return redirect('coupons:list-coupon')

@login_required
def apply_coupon(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            code = data.get('code')
            try:
                coupon = Coupon.objects.get(coupon_code=code, status=True)
                cart = Cart.objects.get(user=request.user)
                
                # Recalculate cart total using effective prices
                cart_total = Decimal('0.00')
                for item in cart.items.filter(is_active=True):
                    variant = item.variant
                    effective_price = Decimal(str(variant.get_effective_price()))
                    cart_total += effective_price * item.quantity

                if coupon.is_valid(cart_total):
                    cart.coupon = coupon
                    cart.save()
                    
                    # Recalculate discount amount
                    discount_amount = cart.get_discount_amount()
                    total_after_discount = cart_total - Decimal(str(discount_amount)) + Decimal(settings.SHIPPING_CHARGE)
                    
                    return JsonResponse({
                        'success': True,
                        'message': 'Coupon applied successfully!',
                        'cart_total': float(cart_total),
                        'discount_amount': float(discount_amount),
                        'total_after_discount': float(total_after_discount)
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'message': 'This coupon is not valid for your order.'
                    })
            except Coupon.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid coupon code.'
                })
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid request format.'
            })
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method.'
    })

@login_required
def remove_coupon(request):
    if request.method == 'POST':
        try:
            cart = Cart.objects.get(user=request.user)
            cart.coupon = None
            cart.save()
            
            # Recalculate cart total using effective prices
            cart_total = Decimal('0.00')
            for item in cart.items.filter(is_active=True):
                variant = item.variant
                effective_price = Decimal(str(variant.get_effective_price()))
                cart_total += effective_price * item.quantity
            
            # Recalculate total after discount
            total_after_discount = cart_total + Decimal(settings.SHIPPING_CHARGE)
            
            return JsonResponse({
                'success': True,
                'message': 'Coupon removed successfully!',
                'cart_total': float(cart_total),
                'total_after_discount': float(total_after_discount)
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error removing coupon: {str(e)}'
            })
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method.'
    })
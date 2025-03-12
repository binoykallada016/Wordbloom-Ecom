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
        code = request.POST.get('code')
        try:
            coupon = Coupon.objects.get(coupon_code=code, status=True)
            cart = Cart.objects.get(user=request.user)
            total_amount = cart.get_total_price()

            if coupon.is_valid(total_amount):
                cart.coupon = coupon
                cart.save()
                messages.success(request, 'Coupon applied successfully!')
            else:
                messages.error(request, 'This coupon is not valid for your order.')
        except Coupon.DoesNotExist:
            messages.error(request, 'Invalid coupon code.')
    return redirect('cart:cart-view')

@login_required
def remove_coupon(request):
    if request.method == 'POST':
        cart = Cart.objects.get(user=request.user)
        cart.coupon = None
        cart.save()
        messages.success(request, 'Coupon removed successfully!')
    return redirect('cart:cart-view')
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Cart, CartItem
from products.models import ProductVariant
from userpanel.models import UserAddress
from userpanel.forms import AddressForm
from .forms import AddToCartForm, UpdateCartForm
from coupons.forms import CouponForm
from django.contrib import messages
import json
from userpanel.models import UserAddress, Wallet, WalletTransaction
from decimal import Decimal
from django.conf import settings

# Create your views here.

@login_required
def validate_cart_items(request, cart_items):
    """
    Validates cart items for availability and stock levels.
    Returns tuple (is_valid, invalid_items)
    """
    invalid_items = []
    is_valid = True
    
    for item in cart_items:
        try:
            variant = ProductVariant.objects.get(id=item.variant.id)
            
            # Check if variant is active
            if not variant.is_active:
                invalid_items.append({
                    'item': item,
                    'reason': 'no_longer_available',
                    'message': f"{item.variant.product.product_name} - {item.variant.format} is no longer available"
                })
                item.delete()  # Remove inactive item from cart
                is_valid = False
                continue
                
            # Check stock availability
            if item.quantity > variant.stock:
                invalid_items.append({
                    'item': item,
                    'reason': 'insufficient_stock',
                    'message': f"Only {variant.stock} units available for {item.variant.product.product_name} - {item.variant.format}"
                })
                # Update quantity to maximum available
                item.quantity = variant.stock
                item.save()
                is_valid = False
                
        except ProductVariant.DoesNotExist:
            invalid_items.append({
                'item': item,
                'reason': 'variant_not_found',
                'message': f"Product variant no longer exists"
            })
            item.delete()
            is_valid = False
            
    return is_valid, invalid_items

@login_required
def validate_and_clean_cart(request):
    """
    Validates cart items and displays appropriate messages.
    Returns True if cart is valid, False otherwise.
    """
    cart = request.user.cart_set.first()
    if not cart:
        messages.error(request, "Your cart is empty.")
        return False
        
    cart_items = cart.items.filter(is_active=True)
    if not cart_items.exists():
        messages.error(request, "Your cart is empty.")
        return False
        
    is_valid, invalid_items = validate_cart_items(request, cart_items)
    
    for invalid_item in invalid_items:
        messages.warning(request, invalid_item['message'])
    
    return is_valid

@login_required
def cart_view(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    cart_items = cart.items.filter(is_active=True)
    
    # Validate cart items
    validate_and_clean_cart(request)
    
    # Refresh cart items after validation
    cart_items = cart.items.filter(is_active=True)
    
    if request.method == 'POST':
        form = UpdateCartForm(request.POST)
        if form.is_valid():
            item_id = form.cleaned_data['item_id']
            quantity = form.cleaned_data['quantity']
            action = form.cleaned_data['action']
            
            try:
                cart_item = cart.items.get(id=item_id)
                if action == 'update':
                    # Validate stock before updating quantity
                    if quantity > cart_item.variant.stock:
                        messages.error(request, f"Only {cart_item.variant.stock} units available.")
                    else:
                        cart_item.quantity = quantity
                        cart_item.save()
                        messages.success(request, "Cart updated successfully.")
                elif action == 'remove':
                    cart_item.delete()
                    messages.success(request, 'Item removed from cart.')
                return redirect('cart:cart-view')
            except CartItem.DoesNotExist:
                messages.error(request, 'Item not found in cart.')
    
    cart_total = cart.get_total_price()
    discount_amount = cart.get_discount_amount()
    shipping_charge = getattr(settings, "SHIPPING_CHARGE", Decimal('50.00'))
    total_after_discount = Decimal(cart.get_total_price_after_discount()) + Decimal(settings.SHIPPING_CHARGE)
    update_form = UpdateCartForm()
    coupon_form = CouponForm()
    
    context = {
        'cart_items': cart_items,
        'cart_total': cart_total,
        'discount_amount': discount_amount,
        'total_after_discount': total_after_discount,
        'update_form': update_form,
        'coupon_form': coupon_form,
        'shipping_charge': shipping_charge,
    }
    return render(request, 'userside/cart/cart_view.html', context)



@login_required
def add_to_cart(request):
    if request.method == 'POST':
        form = AddToCartForm(request.POST)
        if form.is_valid():
            variant_id = form.cleaned_data['variant_id']
            quantity = form.cleaned_data['quantity']
            
            variant = get_object_or_404(ProductVariant, id=variant_id)
            
            # Check variant availability
            if not variant.is_active or variant.stock < quantity:
                messages.error(request, 'Selected variant is not available or insufficient stock.')
                return redirect('accounts:shop')
            
            # Create or update cart
            cart, _ = Cart.objects.get_or_create(user=request.user)
            
            # Try to get existing cart item or create new
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                variant=variant,
                product=variant.product
            )
            
            # Update quantity
            if not created:
                cart_item.quantity += quantity
            else:
                cart_item.quantity = quantity
            
            # Ensure we don't exceed stock
            cart_item.quantity = min(cart_item.quantity, variant.stock)
            cart_item.save()
            
            messages.success(request, 'Item added to cart successfully.')
            return redirect('cart:cart-view')
        
        # If form is invalid
        messages.error(request, 'Error adding item to cart.')
        return redirect('accounts:shop')
    
    # If not a POST request
    return redirect('accounts:shop')



@login_required
def remove_item(request, item_id):
    try:
        cart_item = CartItem.objects.get(id=item_id, cart__user=request.user)
        cart_item.delete()
        
        # Recalculate cart total
        cart = Cart.objects.get(user=request.user)
        cart_items = CartItem.objects.filter(cart=cart)
        cart_total = sum(item.sub_total() for item in cart_items)
        
        return JsonResponse({
            'status': 'success',
            'cart_total': cart_total,
            'cart_empty': not cart_items.exists()
        })
    except CartItem.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Item not found'}, status=404)


@login_required
def update_cart_quantity(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        item_id = data.get('item_id')
        quantity = data.get('quantity')
        
        try:
            cart_item = CartItem.objects.get(id=item_id, cart__user=request.user)
            cart_item.quantity = int(quantity)
            cart_item.save()
            
            # Recalculate cart total
            cart = Cart.objects.get(user=request.user)
            cart_items = CartItem.objects.filter(cart=cart)
            cart_total = sum(item.sub_total() for item in cart_items)
            
            return JsonResponse({
                'status': 'success',
                'item_subtotal': cart_item.sub_total(),
                'cart_total': cart_total
            })
        except CartItem.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Item not found'}, status=404)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

@login_required
def checkout(request):
    cart = Cart.objects.get(user=request.user)
    # Validate cart before proceeding
    if not validate_and_clean_cart(request):
        return redirect('cart:cart-view')
    cart_items = cart.items.filter(is_active=True)
    if not cart_items.exists():
        messages.warning(request, "Your cart is empty. Please add items before proceeding to checkout.")
        return redirect('cart:cart-view')
    
    if request.method == 'POST':
        address_id = request.POST.get('address')
        payment_method = request.POST.get('payment_method')
        use_wallet = request.POST.get('use_wallet') == 'on'  # Check if the user wants to use the wallet
        
        if not address_id:
            messages.error(request, "Please select a shipping address.")
            # return redirect('cart:checkout') #Removed to prevent form reset
        elif not payment_method:
            messages.error(request, "Please select a payment method.")
            # return redirect('cart:checkout')
        else:
            address = get_object_or_404(UserAddress, id=address_id, user=request.user)
            
            # Calculate total amount after potential coupon discount
            total_amount = Decimal(cart.get_total_price_after_discount()) + Decimal(settings.SHIPPING_CHARGE)
            
            # --- Wallet Handling ---
            wallet_balance = Decimal('0.00')
            if hasattr(request.user, 'wallet'):
                wallet_balance = request.user.wallet.balance
            
            amount_to_pay = total_amount  # Initialize with total amount
            wallet_used = Decimal('0.00')
            
            if use_wallet:
                if wallet_balance >= total_amount:
                    # Use entire wallet balance
                    wallet_used = total_amount
                    amount_to_pay = Decimal('0.00')  # No further payment needed
                    if payment_method != 'Razorpay':  # Only change payment method if it's not Razorpay
                        payment_method = 'Wallet'  # Set payment method explicitly
                else:
                    # Use partial wallet balance
                    wallet_used = wallet_balance
                    amount_to_pay = total_amount - wallet_balance
            # --- End Wallet Handling ---
            
            # Store data in session for place_order view
            request.session['selected_address_id'] = address_id
            request.session['payment_method'] = payment_method
            request.session['amount_to_pay'] = str(amount_to_pay)  # Convert to string for session
            request.session['wallet_used'] = str(wallet_used)
            request.session['total_amount'] = str(total_amount)  # Store original total for reference
            
            return redirect('orders:place-order')
    else:
        # For GET requests, or if there are errors, re-render the checkout page.
        user_addresses = UserAddress.objects.filter(user=request.user)
        total_amount = cart.get_total_price()
        # Recalculate taking any coupon into account:
        discount_amount = cart.get_discount_amount()
        shipping_charge = getattr(settings, "SHIPPING_CHARGE", Decimal('50.00'))
        total_after_discount = Decimal(cart.get_total_price_after_discount()) + Decimal(settings.SHIPPING_CHARGE)
        
        wallet_balance = Decimal('0.00')  # Initialize.
        if hasattr(request.user, 'wallet'):  # Check if wallet exists.
            wallet_balance = request.user.wallet.balance
        
        context = {
            'cart_items': cart_items,
            'total_amount': total_amount,
            'discount_amount': discount_amount,
            'total_after_discount': total_after_discount,
            'user_addresses': user_addresses,
            'wallet_balance': wallet_balance,  # Pass to template.
            'shipping_charge': shipping_charge,
        }
        return render(request, 'userside/cart/checkout.html', context)


@login_required
def add_address(request):
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            address.save()
            messages.success(request, 'Address added successfully.')
            return redirect('cart:checkout')
    else:
        form = AddressForm()
    return render(request, 'userside/cart/add_address.html', {'form': form})
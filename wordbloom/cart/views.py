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
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

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

    total_original_price = Decimal('0.00')
    total_discount = Decimal('0.00')
    
    # Calculate discount amount for each cart item
    for item in cart_items:
        item.discount_amount = round(float(item.variant.price) - float(item.variant.discounted_price), 2) if item.variant.discounted_price else 0
        total_original_price += Decimal(item.variant.price) * item.quantity
        total_discount += Decimal(item.discount_amount) * item.quantity

    # Check if coupon is still active
    if cart.coupon:
        # Check if coupon is active and not expired
        if not cart.coupon.status or cart.coupon.expiry_date < timezone.now().date():
            # Coupon is inactive or expired
            messages.warning(request, f"Coupon '{cart.coupon.coupon_code}' is no longer valid and has been removed from your cart.")
            cart.coupon = None
            cart.save()


    if request.method == 'POST':
        form = UpdateCartForm(request.POST)
        if form.is_valid():
            item_id = form.cleaned_data['item_id']
            quantity = form.cleaned_data['quantity']
            action = form.cleaned_data['action']

            # Add logging here
            logger.info("Cart form action '%s' for item %s, quantity %s", action, item_id, quantity)
            
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
        'total_original_price': total_original_price,
        'total_discount': total_discount,
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
def update_cart_quantity(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            item_id = data.get('item_id')
            quantity = int(data.get('quantity'))
            
            # Add logging here
            logger.info("Cart update requested for item %s, quantity %s", item_id, quantity)

            if quantity < 1:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Quantity must be at least 1'
                }, status=400)
            
            cart_item = CartItem.objects.get(id=item_id, cart__user=request.user)
            
            # Check stock availability
            if quantity > cart_item.variant.stock:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Only {cart_item.variant.stock} units available'
                }, status=400)
            
            # Update quantity
            cart_item.quantity = quantity
            cart_item.save()
            
            # Recalculate cart totals
            cart = Cart.objects.get(user=request.user)
            cart_items = CartItem.objects.filter(cart=cart, is_active=True)
            
            # Calculate totals
            total_original_price = Decimal('0.00')
            total_discount = Decimal('0.00')
            
            for item in cart_items:
                item_discount = Decimal(item.variant.price) - Decimal(item.variant.discounted_price) if item.variant.discounted_price else Decimal('0.00')
                total_original_price += Decimal(item.variant.price) * item.quantity
                total_discount += item_discount * item.quantity
            
            cart_total = cart.get_total_price()
            discount_amount = cart.get_discount_amount()
            shipping_charge = getattr(settings, "SHIPPING_CHARGE", Decimal('50.00'))
            # Convert shipping_charge to Decimal if it's not already
            if not isinstance(shipping_charge, Decimal):
                shipping_charge = Decimal(str(shipping_charge))
            total_after_discount = Decimal(cart.get_total_price_after_discount()) + shipping_charge
            
            return JsonResponse({
                'status': 'success',
                'item_subtotal': float(cart_item.sub_total()),
                'cart_total': float(cart_total),
                'discount_amount': float(discount_amount),
                'total_after_discount': float(total_after_discount),
                'total_original_price': float(total_original_price),
                'total_discount': float(total_discount)
            })
            
        except CartItem.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Item not found'
            }, status=404)
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid JSON'
            }, status=400)
        except Exception as e:
            # Use the logger that's already defined at the module level
            logger.error(f"Error updating cart quantity: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=405)

@login_required
def remove_item(request, item_id):
    try:
        # Add logging here
        logger.info("Remove item requested for item %s", item_id)

        # First try to get the cart item
        cart_item = CartItem.objects.get(id=item_id, cart__user=request.user)
        
        # Get the cart before deleting the item
        cart = Cart.objects.get(user=request.user)
        
        # Delete the item
        cart_item.delete()
        
        # Recalculate cart totals
        cart_items = CartItem.objects.filter(cart=cart, is_active=True)
        
        # Calculate totals
        total_original_price = Decimal('0.00')
        total_discount = Decimal('0.00')
        
        for item in cart_items:
            item_discount = Decimal(item.variant.price) - Decimal(item.variant.discounted_price) if item.variant.discounted_price else Decimal('0.00')
            total_original_price += Decimal(item.variant.price) * item.quantity
            total_discount += item_discount * item.quantity
        
        cart_total = cart.get_total_price()
        discount_amount = cart.get_discount_amount()
        shipping_charge = getattr(settings, "SHIPPING_CHARGE", Decimal('50.00'))
        # Convert shipping_charge to Decimal if it's not already
        if not isinstance(shipping_charge, Decimal):
            shipping_charge = Decimal(str(shipping_charge))
        total_after_discount = Decimal(cart.get_total_price_after_discount()) + shipping_charge
        
        return JsonResponse({
            'status': 'success',
            'cart_total': float(cart_total),
            'discount_amount': float(discount_amount),
            'total_after_discount': float(total_after_discount),
            'total_original_price': float(total_original_price),
            'total_discount': float(total_discount),
            'cart_empty': not cart_items.exists()
        })
    except CartItem.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Item not found'}, status=404)
    except Cart.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Cart not found'}, status=404)
    except Exception as e:
        # Use the logger that's already defined at the module level
        logger.error(f"Error removing cart item: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


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
        
        # Add logging here
        logger.info("Checkout initiated by user %s, address %s, payment method %s, use wallet: %s", 
               request.user.id, address_id, payment_method, use_wallet)

        # Check if address is selected
        if not address_id:
            messages.error(request, "Please select a shipping address.")
            # Continue to render the page instead of redirecting
        # Check if payment method is selected
        elif not payment_method:
            messages.error(request, "Please select a payment method.")
            # Continue to render the page instead of redirecting
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
            
            # Store data in session for place_order view
            request.session['selected_address_id'] = address_id
            request.session['payment_method'] = payment_method
            request.session['amount_to_pay'] = str(amount_to_pay)  # Convert to string for session
            request.session['wallet_used'] = str(wallet_used)
            request.session['total_amount'] = str(total_amount)  # Store original total for reference
            
            return redirect('orders:place-order')
    
    # For GET requests, or if there are errors, re-render the checkout page.
    user_addresses = UserAddress.objects.filter(user=request.user)

    # Calculate totals to match cart_view.html
    total_original_price = Decimal('0.00')
    total_discount = Decimal('0.00')
    
    # Calculate discount amount for each cart item - same as in cart_view
    for item in cart_items:
        item.discount_amount = round(float(item.variant.price) - float(item.variant.discounted_price), 2) if item.variant.discounted_price else 0
        item.sub_total = Decimal(item.variant.price) * item.quantity
        total_original_price += Decimal(item.variant.price) * item.quantity
        total_discount += Decimal(item.discount_amount) * item.quantity

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
        'total_original_price': total_original_price,  # Added for order summary
        'total_discount': total_discount,  # Added for order summary
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

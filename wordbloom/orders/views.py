from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.crypto import get_random_string
from .models import OrderMain, OrderItem, ReturnRequest
from cart.models import Cart, CartItem
from .forms import ReturnRequestForm
from django.core.paginator import Paginator
from userpanel.models import UserAddress, Wallet, WalletTransaction
from django.db import transaction
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
import razorpay
from django.conf import settings
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal
from django.conf import settings


# Create your views here.

@login_required
@transaction.atomic
def place_order(request):
    # Get checkout details from session
    address_id = request.session.get('selected_address_id')
    payment_method = request.session.get('payment_method')
    wallet_used = Decimal(request.session.get('wallet_used', '0.00'))
    amount_to_pay = Decimal(request.session.get('amount_to_pay', '0.00'))
    total_amount = Decimal(request.session.get('total_amount', '0.00'))
    
    if not address_id or not payment_method:
        messages.error(request, "Please select both address and payment method.")
        return redirect('cart:checkout')
    
    try:
        cart = Cart.objects.get(user=request.user)
        cart_items = CartItem.objects.filter(cart=cart, is_active=True)
        
        if not cart_items.exists():
            messages.error(request, "Your cart is empty.")
            return redirect('cart:cart-view')
        
        address = get_object_or_404(UserAddress, id=address_id, user=request.user)
        shipping_charge = Decimal(settings.SHIPPING_CHARGE)  # Get shipping charge from settings
        
        # Calculate totals
        cart_total = Decimal(cart.get_total_price_after_discount())
        total_with_shipping = cart_total + shipping_charge  # Include shipping charge
        discount_amount = cart.get_discount_amount()
        
        with transaction.atomic():
            # Create order
            order = OrderMain.objects.create(
                user=request.user,
                address=address,
                total_amount=total_with_shipping,  # Total *before* wallet deduction
                payment_method=payment_method,
                order_id=get_random_string(10).upper(),
                discount_amount=discount_amount,
            )
            
            # Process order items
            for cart_item in cart_items:
                variant = cart_item.variant
                if cart_item.quantity > variant.stock:
                    raise Exception(f"Not enough stock for {variant.product.product_name}")
                
                variant.stock -= cart_item.quantity
                variant.save()
                
                OrderItem.objects.create(
                    order=order,
                    product_variant=variant,
                    quantity=cart_item.quantity,
                    price=variant.discounted_price or variant.price
                )
            
            # --- Wallet Deduction ---
            if wallet_used > Decimal('0.00'):
                if not hasattr(request.user, 'wallet'):
                    # Create wallet if it doesn't exist
                    Wallet.objects.create(user=request.user, balance=Decimal('0.00'))
                
                wallet = request.user.wallet
                
                # Verify wallet has sufficient balance
                if wallet.balance < wallet_used:
                    raise Exception(f"Insufficient wallet balance. Available: ₹{wallet.balance}")
                
                # Deduct from wallet
                wallet.balance -= wallet_used
                wallet.save()
                
                # Create wallet transaction record
                WalletTransaction.objects.create(
                    wallet=wallet,
                    amount=wallet_used,
                    transaction_type='debit',
                    description=f"Used for order {order.order_id}"
                )
            
            # Clear cart
            cart_items.delete()
            if cart.coupon:
                cart.coupon = None
                cart.save()
            
            # Handle Razorpay payment if needed
            if payment_method == 'Razorpay' and amount_to_pay > Decimal('0.00'):
                try:
                    # Initialize Razorpay client with basic auth
                    key_id = settings.RAZORPAY_KEY_ID
                    key_secret = settings.RAZORPAY_KEY_SECRET
                    
                    print(f"Initializing Razorpay with key_id: {key_id[:5]}...")
                    client = razorpay.Client(
                        auth=(key_id, key_secret)
                    )
                    
                    # Prepare payment data - use amount_to_pay (after wallet deduction) 
                    amount_in_paise = int(float(amount_to_pay) * 100)
                    payment_data = {
                        'amount': amount_in_paise,
                        'currency': 'INR',
                        'receipt': str(order.order_id),
                        'notes': {
                            'order_id': str(order.order_id),
                            'customer_email': request.user.email
                        }
                    }
                    
                    print(f"Creating Razorpay order with data: {payment_data}")
                    # Create Razorpay order
                    razorpay_order = client.order.create(payment_data)
                    
                    if not razorpay_order.get('id'):
                        raise Exception("No order ID received from Razorpay")
                    
                    # Update order with Razorpay details
                    order.razorpay_order_id = razorpay_order['id']
                    order.order_status = 'Payment_Pending'
                    order.save()
                    
                    # Prepare checkout data
                    context = {
                        'order': order,
                        'order_id': order.order_id,
                        'razorpay_order_id': razorpay_order['id'],
                        'razorpay_merchant_key': key_id,
                        'razorpay_amount': amount_in_paise,
                        'currency': 'INR',
                        'callback_url': request.build_absolute_uri(reverse('orders:razorpay-callback')),
                        'user_name': request.user.full_name,
                        'user_email': request.user.email,
                        'user_contact': getattr(request.user, 'phone_number', '')
                    }
                    
                    # Clear the session data
                    for key in ['selected_address_id', 'payment_method', 'amount_to_pay', 'wallet_used', 'total_amount']:
                        if key in request.session:
                            del request.session[key]
                    
                    return render(request, 'userside/order/razorpay_payment.html', context)
                
                except Exception as e:
                    # Log the full error
                    import traceback
                    print(f"Razorpay Error: {str(e)}")
                    print("Full traceback:")
                    print(traceback.format_exc())
                    
                    # Clean up the order and restore wallet
                    if wallet_used > Decimal('0.00'):
                        wallet = request.user.wallet
                        wallet.balance += wallet_used
                        wallet.save()
                        
                        # Create refund transaction
                        WalletTransaction.objects.create(
                            wallet=wallet,
                            amount=wallet_used,
                            transaction_type='credit',
                            description=f"Refund due to failed payment for order {order.order_id}"
                        )
                    
                    order.delete()
                    messages.error(request, f"Payment initialization failed: {str(e)}")
                    return redirect('cart:checkout')
            
            # For COD or full wallet payment
            if payment_method == 'Wallet':
                order.payment_status = 'Success'
                order.order_status = 'Confirmed'
            else:
                order.payment_status = 'Pending'
                order.order_status = 'Confirmed'
            
            order.save()
            
            # Clear the session data
            for key in ['selected_address_id', 'payment_method', 'amount_to_pay', 'wallet_used', 'total_amount']:
                if key in request.session:
                    del request.session[key]
            
            messages.success(request, f"Order placed successfully. Your order ID is {order.order_id}")
            return redirect('orders:order-confirmation', order_id=order.order_id)
    
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('cart:checkout')

@csrf_exempt
def razorpay_callback(request):
    if request.method == "POST":
        payment_id = request.POST.get('razorpay_payment_id', '')
        razorpay_order_id = request.POST.get('razorpay_order_id', '')
        signature = request.POST.get('razorpay_signature', '')
        
        try:
            order = OrderMain.objects.get(razorpay_order_id=razorpay_order_id)
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            
            # Verify payment signature
            params_dict = {
                'razorpay_payment_id': payment_id,
                'razorpay_order_id': razorpay_order_id,
                'razorpay_signature': signature
            }
            
            try:
                client.utility.verify_payment_signature(params_dict)
                # Payment successful
                order.payment_id = payment_id
                order.payment_status = 'Success'
                order.order_status = 'Confirmed'
                order.save()
                # return JsonResponse({'status': 'success'})
                return redirect('orders:order-confirmation', order_id=order.order_id)
            except razorpay.errors.SignatureVerificationError:
                # Payment verification failed
                order.payment_status = 'Failed'
                order.save()
                return JsonResponse({'status': 'failed', 'error': 'Payment verification failed'})
                
        except OrderMain.DoesNotExist:
            return JsonResponse({'status': 'failed', 'error': 'Order not found'})
        except Exception as e:
            return JsonResponse({'status': 'failed', 'error': str(e)})
            
    return JsonResponse({'status': 'failed', 'error': 'Invalid request method'})



@login_required
def retry_payment(request, order_id):
    order = get_object_or_404(OrderMain, order_id=order_id, user=request.user)
    
    if order.payment_method != 'Razorpay' or order.payment_status == 'Success':
        messages.error(request, "Invalid retry request")
        return redirect('userpanel:order_list')
    
    try:
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        
        payment_data = {
            'amount': int(order.total_amount * 100),
            'currency': 'INR',
            'receipt': order.order_id,
        }
        
        razorpay_order = client.order.create(data=payment_data)
        order.razorpay_order_id = razorpay_order['id']
        order.payment_status = 'Pending'
        order.save()
        
        context = {
            'order_id': order.order_id,
            'razorpay_order_id': razorpay_order['id'],
            'razorpay_merchant_key': settings.RAZORPAY_KEY_ID,
            'razorpay_amount': payment_data['amount'],
            'currency': payment_data['currency'],
            'callback_url': request.build_absolute_uri(reverse('orders:razorpay-callback')),
        }
        return render(request, 'userside/order/razorpay_payment.html', context)
    except Exception as e:
        messages.error(request, f"Error initiating payment: {str(e)}")
        return redirect('userpanel:order_list')


# @login_required
# def order_confirmation(request, order_id):
#     try:
#         order = OrderMain.objects.get(order_id=order_id, user=request.user)
#     except OrderMain.DoesNotExist:
#         messages.error(request, "Order not found.")
#         return redirect('userpanel:order_list')

#     context = {
#         'order': order,
#     }
#     return render(request, 'userside/order/order_confirmation.html', context)

@login_required
def order_confirmation(request, order_id):
    try:
        order = OrderMain.objects.get(order_id=order_id, user=request.user)
    except OrderMain.DoesNotExist:
        messages.error(request, "Order not found.")
        return redirect('userpanel:order_list')
    
    # Get wallet information from session if available
    wallet_used = request.session.get('wallet_used', 0)
    amount_to_pay = request.session.get('amount_to_pay', order.total_amount)
    
    context = {
        'order': order,
        'wallet_used': wallet_used,
        'amount_to_pay': amount_to_pay,
    }
    
    # Clear the session data if not already cleared
    for key in ['selected_address_id', 'payment_method', 'amount_to_pay', 'wallet_used', 'total_amount']:
        if key in request.session:
            del request.session[key]
            
    return render(request, 'userside/order/order_confirmation.html', context)


@login_required
def order_failure(request, order_id):
    order = get_object_or_404(OrderMain, order_id=order_id, user=request.user)
    return render(request, 'userside/order/order_failure.html', {'order': order})


# @login_required
# def return_request(request, order_id):
#     order = get_object_or_404(OrderMain, order_id=order_id, user=request.user)
#     if request.method == 'POST':
#         form = ReturnRequestForm(request.POST)
#         if form.is_valid():
#             return_request = form.save(commit=False)
#             return_request.order = order
#             return_request.save()
#             order.order_status = 'Return_Initiated'
#             order.save()
#             messages.success(request, "Your return request has been submitted.")
#             return redirect('userpanel:order_list')
#     else:
#         form = ReturnRequestForm()
#     return render(request, 'userside/order/return_request.html', {'form': form, 'order': order})


@login_required
def return_request(request, order_id):
    order = get_object_or_404(OrderMain, order_id=order_id, user=request.user)
    item_id = request.GET.get('item_id')
    
    # Get the specific item if item_id is provided
    item = None
    if item_id:
        item = get_object_or_404(OrderItem, id=item_id, order=order)
        if item.is_returned:
            messages.error(request, "This item has already been returned or return has been initiated.")
            return redirect('userpanel:user_order_detail', order_id=order.order_id)
    
    if request.method == 'POST':
        form = ReturnRequestForm(request.POST)
        if form.is_valid():
            return_request = form.save(commit=False)
            return_request.order = order
            
            # If it's for a specific item
            if item:
                return_request.item = item
                item.is_returned = True
                item.save()
            else:
                # For full order return
                order.order_status = 'Return_Initiated'
                order.save()
                
            return_request.save()
            messages.success(request, "Your return request has been submitted.")
            return redirect('userpanel:user_order_detail', order_id=order.order_id)
    else:
        form = ReturnRequestForm()
    
    context = {
        'form': form, 
        'order': order,
        'item': item
    }
    return render(request, 'userside/order/return_request.html', {'form': form, 'order': order, 'item': item})


@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(OrderMain, order_id=order_id, user=request.user)
    if request.method == 'POST':
        with transaction.atomic():
            order.order_status = 'Cancelled'
            order.save()

            # Refund to wallet
            wallet, created = Wallet.objects.get_or_create(user=request.user)
            refund_amount = order.refund_amount()
            wallet.add_funds(refund_amount)

            messages.success(request, f"Order {order.order_id} cancelled successfully. Refund of ₹{refund_amount} added to your wallet.")
            return redirect('userpanel:order_list')

    return render(request, 'userside/order/confirm_cancel.html', {'order': order})

# @login_required
# def cancel_item(request, item_id):
#     item = get_object_or_404(OrderItem, id=item_id, order__user=request.user)
#     if request.method == 'POST':
#         with transaction.atomic():
#             item.is_cancelled = True
#             item.save()

#             # Refund to wallet
#             wallet, created = Wallet.objects.get_or_create(user=request.user)
#             refund_amount = item.get_cost()
#             wallet.add_funds(refund_amount)

#             messages.success(request, f"Item cancelled successfully. Refund of ₹{refund_amount} added to your wallet.")
#             return redirect('userpanel:user_order_detail', order_id=item.order.order_id)

#     return render(request, 'userside/order/confirm_cancel_item.html', {'item': item})

@login_required
def cancel_item(request, item_id):
    item = get_object_or_404(OrderItem, id=item_id, order__user=request.user)
    order = item.order
    
    # Check if item can be cancelled
    if order.order_status in ['Shipped', 'Delivered', 'Cancelled']:
        messages.error(request, "This item cannot be cancelled at this stage.")
        return redirect('userpanel:user_order_detail', order_id=order.order_id)
    
    if request.method == 'POST':
        with transaction.atomic():
            # Mark item as cancelled
            item.is_cancelled = True
            item.save()
            
            # Refund to wallet
            wallet, created = Wallet.objects.get_or_create(user=request.user)
            refund_amount = item.get_cost()
            wallet.balance += refund_amount
            wallet.save()
            
            # Create wallet transaction
            WalletTransaction.objects.create(
                wallet=wallet,
                amount=refund_amount,
                transaction_type='credit',
                description=f'Refund for cancelled item in order #{order.order_id}'
            )
            
            messages.success(request, f"Item cancelled successfully. Refund of ₹{refund_amount} added to your wallet.")
        return redirect('userpanel:user_order_detail', order_id=order.order_id)
    
    return render(request, 'userside/order/confirm_cancel_item.html', {'item': item})



@login_required
def admin_order_list(request):
    # Get search query
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', 'Show all')
    
    # Base queryset
    orders = OrderMain.objects.all().order_by('-created_at')
    
    # Apply filters
    if search_query:
        orders = orders.filter(
            Q(order_id__icontains=search_query) |
            Q(user__full_name__icontains=search_query)
        )
    
    if status_filter != 'Show all':
        orders = orders.filter(order_status=status_filter)
    
    # Pagination
    items_per_page = int(request.GET.get('items_per_page', 10))
    paginator = Paginator(orders, items_per_page)
    page = request.GET.get('page', 1)
    
    try:
        orders = paginator.page(page)
    except PageNotAnInteger:
        orders = paginator.page(1)
    except EmptyPage:
        orders = paginator.page(paginator.num_pages)
    
    context = {
        'orders': orders,
        'ORDER_STATUS_CHOICES': OrderMain.ORDER_STATUS_CHOICES,
        'search_query': search_query,
        'status_filter': status_filter,
        'items_per_page': str(items_per_page)
    }
    return render(request, 'adminside/order/order_list.html', context)


# @login_required
# def admin_order_detail(request, order_id):
#     order = get_object_or_404(OrderMain, id=order_id)
#     order_items = order.items.all()
    
#     # Calculate subtotal, discount, and grand total
#     subtotal = sum(item.total_cost for item in order_items)
#     discount_amount = 0  # You can implement discount logic here
#     grand_total = subtotal - discount_amount
    
#     context = {
#         'order': order,
#         'order_items': order_items,
#         'subtotal': subtotal,
#         'discount_amount': discount_amount,
#         'grand_total': grand_total
#     }
#     return render(request, 'adminside/order/order_details.html', context)

@login_required
def admin_order_detail(request, order_id):
    order = get_object_or_404(OrderMain, id=order_id)
    order_items = order.items.all()
    
    # Get all return requests for this order
    return_requests = ReturnRequest.objects.filter(order=order)
    
    # Calculate subtotal, discount, and grand total
    subtotal = sum(item.total_cost for item in order_items)
    discount_amount = order.discount_amount
    grand_total = subtotal - discount_amount
    
    context = {
        'order': order,
        'order_items': order_items,
        'return_requests': return_requests,
        'subtotal': subtotal,
        'discount_amount': discount_amount,
        'grand_total': grand_total
    }
    return render(request, 'adminside/order/order_details.html', context)

@login_required
def change_order_status(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(OrderMain, id=order_id)
        new_status = request.POST.get('order_status')
        order.order_status = new_status
        order.save()

        if new_status == 'Return_Approved':
            with transaction.atomic():
                wallet, created = Wallet.objects.get_or_create(user=order.user)
                refund_amount = order.refund_amount()
                wallet.balance += refund_amount
                wallet.save()

                WalletTransaction.objects.create(
                    wallet=wallet,
                    amount=refund_amount,
                    transaction_type='credit',
                    description=f'Refund for approved return of order #{order.order_id}'
                )

        messages.success(request, f"Order status updated to {new_status}")
        return redirect('orders:admin-order-detail', order_id=order_id)
    messages.error(request, "Invalid request")
    return redirect('orders:admin-order-list')

@login_required
def admin_return_orders(request):
    return_requests = ReturnRequest.objects.all().order_by('-created_at')
    paginator = Paginator(return_requests, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'adminside/order/return_order.html', {'page_obj': page_obj})

# @login_required
# def approve_return(request, order_id):
#     order = get_object_or_404(OrderMain, id=order_id)
#     if request.method == 'POST':
#         with transaction.atomic():
#             order.order_status = 'Return_Approved'
#             order.save()

#             # Refund to wallet
#             wallet, created = Wallet.objects.get_or_create(user=order.user)
#             refund_amount = order.refund_amount()
#             wallet.add_funds(refund_amount)

#             messages.success(request, f"Return approved for order {order.order_id}. Refund of ₹{refund_amount} added to the user's wallet.")
#     return redirect('orders:admin-order-detail', order_id=order.id)


@login_required
def approve_return(request, return_request_id):
    return_request = get_object_or_404(ReturnRequest, id=return_request_id)
    order = return_request.order
    
    if request.method == 'POST':
        with transaction.atomic():
            # If it's a specific item return
            if return_request.item:
                item = return_request.item
                refund_amount = item.get_cost()
                
                # Update return request status
                return_request.status = 'Approved'
                return_request.save()
            else:
                # Full order return
                order.order_status = 'Return_Approved'
                order.save()
                refund_amount = order.refund_amount()
            
            # Refund to wallet
            wallet, created = Wallet.objects.get_or_create(user=order.user)
            wallet.balance += refund_amount
            wallet.save()
            
            # Create wallet transaction
            WalletTransaction.objects.create(
                wallet=wallet,
                amount=refund_amount,
                transaction_type='credit',
                description=f'Refund for approved return of {return_request.item and "item" or "order"} #{order.order_id}'
            )
            
            messages.success(request, f"Return approved. Refund of ₹{refund_amount} added to the user's wallet.")
            
        return redirect('orders:admin-order-detail', order_id=order.id)


# @login_required
# def reject_return(request, order_id):
#     order = get_object_or_404(OrderMain, id=order_id)
#     if request.method == 'POST':
#         order.order_status = 'Return_Rejected'
#         order.save()
#         messages.success(request, f"Return rejected for order {order.order_id}.")
#     return redirect('orders:admin-order-detail', order_id=order.id)

@login_required
def reject_return(request, return_request_id):
    return_request = get_object_or_404(ReturnRequest, id=return_request_id)
    order = return_request.order
    
    if request.method == 'POST':
        # If it's a specific item return
        if return_request.item:
            item = return_request.item
            item.is_returned = False
            item.save()
            
            # Update return request status
            return_request.status = 'Rejected'
            return_request.save()
        else:
            # Full order return
            order.order_status = 'Return_Rejected'
            order.save()
        
        messages.success(request, f"Return rejected for {return_request.item and 'item' or 'order'} {order.order_id}.")
        return redirect('orders:admin-order-detail', order_id=order.id)
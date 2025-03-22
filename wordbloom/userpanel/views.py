from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from .forms import UserProfileForm, AddressForm, CustomPasswordChangeForm
from .models import UserAddress, Wishlist, Wallet
from orders.models import OrderMain,OrderItem
from products.models import Product, ProductVariant
from django.db import transaction
from .models import Wallet, WalletTransaction
from decimal import Decimal
from orders.models import OrderMain
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Image, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib import colors
import os
from io import BytesIO
from django.conf import settings


# Create your views here.
@login_required
def profile(request):
    return render(request, 'userside/userpanel/profile.html')

@login_required
def edit_profile(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated.')
            return redirect('userpanel:profile')
    else:
        form = UserProfileForm(instance=request.user)
    return render(request, 'userside/userpanel/edit_profile.html', {'form': form})

@login_required
def change_password(request):
    if request.method == 'POST':
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password was successfully updated!')
            return redirect('userpanel:profile')
    else:
        form = CustomPasswordChangeForm(request.user)
    return render(request, 'userside/userpanel/change_password.html', {'form': form})

@login_required
def manage_addresses(request):
    addresses = UserAddress.objects.filter(user=request.user)
    return render(request, 'userside/userpanel/manage_address.html', {'addresses': addresses})

@login_required
def add_address(request):
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            address.save()
            messages.success(request, 'Address added successfully.')
            return redirect('userpanel:manage_addresses')
    else:
        form = AddressForm()
    return render(request, 'userside/userpanel/add_address.html', {'form': form})

@login_required
def edit_address(request, address_id):
    address = get_object_or_404(UserAddress, id=address_id, user=request.user)
    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            messages.success(request, 'Address updated successfully.')
            return redirect('userpanel:manage_addresses')
    else:
        form = AddressForm(instance=address)
    return render(request, 'userside/userpanel/edit_address.html', {'form': form})

@login_required
def delete_address(request, address_id):
    address = get_object_or_404(UserAddress, id=address_id, user=request.user)
    address.delete()
    messages.success(request, 'Address deleted successfully.')
    return redirect('userpanel:manage_addresses')

@login_required
def order_list(request):
    orders = OrderMain.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'userside/userpanel/order_list.html', {'orders': orders})

# @login_required
# def cancel_order(request, order_id):
#     order = get_object_or_404(OrderMain, order_id=order_id, user=request.user)
    
#     # Only allow cancellation for Confirmed or Shipped status
#     if order.order_status not in ['Confirmed', 'Shipped']:
#         messages.error(request, "Only orders with Confirmed or Shipped status can be cancelled")
#         return redirect('userpanel:order_list')

#     if request.method == 'POST':
#         with transaction.atomic():
#             # First restore stock for all items in the order
#             for item in order.items.all():
#                 if not item.is_cancelled:  # Only restore stock for items that weren't already cancelled
#                     variant = item.product_variant
#                     variant.stock += item.quantity
#                     variant.save()
                    
#                     # Mark all items as cancelled
#                     item.is_cancelled = True
#                     item.save()
            
#             # Update order status to Cancelled
#             order.order_status = 'Cancelled'
#             order.save()
            
#             # Handle refund to wallet if payment was successful
#             if order.payment_status == 'Success':
#                 wallet, created = Wallet.objects.get_or_create(user=request.user)
                
#                 # Calculate refund amount based on shipping status
#                 if order.order_status == 'Shipped':
#                     # Deduct shipping charge from refund if order was already shipped
#                     shipping_charge = getattr(settings, "SHIPPING_CHARGE", Decimal('50.00'))
#                     refund_amount = order.total_amount - shipping_charge
#                 else:
#                     # Full refund for confirmed but not shipped orders
#                     refund_amount = order.total_amount
                
#                 # Add funds to wallet
#                 if refund_amount > 0:
#                     wallet.add_funds(refund_amount)
#                     # Create transaction record
#                     WalletTransaction.objects.create(
#                         wallet=wallet,
#                         amount=refund_amount,
#                         transaction_type='CREDIT',
#                         description=f"Refund for cancelled order #{order.order_id}"
#                     )
#                     messages.success(request, f"₹{refund_amount} has been refunded to your wallet.")
            
#             messages.success(request, f"Order {order_id} has been cancelled successfully")
            
#         return redirect('userpanel:order_list')
    
#     return render(request, 'userside/order/confirm_cancel.html', {'order': order})


@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(OrderMain, order_id=order_id, user=request.user)
    # Only allow cancellation for Confirmed or Shipped status
    if order.order_status not in ['Confirmed', 'Shipped']:
        messages.error(request, "Only orders with Confirmed or Shipped status can be cancelled")
        return redirect('userpanel:order_list')
        
    if request.method == 'POST':
        with transaction.atomic():
            # Track the total refund amount for this cancellation
            total_refund_amount = Decimal('0.00')
            
            # First restore stock for all items in the order that aren't already cancelled
            for item in order.items.all():
                if not item.is_cancelled and not item.is_returned:  # Only handle active items
                    variant = item.product_variant
                    variant.stock += item.quantity
                    variant.save()
                    
                    # Mark the item as cancelled
                    item.is_cancelled = True
                    
                    # Only calculate refund for items that haven't been refunded yet
                    if not item.is_refunded and order.payment_status == 'Success':
                        refund_amount = item.get_cost()
                        
                        # For shipped orders, deduct shipping charge proportionally from each item
                        if order.order_status == 'Shipped':
                            shipping_charge = getattr(settings, "SHIPPING_CHARGE", Decimal('50.00'))
                            # Calculate this item's proportion of the total order
                            active_order_total = sum(i.get_cost() for i in order.items.all() 
                                                   if not i.is_cancelled and not i.is_returned and i != item)
                            total_order_value = active_order_total + item.get_cost()
                            
                            if total_order_value > Decimal('0.00'):
                                item_proportion = item.get_cost() / total_order_value
                                shipping_deduction = shipping_charge * item_proportion
                                refund_amount = refund_amount - shipping_deduction
                        
                        # Track the refund
                        item.is_refunded = True
                        item.refunded_amount = refund_amount
                        total_refund_amount += refund_amount
                    
                    item.save()
                    
            # Update order status to Cancelled
            order.order_status = 'Cancelled'
            order.save()
            
            # Handle refund to wallet if payment was successful and we have an amount to refund
            if order.payment_status == 'Success' and total_refund_amount > 0:
                wallet, created = Wallet.objects.get_or_create(user=request.user)
                # Add funds to wallet
                wallet.add_funds(total_refund_amount)
                
                # Create transaction record
                WalletTransaction.objects.create(
                    wallet=wallet,
                    amount=total_refund_amount,
                    transaction_type='CREDIT',
                    description=f"Refund for cancelled order #{order.order_id}"
                )
                
                messages.success(request, f"₹{total_refund_amount} has been refunded to your wallet.")
            
            messages.success(request, f"Order {order_id} has been cancelled successfully")
            return redirect('userpanel:order_list')
            
    return render(request, 'userside/order/confirm_cancel.html', {'order': order})

# @login_required
# def user_order_detail(request, order_id):
#     order = get_object_or_404(OrderMain, order_id=order_id, user=request.user)
#     order_items = order.items.all()
    
#     # Calculate totals considering cancelled items
#     subtotal = Decimal('0.00')
#     total_discount = Decimal('0.00')
#     active_item_total = Decimal('0.00')
#     cancelled_item_total = Decimal('0.00')
    
#     for item in order_items:
#         original_price = item.product_variant.price
#         discounted_price = item.price
#         item_discount = (original_price - discounted_price) * item.quantity
#         item_total = original_price * item.quantity
        
#         # Add to appropriate totals based on cancellation status
#         if not item.is_cancelled:
#             active_item_total += item.get_cost()
#             subtotal += item_total
#             total_discount += item_discount
#         else:
#             cancelled_item_total += item.get_cost()
    
#     # Get shipping charge from settings
#     # Get shipping charge from settings and convert to Decimal if it's not already
#     shipping_charge = Decimal(str(getattr(settings, "SHIPPING_CHARGE", Decimal('50.00'))))
    
#     # Calculate coupon discount (if any)
#     coupon_discount = order.discount_amount
#     coupon_applied = coupon_discount > Decimal('0.00')
    
#     # Calculate grand total for active items
#     grand_total = active_item_total + shipping_charge - coupon_discount
    
#     context = {
#         'order': order,
#         'order_items': order_items,
#         'subtotal': subtotal,
#         'total_discount': total_discount,
#         'coupon_discount': coupon_discount,
#         'shipping_charge': shipping_charge,
#         'grand_total': grand_total,
#         'coupon_applied': coupon_applied,
#         'cancelled_item_total': cancelled_item_total,
#         'active_item_total': active_item_total,
#     }
    
#     return render(request, 'userside/userpanel/user_order_detail.html', context)


@login_required
def user_order_detail(request, order_id):
    order = get_object_or_404(OrderMain, order_id=order_id, user=request.user)
    order_items = order.items.all()
    
    # Calculate totals considering cancelled and returned items
    subtotal = Decimal('0.00')
    total_discount = Decimal('0.00')
    active_item_total = Decimal('0.00')
    cancelled_item_total = Decimal('0.00')
    returned_item_total = Decimal('0.00')
    total_refunded = Decimal('0.00')
    
    for item in order_items:
        original_price = item.product_variant.price
        discounted_price = item.price
        item_discount = (original_price - discounted_price) * item.quantity
        item_total = original_price * item.quantity
        
        # Add to appropriate totals based on item status
        if not item.is_cancelled and not item.is_returned:
            active_item_total += item.get_cost()
            subtotal += item_total
            total_discount += item_discount
        elif item.is_cancelled:
            cancelled_item_total += item.get_cost()
            # Track the actual refunded amount
            if item.is_refunded:
                total_refunded += item.refunded_amount
        elif item.is_returned:
            returned_item_total += item.get_cost()
            # Track the actual refunded amount
            if item.is_refunded:
                total_refunded += item.refunded_amount
    
    # Add returned and cancelled items to subtotal for correct original total
    subtotal += returned_item_total + cancelled_item_total
    
    # Get shipping charge from settings and convert to Decimal if it's not already
    shipping_charge = Decimal(str(getattr(settings, "SHIPPING_CHARGE", Decimal('50.00'))))
    
    # Calculate coupon discount (if any)
    coupon_discount = order.discount_amount
    coupon_applied = coupon_discount > Decimal('0.00')
    
    # Calculate grand total for active items only
    grand_total = active_item_total + shipping_charge - coupon_discount
    
    context = {
        'order': order,
        'order_items': order_items,
        'subtotal': subtotal,
        'total_discount': total_discount,
        'coupon_discount': coupon_discount,
        'shipping_charge': shipping_charge,
        'grand_total': grand_total,
        'coupon_applied': coupon_applied,
        'cancelled_item_total': cancelled_item_total,
        'returned_item_total': returned_item_total,
        'total_refunded': total_refunded,
        'active_item_total': active_item_total,
    }
    return render(request, 'userside/userpanel/user_order_detail.html', context)

# @login_required
# def cancel_item(request, item_id):
#     item = get_object_or_404(OrderItem, id=item_id, order__user=request.user)
#     order = item.order
    
#     # Only allow cancellation for Confirmed status (not Shipped)
#     if order.order_status != 'Confirmed':
#         messages.error(request, "Items can only be cancelled when the order is Confirmed")
#         return redirect('userpanel:user_order_detail', order_id=order.order_id)
    
#     if item.is_cancelled:
#         messages.error(request, "This item is already cancelled")
#         return redirect('userpanel:user_order_detail', order_id=order.order_id)
    
#     if request.method == 'POST':
#         with transaction.atomic():
#             # Restore stock
#             variant = item.product_variant
#             variant.stock += item.quantity
#             variant.save()
            
#             # Mark the item as cancelled instead of deleting
#             item.is_cancelled = True
#             item.save()
            
#             # Handle refund to wallet if payment was successful
#             if order.payment_status == 'Success':
#                 wallet, created = Wallet.objects.get_or_create(user=request.user)
#                 refund_amount = item.get_cost()
                
#                 if refund_amount > 0:
#                     wallet.add_funds(refund_amount)
#                     # Create transaction record
#                     WalletTransaction.objects.create(
#                         wallet=wallet,
#                         amount=refund_amount,
#                         transaction_type='CREDIT',
#                         description=f"Refund for cancelled item in order #{order.order_id}"
#                     )
#                     messages.success(request, f"₹{refund_amount} has been refunded to your wallet.")
            
#             # Check if all items in the order are now cancelled
#             all_cancelled = all(item.is_cancelled for item in order.items.all())
#             if all_cancelled:
#                 order.order_status = 'Cancelled'
#                 order.save()
#                 messages.success(request, "All items have been cancelled, so the order is now cancelled")
            
#             messages.success(request, "Item cancelled successfully")
            
#         return redirect('userpanel:user_order_detail', order_id=order.order_id)
    
#     return render(request, 'userside/order/confirm_cancel_item.html', {'item': item})


@login_required
def cancel_item(request, item_id):
    item = get_object_or_404(OrderItem, id=item_id, order__user=request.user)
    order = item.order
    
    # Only allow cancellation for Confirmed status (not Shipped)
    if order.order_status != 'Confirmed':
        messages.error(request, "Items can only be cancelled when the order is Confirmed")
        return redirect('userpanel:user_order_detail', order_id=order.order_id)
    
    if item.is_cancelled:
        messages.error(request, "This item is already cancelled")
        return redirect('userpanel:user_order_detail', order_id=order.order_id)
    
    if request.method == 'POST':
        with transaction.atomic():
            # Restore stock
            variant = item.product_variant
            variant.stock += item.quantity
            variant.save()
            
            # Mark the item as cancelled
            item.is_cancelled = True
            
            # Handle refund to wallet if payment was successful and item hasn't been refunded yet
            refund_amount = Decimal('0.00')
            if order.payment_status == 'Success' and not item.is_refunded:
                refund_amount = item.get_cost()
                item.is_refunded = True
                item.refunded_amount = refund_amount
                
                wallet, created = Wallet.objects.get_or_create(user=request.user)
                wallet.add_funds(refund_amount)
                
                # Create transaction record
                WalletTransaction.objects.create(
                    wallet=wallet,
                    amount=refund_amount,
                    transaction_type='CREDIT',
                    description=f"Refund for cancelled item in order #{order.order_id}"
                )
                
                messages.success(request, f"₹{refund_amount} has been refunded to your wallet.")
            
            item.save()
            
            # Check if all items in the order are now cancelled
            all_cancelled = all(item.is_cancelled for item in order.items.all())
            if all_cancelled:
                order.order_status = 'Cancelled'
                order.save()
                messages.success(request, "All items have been cancelled, so the order is now cancelled")
            
            messages.success(request, "Item cancelled successfully")
            return redirect('userpanel:user_order_detail', order_id=order.order_id)
    
    return render(request, 'userside/order/confirm_cancel_item.html', {'item': item})


@login_required
def wishlist(request):
    wishlist_items = Wishlist.objects.filter(user=request.user)
    return render(request, 'userside/userpanel/wishlist.html', {'wishlist_items': wishlist_items})

@login_required
def remove_from_wishlist(request):
    if request.method == 'POST':
        wishlist_id = request.POST.get('wishlist_id')
        wishlist_item = get_object_or_404(Wishlist, id=wishlist_id, user=request.user)
        wishlist_item.delete()
        messages.success(request, 'Item removed from wishlist.')
    return redirect('userpanel:wishlist')

@login_required
def add_to_wishlist(request, product_id):
    product = get_object_or_404(Product, product_id=product_id)
    variant_id = request.POST.get('variant_id')

    try:
        variant = None
        if variant_id:
            variant = ProductVariant.objects.get(id=variant_id)

        if variant:
            if Wishlist.objects.filter(user=request.user, product=product, variant=variant).exists():
                messages.error(request, 'This variant is already in your wishlist.')
            else:
                Wishlist.objects.create(user=request.user, product=product, variant=variant)
                messages.success(request, 'Variant added to wishlist successfully.')
        else:
            if Wishlist.objects.filter(user=request.user, product=product).exists():
                messages.error(request, 'This product is already in your wishlist.')
            else:
                Wishlist.objects.create(user=request.user, product=product, variant=None)
                messages.success(request, 'Product added to wishlist successfully.')

    except ProductVariant.DoesNotExist:
        messages.error(request, 'Invalid variant.')
    except Exception as e:
        messages.error(request, 'Error adding to wishlist.')

    # Redirect back to the previous page
    referer_url = request.META.get('HTTP_REFERER')
    if referer_url:
        return redirect(referer_url)
    else:
        return redirect('accounts:shop')


@login_required
def wallet_view(request):
    wallet, created = Wallet.objects.get_or_create(user=request.user)
    transactions = wallet.transactions.all().order_by('-timestamp')
    return render(request, 'userside/userpanel/wallet.html', {'wallet': wallet, 'transactions': transactions})


@login_required
def add_funds(request):
    if request.method == 'POST':
        amount = Decimal(request.POST.get('amount', 0))
        if amount > 0:
            wallet, created = Wallet.objects.get_or_create(user=request.user)
            wallet.add_funds(amount)
            messages.success(request, f'₹{amount} has been added to your wallet.')
        else:
            messages.error(request, 'Please enter a valid amount.')
    return redirect('userpanel:wallet')

@login_required
def refund_to_wallet(request, order_id):
    order = get_object_or_404(OrderMain, id=order_id, user=request.user)
    if order.order_status == 'Cancelled' and order.payment_status == 'Success':
        with transaction.atomic():
            wallet, created = Wallet.objects.get_or_create(user=request.user)
            refund_amount = order.refund_amount()
            wallet.add_funds(refund_amount)
            order.payment_status = 'Refunded'
            order.save()
            messages.success(request, f'Refund of ₹{refund_amount} has been added to your wallet.')
    else:
        messages.error(request, 'This order is not eligible for a refund.')
    return redirect('userpanel:wallet')

# @login_required
# def generate_invoice(request, order_id):
#     order = get_object_or_404(OrderMain, order_id=order_id, user=request.user)
#     response = HttpResponse(content_type='application/pdf')
#     response['Content-Disposition'] = f'attachment; filename="invoice_{order.order_id}.pdf"'
#     buffer = BytesIO()
#     doc = SimpleDocTemplate(buffer, pagesize=A4)
#     elements = []
    
#     # Logo
#     logo_path = os.path.join(settings.BASE_DIR, 'static', 'userside', 'assets', 'imgs', 'theme', 'icons', 'logo_wordbloom.png')
#     try:
#         logo = Image(logo_path, width=1*inch, height=1*inch)
#         logo.hAlign = 'CENTER'
#         elements.append(logo)
#     except Exception as e:
#         print(f"Error loading logo: {e}")  # Add proper logging in production
#         elements.append(Paragraph("Logo could not be loaded", getSampleStyleSheet()['Normal']))
    
#     # Invoice Title and Details
#     styles = getSampleStyleSheet()
#     title = Paragraph("Invoice", styles['h1'])
#     title.style.alignment = 1  # Center
#     elements.append(title)
#     elements.append(Spacer(1, 12))
    
#     order_details = [
#         f"Order ID: {order.order_id}",
#         f"Order Date: {order.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
#         f"Payment Method: {order.payment_method}",
#         f"Payment Status: {order.get_payment_status_display()}"
#     ]
    
#     for detail in order_details:
#         elements.append(Paragraph(detail, styles['Normal']))
    
#     elements.append(Spacer(1, 12))
#     elements.append(Paragraph("Shipping Address:", styles['h2']))
#     elements.append(Paragraph(f"{order.shipping_address.name}", styles['Normal']))
#     elements.append(Paragraph(f"{order.shipping_address.house_name}, {order.shipping_address.street_name}", styles['Normal']))
#     elements.append(Paragraph(f"{order.shipping_address.district}, {order.shipping_address.state}", styles['Normal']))
#     elements.append(Paragraph(f"{order.shipping_address.country} - {order.shipping_address.pin_number}", styles['Normal']))
#     elements.append(Paragraph(f"Phone: {order.shipping_address.phone_number}", styles['Normal']))
    
#     elements.append(Spacer(1, 24))
    
#     # Order Items Table with more details - now including cancellation status
#     data = [['Item', 'Variant', 'Quantity', 'Unit Price', 'Item Discount', 'Item Subtotal', 'Status']]
    
#     order_mrp_total = Decimal('0.00')
#     order_discount_total = Decimal('0.00')
#     total_cancelled_amount = Decimal('0.00')
    
#     for item in order.items.all():
#         # Calculate the original price (MRP) from the product variant
#         original_price = item.product_variant.price
#         discounted_price = item.price
        
#         # Calculate item discount
#         item_discount = (original_price - discounted_price) * item.quantity
        
#         # Only add active items to totals
#         if not item.is_cancelled:
#             order_discount_total += item_discount
#             order_mrp_total += original_price * item.quantity
#         else:
#             total_cancelled_amount += item.get_cost()
        
#         # Set status text
#         status = "Cancelled" if item.is_cancelled else "Active"
        
#         # Use wrapping for long product names
#         product_name = item.product_variant.product.product_name
#         data.append([
#             product_name,
#             item.product_variant.format,
#             item.quantity,
#             f"Rs.{original_price:.2f}",
#             f"Rs.{item_discount:.2f}",
#             f"Rs.{item.get_cost():.2f}",
#             status
#         ])
    
#     # Get shipping charge from settings
#     shipping_charge = Decimal(str(getattr(settings, "SHIPPING_CHARGE", Decimal('50.00'))))
    
#     # Calculate coupon discount (if any)
#     coupon_discount = order.discount_amount
    
#     # Determine if coupon was applied
#     coupon_applied = coupon_discount > Decimal('0.00')
    
#     # Calculate grand total (excluding cancelled items)
#     active_items_total = sum(item.get_cost() for item in order.items.all() if not item.is_cancelled)
#     grand_total = active_items_total + shipping_charge - coupon_discount
    
#     # Add empty row
#     data.append(['', '', '', '', '', '', ''])
    
#     # Add summary rows with labels directly in the first column
#     data.append(['Order MRP ', '', '', '', '', f"Rs.{order_mrp_total:.2f}", ''])
#     data.append(['Total Order Discount', '', '', '', '', f"- Rs.{order_discount_total:.2f}", ''])
    
#     if coupon_applied:
#         data.append(['Coupon Discount', '', '', '', '', f"- Rs.{coupon_discount:.2f}", ''])
    
#     data.append(['Shipping Charge', '', '', '', '', f"Rs.{shipping_charge:.2f}", ''])
    
#     if total_cancelled_amount > Decimal('0.00'):
#         data.append(['Total Cancelled Amount', '', '', '', '', f"Rs.{total_cancelled_amount:.2f}", ''])
#         data.append(['Refunded to Wallet', '', '', '', '', f"Rs.{total_cancelled_amount:.2f}", ''])
    
#     data.append(['Grand Total', '', '', '', '', f"Rs.{grand_total:.2f}", ''])
    
#     col_widths = [1.7*inch, 0.8*inch, 0.6*inch, 0.8*inch, 0.8*inch, 1*inch, 0.8*inch]
#     table = Table(data, colWidths=col_widths)
    
#     # Calculate the row index where summary rows start
#     summary_row_start = len(data) - (7 if total_cancelled_amount > Decimal('0.00') else 5)
#     if coupon_applied:
#         summary_row_start -= 1
    
#     table.setStyle(TableStyle([
#         ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
#         ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
#         ('ALIGN', (0, 0), (-1, 0), 'CENTER'),  # Headers are centered
#         ('ALIGN', (0, 1), (0, summary_row_start-2), 'LEFT'),  # Left align product names
#         ('ALIGN', (1, 1), (1, summary_row_start-2), 'CENTER'),  # Center align variants
#         ('ALIGN', (2, 1), (2, summary_row_start-2), 'CENTER'),  # Center align quantities
#         ('ALIGN', (3, 1), (5, summary_row_start-2), 'RIGHT'),  # Right align prices
#         ('ALIGN', (6, 1), (6, summary_row_start-2), 'CENTER'),  # Center align status
        
#         ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Vertically center all content
#         ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
#         ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
#         ('BACKGROUND', (0, 1), (-1, summary_row_start-2), colors.beige),
#         ('GRID', (0, 0), (-1, summary_row_start-2), 1, colors.black),  # Grid for products only
#         # Ensure proper word wrapping for product names
#         ('WORDWRAP', (0, 1), (0, summary_row_start-2), True),
#         # Enhanced styling for summary rows
#         # For the empty row
#         ('SPAN', (0, summary_row_start-1), (-1, summary_row_start-1)),
#         ('BACKGROUND', (0, summary_row_start-1), (-1, summary_row_start-1), colors.beige),
#         ('LINEABOVE', (0, summary_row_start), (-1, summary_row_start), 1, colors.black),
#         # For the summary rows
#         ('SPAN', (0, summary_row_start), (4, summary_row_start)),  # MRP Total
#         ('SPAN', (0, summary_row_start+1), (4, summary_row_start+1)),  # Item Discount
        
#         # Left-align the labels
#         ('ALIGN', (0, summary_row_start), (0, -1), 'LEFT'),
#         ('FONTNAME', (0, summary_row_start), (0, -1), 'Helvetica-Bold'),
#         ('LEFTPADDING', (0, summary_row_start), (0, -1), 20),  # Add padding to make labels stand out
#         # Right-align the amounts
#         ('ALIGN', (-2, 1), (-2, -1), 'RIGHT'),
#         ('RIGHTPADDING', (-2, 1), (-2, -1), 20),
#         # Highlight the grand total
#         ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
#         ('FONTNAME', (-2, -1), (-2, -1), 'Helvetica-Bold'),
#         ('LINEBELOW', (0, -1), (-1, -1), 1, colors.black),
#     ]))
    
#     # Add styling for additional rows
#     row_offset = 0
    
#     # Add coupon row styling if present
#     if coupon_applied:
#         table.setStyle(TableStyle([
#             ('SPAN', (0, summary_row_start+2), (4, summary_row_start+2)),  # Coupon Discount
#         ]))
#         row_offset += 1
    
#     # Add styling for shipping charge row
#     table.setStyle(TableStyle([
#         ('SPAN', (0, summary_row_start+2+row_offset), (4, summary_row_start+2+row_offset)),  # Shipping Charge
#     ]))
    
#     # Add styling for cancelled/refunded rows if present
#     if total_cancelled_amount > Decimal('0.00'):
#         table.setStyle(TableStyle([
#             ('SPAN', (0, summary_row_start+3+row_offset), (4, summary_row_start+3+row_offset)),  # Total Cancelled
#             ('SPAN', (0, summary_row_start+4+row_offset), (4, summary_row_start+4+row_offset)),  # Refunded to Wallet
#             ('BACKGROUND', (0, summary_row_start+3+row_offset), (-1, summary_row_start+4+row_offset), colors.lavender),
#         ]))
    
#     elements.append(table)
    
#     # Add footer
#     elements.append(Spacer(1, 24))
#     elements.append(Paragraph("Thank you for shopping with WordBloom!", styles['Normal']))
    
#     doc.build(elements)
#     pdf = buffer.getvalue()
#     buffer.close()
#     response.write(pdf)
#     return response

@login_required
def generate_invoice(request, order_id):
    order = get_object_or_404(OrderMain, order_id=order_id, user=request.user)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_{order.order_id}.pdf"'
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    
    # Logo
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'userside', 'assets', 'imgs', 'theme', 'icons', 'logo_wordbloom.png')
    try:
        logo = Image(logo_path, width=1*inch, height=1*inch)
        logo.hAlign = 'CENTER'
        elements.append(logo)
    except Exception as e:
        print(f"Error loading logo: {e}") # Add proper logging in production
        elements.append(Paragraph("Logo could not be loaded", getSampleStyleSheet()['Normal']))
        
    # Invoice Title and Details
    styles = getSampleStyleSheet()
    title = Paragraph("Invoice", styles['h1'])
    title.style.alignment = 1 # Center
    elements.append(title)
    elements.append(Spacer(1, 12))
    
    order_details = [
        f"Order ID: {order.order_id}",
        f"Order Date: {order.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Payment Method: {order.payment_method}",
        f"Payment Status: {order.get_payment_status_display()}"
    ]
    
    for detail in order_details:
        elements.append(Paragraph(detail, styles['Normal']))
    
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("Shipping Address:", styles['h2']))
    elements.append(Paragraph(f"{order.shipping_address.name}", styles['Normal']))
    elements.append(Paragraph(f"{order.shipping_address.house_name}, {order.shipping_address.street_name}", styles['Normal']))
    elements.append(Paragraph(f"{order.shipping_address.district}, {order.shipping_address.state}", styles['Normal']))
    elements.append(Paragraph(f"{order.shipping_address.country} - {order.shipping_address.pin_number}", styles['Normal']))
    elements.append(Paragraph(f"Phone: {order.shipping_address.phone_number}", styles['Normal']))
    elements.append(Spacer(1, 24))
    
    # Order Items Table with more details - now including cancellation and return status
    data = [['Item', 'Variant', 'Quantity', 'Unit Price', 'Item Discount', 'Item Subtotal', 'Status']]
    
    order_mrp_total = Decimal('0.00')
    order_discount_total = Decimal('0.00')
    total_cancelled_amount = Decimal('0.00')
    total_returned_amount = Decimal('0.00')
    total_refunded_amount = Decimal('0.00')
    
    for item in order.items.all():
        # Make sure product_variant exists before trying to access its properties
        if item.product_variant:
            # Use explicit variable assignment for each property to ensure they're captured
            product_name = item.product_variant.product.product_name
            variant_format = item.product_variant.format
            original_price = item.product_variant.price
            discounted_price = item.price
            
            # Calculate item discount
            item_discount = (original_price - discounted_price) * item.quantity
            
            # Track refunds
            if item.is_refunded:
                total_refunded_amount += item.refunded_amount
                
            # Only add active items to totals
            if not item.is_cancelled and not item.is_returned:
                order_discount_total += item_discount
                order_mrp_total += original_price * item.quantity
            elif item.is_cancelled:
                total_cancelled_amount += item.get_cost()
            elif item.is_returned:
                total_returned_amount += item.get_cost()
                
            # Set status text
            if item.is_cancelled:
                status = "Cancelled"
                if item.is_refunded:
                    status += f" (Refunded: ₹{item.refunded_amount})"
            elif item.is_returned:
                status = "Returned"
                if item.is_refunded:
                    status += f" (Refunded: ₹{item.refunded_amount})"
            else:
                status = "Active"
                
            # Add item to the data list with explicit properties
            data.append([
                product_name,
                variant_format,
                item.quantity,
                f"Rs.{original_price:.2f}",
                f"Rs.{item_discount:.2f}",
                f"Rs.{item.get_cost():.2f}",
                status
            ])

    # Get shipping charge from settings
    shipping_charge = Decimal(str(getattr(settings, "SHIPPING_CHARGE", Decimal('50.00'))))
    
    # Calculate coupon discount (if any)
    coupon_discount = order.discount_amount
    
    # Determine if coupon was applied
    coupon_applied = coupon_discount > Decimal('0.00')
    
    # Calculate grand total (excluding cancelled and returned items)
    active_items_total = sum(item.get_cost() for item in order.items.all() 
                            if not item.is_cancelled and not item.is_returned)
    grand_total = active_items_total + shipping_charge - coupon_discount
    
    # Add empty row
    data.append(['', '', '', '', '', '', ''])
    
    # Add summary rows with labels directly in the first column
    data.append(['Order MRP ', '', '', '', '', f"Rs.{order_mrp_total:.2f}", ''])
    data.append(['Total Order Discount', '', '', '', '', f"- Rs.{order_discount_total:.2f}", ''])
    
    if coupon_applied:
        data.append(['Coupon Discount', '', '', '', '', f"- Rs.{coupon_discount:.2f}", ''])
        
    data.append(['Shipping Charge', '', '', '', '', f"Rs.{shipping_charge:.2f}", ''])
    
    if total_cancelled_amount > Decimal('0.00'):
        data.append(['Total Cancelled Amount', '', '', '', '', f"Rs.{total_cancelled_amount:.2f}", ''])
        
    if total_returned_amount > Decimal('0.00'):
        data.append(['Total Returned Amount', '', '', '', '', f"Rs.{total_returned_amount:.2f}", ''])
        
    if total_refunded_amount > Decimal('0.00'):
        data.append(['Total Refunded to Wallet', '', '', '', '', f"Rs.{total_refunded_amount:.2f}", ''])
    
    data.append(['Grand Total', '', '', '', '', f"Rs.{grand_total:.2f}", ''])
    
    # Set column widths to ensure all content fits
    col_widths = [1.7*inch, 0.8*inch, 0.6*inch, 0.8*inch, 0.8*inch, 1*inch, 1.2*inch]  # Increased width for status column
    
    table = Table(data, colWidths=col_widths)
    
    # Calculate the row index where summary rows start
    summary_row_start = len([item for item in order.items.all() if item.product_variant]) + 2  # Add 2 for header row and empty row
    
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'), # Headers are centered
        ('ALIGN', (0, 1), (0, summary_row_start-1), 'LEFT'), # Left align product names
        ('ALIGN', (1, 1), (1, summary_row_start-1), 'CENTER'), # Center align variants
        ('ALIGN', (2, 1), (2, summary_row_start-1), 'CENTER'), # Center align quantities
        ('ALIGN', (3, 1), (5, summary_row_start-1), 'RIGHT'), # Right align prices
        ('ALIGN', (6, 1), (6, summary_row_start-1), 'LEFT'), # Left align status
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), # Vertically center all content
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, summary_row_start-1), colors.beige),
        ('GRID', (0, 0), (-1, summary_row_start-1), 1, colors.black), # Grid for products only
        # Ensure proper word wrapping for product names and status
        ('WORDWRAP', (0, 1), (0, summary_row_start-1), True),
        ('WORDWRAP', (6, 1), (6, summary_row_start-1), True),
    ]))
    
    # Add styling for the summary section
    for i, row in enumerate(data[summary_row_start:], start=summary_row_start):
        if 'Grand Total' in row[0]:
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, i), (-1, i), colors.lightgrey),
                ('FONTNAME', (0, i), (0, i), 'Helvetica-Bold'),
                ('FONTNAME', (-2, i), (-2, i), 'Helvetica-Bold'),
                ('SPAN', (0, i), (4, i)),
            ]))
        else:
            table.setStyle(TableStyle([
                ('SPAN', (0, i), (4, i)),
                ('ALIGN', (0, i), (0, i), 'LEFT'),
                ('ALIGN', (-2, i), (-2, i), 'RIGHT'),
            ]))
    
    elements.append(table)
    
    # Add footer
    elements.append(Spacer(1, 24))
    elements.append(Paragraph("Thank you for shopping with WordBloom!", styles['Normal']))
    
    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    
    return response

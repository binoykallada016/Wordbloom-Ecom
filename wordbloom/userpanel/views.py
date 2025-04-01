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
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Image, Spacer
from reportlab.platypus.flowables import HRFlowable
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
                        refund_amount = item.total
                        
                        # For shipped orders, deduct shipping charge proportionally from each item
                        if order.order_status == 'Shipped':
                            shipping_charge = getattr(settings, "SHIPPING_CHARGE", Decimal('50.00'))
                            # Calculate this item's proportion of the total order
                            active_order_total = sum(
                                i.total for i in order.items.all() 
                                if not i.is_cancelled and not i.is_returned and i != item
                            )
                            total_order_value = active_order_total + item.total
                            
                            if total_order_value > Decimal('0.00'):
                                item_proportion = item.total / total_order_value
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
        variant = item.product_variant
        
        # Use get_effective_price() to determine the most beneficial price
        effective_price = Decimal(str(variant.get_effective_price()))
        original_price = Decimal(str(variant.price))
        
        # Calculate item-level discount
        item_discount = original_price - effective_price
        item_total = original_price * item.quantity
        
        # Store discount information directly on the item for template use
        item.original_price = original_price
        item.effective_price = effective_price
        item.item_discount = item_discount * item.quantity

        
        # Add to appropriate totals based on item status
        if not item.is_cancelled and not item.is_returned:
            active_item_total += (effective_price * item.quantity)
            subtotal += item_total
            total_discount += (item_discount * item.quantity)
        elif item.is_cancelled:
            cancelled_item_total += item.total
            if item.is_refunded:
                total_refunded += item.refunded_amount
        elif item.is_returned:
            returned_item_total += item.total
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
                refund_amount = item.total
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


@login_required
def generate_invoice(request, order_id):
    order = get_object_or_404(OrderMain, order_id=order_id, user=request.user)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_{order.order_id}.pdf"'
    buffer = BytesIO()
    
    # Use portrait A4 with standardized page margins
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4,
        rightMargin=52,
        leftMargin=52,
        topMargin=52,
        bottomMargin=52
    )
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Define custom teal color to replace darkblue
    teal_color = colors.HexColor('#2b5f5f')
    
    # Add custom styles
    styles.add(ParagraphStyle(
        name='Header',
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=teal_color,  # Changed from darkblue to teal
        spaceAfter=6
    ))
    
    styles.add(ParagraphStyle(
        name='TableHeader',
        fontName='Helvetica-Bold',
        fontSize=9,
        alignment=1  # Center align
    ))
    
    styles.add(ParagraphStyle(
        name='Footer',
        fontName='Helvetica',
        fontSize=10,
        alignment=1,  # Center align
        textColor=teal_color  # Changed from darkblue to teal
    ))
    
    # Create header table for logo and company name
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'userside', 'assets', 'imgs', 'theme', 'icons', 'logo_wordbloom.png')
    try:
        logo = Image(logo_path, width=0.8*inch, height=0.8*inch)
        company_name = Paragraph("<b>WordBloom</b>", styles['Header'])
        company_tagline = Paragraph("Your Destination for Books", styles['Normal'])
        
        header_data = [[logo, [company_name, company_tagline]]]
        header_table = Table(header_data, colWidths=[1*inch, 4*inch])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('ALIGN', (1, 0), (1, 0), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        elements.append(header_table)
    except Exception as e:
        print(f"Error loading logo: {e}")  # Add proper logging in production
        elements.append(Paragraph("WordBloom", styles['Header']))
    
    # Add a horizontal line - changed color to teal
    elements.append(HRFlowable(width="100%", thickness=1, color=teal_color, spaceBefore=10, spaceAfter=10))
    
    # Invoice Title and Reference Section
    title = Paragraph("<b>INVOICE</b>", styles['h1'])
    title.style.alignment = 1  # Center
    elements.append(title)
    elements.append(Spacer(1, 12))
    
    # Create order details table with improved alignment
    order_details_data = [
        ['Order ID', ':', order.order_id],
        ['Order Date', ':', order.created_at.strftime('%Y-%m-%d %H:%M:%S')],
        ['Payment Method', ':', order.payment_method],
        ['Payment Status', ':', order.get_payment_status_display()]
    ]

    # Improved alignment for order details table
    order_details_table = Table(order_details_data, colWidths=[3*inch, 0.3*inch, 3.5*inch])
    order_details_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),     # Left align labels
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),   # Center align colons
        ('ALIGN', (2, 0), (2, -1), 'LEFT'),     # Left align values
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(order_details_table)
    elements.append(Spacer(1, 12))
    
    # Shipping Address Section
    elements.append(Paragraph("<b>Shipping Address:</b>", styles['Header']))
    
    address_parts = [
        order.shipping_address.name,
        f"{order.shipping_address.house_name}, {order.shipping_address.street_name}",
        f"{order.shipping_address.district}, {order.shipping_address.state}",
        f"{order.shipping_address.country} - {order.shipping_address.pin_number}",
        f"Phone: {order.shipping_address.phone_number}"
    ]
    
    # Create a table for address to improve alignment
    address_data = [[part] for part in address_parts]
    address_table = Table(address_data, colWidths=[6.8*inch])
    address_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('VALIGN', (0, 0), (0, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (0, -1), 3),
    ]))
    elements.append(address_table)
    elements.append(Spacer(1, 24))
    
    # Order Items Table with improved styling
    table_headers = ['Item', 'Variant', 'Qty', 'Unit Price', 'Item Discount', 'Item Subtotal', 'Status']
    data = [table_headers]
    
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
                
            # Set status text - limit width by using appropriate wording
            if item.is_cancelled:
                if item.is_refunded:
                    status = f"Cancelled\nRefunded: Rs.{item.refunded_amount}"
                else:
                    status = "Cancelled"
            elif item.is_returned:
                if item.is_refunded:
                    status = f"Returned\nRefunded: Rs.{item.refunded_amount}"
                else:
                    status = "Returned"
            else:
                status = "Active"
                
            # Add item to the data list with explicit properties
            data.append([
                product_name,
                variant_format,
                str(item.quantity),
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
    
    # Create a lighter teal color for alternating rows
    light_teal = colors.Color(0.92, 0.96, 0.96)  # Light teal instead of beige
    
    # Set column widths to ensure all content fits - adjusted to prevent overflow
    # Note: Total width must be less than the available width on page (A4 width - margins)
    col_widths = [1.5*inch, 0.8*inch, 0.4*inch, 0.75*inch, 0.95*inch, 1*inch, 1.6*inch]
    
    # Set up the items table
    table = Table(data, colWidths=col_widths, repeatRows=1)
    
    # Calculate the row index where summary rows start
    summary_row_start = len([item for item in order.items.all() if item.product_variant]) + 1  # Add 1 for header row
    
    # Style the table - improved colors and layout
    table_style = [
        # Header styling - changed to teal
        ('BACKGROUND', (0, 0), (-1, 0), teal_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        
        # Item rows styling
        ('ALIGN', (0, 1), (0, summary_row_start), 'LEFT'),  # Left align product names
        ('ALIGN', (1, 1), (1, summary_row_start), 'CENTER'),  # Center align variants
        ('ALIGN', (2, 1), (2, summary_row_start), 'CENTER'),  # Center align quantities
        ('ALIGN', (3, 1), (5, summary_row_start), 'RIGHT'),  # Right align prices
        ('ALIGN', (6, 1), (6, summary_row_start), 'LEFT'),  # Left align status
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        
        # Grid and alternate row styling
        ('GRID', (0, 0), (-1, summary_row_start), 0.5, colors.grey),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.black),
        
        # Word wrapping for text fields
        ('WORDWRAP', (0, 1), (0, summary_row_start), True),
        ('WORDWRAP', (6, 1), (6, summary_row_start), True),
    ]
    
    # Add alternating row colors with light teal
    for i in range(1, summary_row_start + 1):
        if i % 2 == 0:
            table_style.append(('BACKGROUND', (0, i), (-1, i), light_teal))
    
    table.setStyle(TableStyle(table_style))
    elements.append(table)
    elements.append(Spacer(1, 12))
    
    # Summary table with proper styling
    summary_data = []
    
    # Add summary rows
    summary_data.append(['Order MRP', f"Rs.{order_mrp_total:.2f}"])
    summary_data.append(['Total Order Discount', f"- Rs.{order_discount_total:.2f}"])
    
    if coupon_applied:
        summary_data.append(['Coupon Discount', f"- Rs.{coupon_discount:.2f}"])
        
    summary_data.append(['Shipping Charge', f"Rs.{shipping_charge:.2f}"])
    
    if total_cancelled_amount > Decimal('0.00'):
        summary_data.append(['Total Cancelled Amount', f"Rs.{total_cancelled_amount:.2f}"])
        
    if total_returned_amount > Decimal('0.00'):
        summary_data.append(['Total Returned Amount', f"Rs.{total_returned_amount:.2f}"])
        
    if total_refunded_amount > Decimal('0.00'):
        summary_data.append(['Total Refunded to Wallet', f"Rs.{total_refunded_amount:.2f}"])
    
    # Add grand total row
    summary_data.append(['Grand Total', f"Rs.{grand_total:.2f}"])
    
    # Create the summary table with proper widths
    summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
    
    summary_table_style = [
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),  # Right-align labels for better alignment
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('LINEBELOW', (0, -2), (1, -2), 1, colors.grey),  # Line above grand total
        ('TOPPADDING', (0, -1), (1, -1), 6),  # Space above grand total
        ('BOTTOMPADDING', (0, -1), (1, -1), 6),  # Space below grand total
        ('BACKGROUND', (0, -1), (1, -1), light_teal),  # Highlight grand total row with light teal
        ('FONTNAME', (0, -1), (1, -1), 'Helvetica-Bold'),  # Bold font for grand total
    ]
    
    summary_table.setStyle(TableStyle(summary_table_style))
    
    # Create a table to right-align the summary table
    alignment_table = Table([[None, summary_table]], colWidths=[2*inch, 5*inch])
    alignment_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (1, 0), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    
    elements.append(alignment_table)
    
    # Add a horizontal line - changed to teal
    elements.append(Spacer(1, 24))
    elements.append(HRFlowable(width="100%", thickness=1, color=teal_color, spaceBefore=10, spaceAfter=10))
    
    # Add footer
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("Thank you for shopping with WordBloom!", styles['Footer']))
    elements.append(Paragraph("If you have any questions about your order, please contact our customer service.", styles['Footer']))
    
    # Build the PDF document
    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    
    return response

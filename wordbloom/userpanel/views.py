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
from reportlab.lib.pagesizes import letter
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

@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(OrderMain, order_id=order_id, user=request.user)
    if order.order_status == 'Delivered':
        messages.error(request, "Delivered orders cannot be cancelled")
        return redirect('userpanel:order_list')

    if request.method == 'POST':
        with transaction.atomic():
            # First restore stock for all items in the order
            for item in order.items.all():
                if not item.is_cancelled:  # Only restore stock for items that weren't already cancelled
                    variant = item.product_variant
                    variant.stock += item.quantity
                    variant.save()
            
            # Then delete the order
            order.delete()
                
            messages.success(request, f"Order {order_id} cancelled and deleted successfully")
            return redirect('userpanel:order_list')
    
    return render(request, 'userside/order/confirm_cancel.html', {'order': order})

@login_required
def user_order_detail(request, order_id):
    order = get_object_or_404(OrderMain, order_id=order_id, user=request.user)
    order_items = order.items.all()
    context = {
        'order': order,
        'order_items': order_items
    }
    return render(request, 'userside/userpanel/user_order_detail.html', context)

@login_required
def cancel_item(request, item_id):
    item = get_object_or_404(OrderItem, id=item_id, order__user=request.user)
    if item.order.order_status == 'Delivered':
        messages.error(request, "Delivered items cannot be cancelled")
        return redirect('userpanel:user_order_detail', order_id=item.order.order_id)

    if request.method == 'POST':
        with transaction.atomic():
            # Restore stock
            variant = item.product_variant
            variant.stock += item.quantity
            variant.save()
            
            # Get order_id before deleting the item
            order_id = item.order.order_id
            
            # Delete the item
            item.delete()
            
            # Check if this was the last item in the order
            remaining_items = OrderItem.objects.filter(order__order_id=order_id).count()
            if remaining_items == 0:
                # If no items left, delete the entire order
                OrderMain.objects.filter(order_id=order_id).delete()
                messages.success(request, "Order cancelled as all items were cancelled")
                return redirect('userpanel:order_list')
            
            messages.success(request, "Item cancelled and deleted successfully")
            return redirect('userpanel:user_order_detail', order_id=order_id)
    
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
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []

    # Logo (similar to sales report)
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'userside', 'assets', 'imgs', 'theme', 'icons', 'logo_wordbloom.png')
    try:
        logo = Image(logo_path, width=1.5*inch, height=0.75*inch)
        logo.hAlign = 'LEFT'
        elements.append(logo)
    except Exception as e:
        print(f"Error loading logo: {e}")  # Add proper logging in production
        elements.append(Paragraph("Logo could not be loaded", getSampleStyleSheet()['Normal']))


    # Invoice Title and Details
    styles = getSampleStyleSheet()
    title = Paragraph("Invoice", styles['h1'])
    title.style.alignment = 1  # Center
    elements.append(title)
    elements.append(Spacer(1, 12))

    order_details = [
        f"Order ID: {order.order_id}",
        f"Order Date: {order.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Payment Method: {order.payment_method}",
        f"Payment Status: {order.get_payment_status_display()}"  # Use get_FOO_display()
    ]
    for detail in order_details:
        elements.append(Paragraph(detail, styles['Normal']))
    elements.append(Spacer(1, 12))

    # # Billing and Shipping Address (Simplified for brevity)
    # elements.append(Paragraph("Billing Address:", styles['h2']))
    # elements.append(Paragraph(f"{request.user.full_name}", styles['Normal'])) #Using get full name method
    # elements.append(Paragraph(f"{request.user.email}", styles['Normal']))
    # elements.append(Paragraph(f"{order.address.name}", styles['Normal']))
    # elements.append(Paragraph(f"{order.address.house_name}, {order.address.street_name}", styles['Normal']))
    # elements.append(Paragraph(f"{order.address.district}, {order.address.state}", styles['Normal']))
    # elements.append(Paragraph(f"{order.address.country} - {order.address.pin_number}", styles['Normal']))
    # elements.append(Paragraph(f"Phone: {order.address.phone_number}", styles['Normal']))

    elements.append(Spacer(1, 12))
    elements.append(Paragraph("Shipping Address:", styles['h2']))
    # elements.append(Paragraph(f"{request.user.full_name}", styles['Normal']))
    # elements.append(Paragraph(f"{request.user.email}", styles['Normal']))
    elements.append(Paragraph(f"{order.address.name}", styles['Normal']))
    elements.append(Paragraph(f"{order.address.house_name}, {order.address.street_name}", styles['Normal']))
    elements.append(Paragraph(f"{order.address.district}, {order.address.state}", styles['Normal']))
    elements.append(Paragraph(f"{order.address.country} - {order.address.pin_number}", styles['Normal']))
    elements.append(Paragraph(f"Phone: {order.address.phone_number}", styles['Normal']))
    elements.append(Spacer(1, 24))

    # Order Items Table
    data = [['Item', 'Variant', 'Quantity', 'Unit Price', 'Total']]
    for item in order.items.all():
        data.append([
            item.product_variant.product.product_name,
            item.product_variant.format,
            item.quantity,
            f"Rs.{item.price:.2f}",
            f"Rs.{item.get_cost():.2f}",
        ])

    # Add Total, Discount, and Grand Total
    data.append(['', '', '', 'Subtotal', f"Rs.{order.total_amount:.2f}"])
    data.append(['', '', '', 'Discount', f"-Rs.{order.discount_amount:.2f}"])  # Include discount
    data.append(['', '', '', 'Grand Total', f"Rs.{(order.total_amount - order.discount_amount):.2f}"])  # Correct total


    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(table)

    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    return response

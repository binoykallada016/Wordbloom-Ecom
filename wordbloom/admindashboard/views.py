from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.decorators.cache import never_cache, cache_control
from utils.decorators import admin_required
from django.contrib.auth.decorators import login_required
from accounts.models import User
from category.models import Category
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Value, CharField, Sum
from django.db.models.functions import Concat, ExtractYear, ExtractMonth, ExtractDay
from django.urls import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import csv
import os
from io import BytesIO, StringIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image, Spacer, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from django.conf import settings
from django.db.models import Count, F
from orders.models import OrderMain, OrderItem
from userpanel.models import WalletTransaction  # Ensure these are correct models
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

ITEMS_PER_PAGE = 10

@never_cache
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def admin_login(request):
    # Redirect authenticated staff users to the dashboard
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('admindashboard:admin_dashboard')
    

    if request.method == 'POST':
        # Get email and password from POST data
        email = request.POST.get('email')
        password = request.POST.get('password')

        # Debugging: Print the values to verify
        print(f'Email : {email}, Password:{password}')

        # Authenticate user
        user = authenticate(request, username = email, password=password)
        print(f'Authenticated User: {user}')

        if user is not None:
            if user.is_staff: # To allow only the staff users to acces the admin page
                # print("hello")
                login(request, user)
                messages.success(request, f"Hello Admin, {user.first_name}!")
                return redirect('admindashboard:admin_dashboard')
            else:
                # Non-staff user trying to access admin login
                messages.error(request, 'You are not authorized to access this page.')
                return redirect('admindashboard:admin_login')
        else:
            # Invalid credentials
            messages.error(request, 'Invalid credentials.')
            return redirect('admindashboard:admin_login')

    # Render the admin login page
    return render(request, 'adminside/admin/admin_login.html')

@never_cache
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@admin_required
def admin_dashboard(request):
    if not request.user.is_staff:
        return redirect('admindashboard:admin_login')

    today = timezone.now()
    current_year = today.year
    current_month = today.month

    # Default chart data and range
    chart_data = {
        'labels': [],
        'data': []
    }
    payment_chart_data = {'labels': [], 'data': []}  # Initialize for pie chart
    default_range = "yearly"

    filter_type = request.GET.get('filter', 'yearly')  # Get filter, default to 'yearly'

    # --- Date Range Calculation (Common to all data) ---
    start_date = None  # Initialize start_date
    end_date = None    # Initialize end_date

    if filter_type == 'daily':
        start_date = today
        end_date = today
        default_range = 'daily'
    elif filter_type == 'weekly':
        start_date = today - timedelta(days=today.weekday())
        end_date = today
        default_range = 'weekly'
    elif filter_type == 'monthly':
        start_date = today.replace(day=1)
        end_date = today
        default_range = "monthly"
    elif filter_type == 'yearly':
        start_date = today.replace(month=1, day=1)
        end_date = today
        default_range = 'yearly'
    elif filter_type == 'all':  # Correctly handle 'all'
        start_date = None  # No start date for all time
        end_date = None     # No end date for all time
        default_range = 'all'

    # --- Data Fetching (Filtered by Date Range) ---

    # 1.  Order-based data (Sales Chart, Recent Orders)
    if start_date and end_date:
        orders = OrderMain.objects.filter(created_at__date__range=[start_date.date(), end_date.date()])
        order_items = OrderItem.objects.filter(order__created_at__date__range=[start_date.date(), end_date.date()])
    else:  # All time
        orders = OrderMain.objects.all()
        order_items = OrderItem.objects.all()


    # --- Sales Chart Data ---
    if filter_type == 'daily':
         orders_by_period = orders.aggregate(
            count=Count('id'),
            total=Sum('total_amount')
        )
         chart_data = {
            'labels': ['Today'],
            'data': [float(orders_by_period.get('total') or 0)],  # Use .get() for safety
         }

    elif filter_type == 'weekly':
        orders_by_period = orders.annotate(
            day=ExtractDay('created_at')
        ).values('day').annotate(
            count=Count('id'),
            total=Sum('total_amount')
        ).order_by('day')
        week_data = [0] * 7
        for item in orders_by_period:
            day_index = (item['day'] - start_date.day) % 7
            if 0 <= day_index < 7:  # Extra safety check
                week_data[day_index] = float(item.get('total') or 0)
        chart_data = {
            'labels': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
            'data': week_data,
        }

    elif filter_type == 'monthly':
        orders_by_period = orders.annotate(
            day=ExtractDay('created_at')
        ).values('day').annotate(
            count=Count('id'),
            total=Sum('total_amount')
        ).order_by('day')
        month_data = [0] * 31
        for item in orders_by_period:
            if item['day'] is not None: #checking for none
                month_data[item['day'] - 1] = float(item.get('total') or 0)
        chart_data = {
            'labels': [str(day) for day in range(1, 32)],  # Days of month
            'data': month_data
        }
        default_range = "monthly"

    elif filter_type == 'yearly':
        orders_by_period = orders.annotate(
            year=ExtractYear('created_at')
        ).values('year').annotate(
            count=Count('id'),
            total=Sum('total_amount')
        ).order_by('year')

        chart_data = {
            'labels': [str(item['year']) for item in orders_by_period],
            'data': [float(item.get('total') or 0) for item in orders_by_period], # Use get
        }
        default_range = 'yearly'

    else: # all time
        orders_by_period = orders.annotate(
            year=ExtractYear('created_at')
        ).values('year').annotate(
            count=Count('id'),
            total=Sum('total_amount')
        ).order_by('year')
        chart_data = {
            'labels': [str(item['year']) for item in orders_by_period],
            'data': [float(item.get('total') or 0) for item in orders_by_period], # Use get
        }
        default_range = 'all'


    # --- Pie Chart Data (Payment Methods) ---
    payment_methods = orders.values('payment_method').annotate(count=Count('id'))
    payment_chart_data = {
        'labels': [item['payment_method'] for item in payment_methods],
        'data': [item['count'] for item in payment_methods],
    }

     # --- (ii) Top Selling Products --- # Use order_items now
    top_products = order_items.values(
        'product_variant__product__product_name'
    ).annotate(
        total_quantity=Sum('quantity')
    ).order_by('-total_quantity')[:10]

    # --- (iii) Best Selling Category ---

    top_categories = order_items.values(
        'product_variant__product__category__name'
    ).annotate(
       total_quantity=Sum('quantity')
    ).order_by('-total_quantity')[:10]
    # --- (iv) Best Selling Authors ---
    top_authors = order_items.values(
        'product_variant__product__author__name'
    ).annotate(
       total_quantity=Sum('quantity')
    ).order_by('-total_quantity')[:10]

    # --- Recent Orders ---
    recent_orders = orders.order_by('-created_at')[:10]  # Limit to 10 most recent

    context = {
        'chart_data': chart_data,
        'payment_chart_data': payment_chart_data,  # Add pie chart data
        'top_products': top_products,
        'top_categories': top_categories,
        'top_authors': top_authors,
        'recent_orders': recent_orders, #passing to the template
        'default_range': default_range,  # Pass for button highlighting
    }
    return render(request, 'adminside/admin/admin_dashboard.html', context)

@never_cache
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@admin_required
def list_users(request):
    # Get search parameters
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    admin_filter = request.GET.get('admin', '') 
    
    # Start with all users except superusers
    users = User.objects.filter(is_active=True, is_superuser=False)
    
    # Apply search filter from backend
    if search_query:        
        users = users.annotate(
            full_name=Concat('first_name', Value(' '), 'last_name', output_field=CharField())
        ).filter(
            Q(first_name__icontains=search_query) |  
            Q(last_name__icontains=search_query) | 
            Q(full_name__icontains=search_query) | 
            Q(email__icontains=search_query) | 
            Q(phone_number__icontains=search_query)
        )
    
    # Apply status filter
    if status_filter:
        users = users.filter(is_blocked=(status_filter == 'inactive'))
    
    # Apply admin filter
    if admin_filter:
        users = users.filter(is_admin=(admin_filter == 'admin'))
    
    # Order the results
    users = users.order_by('date_joined')
    
    # Pagination
    per_page = 10
    paginator = Paginator(users, per_page)
    page = request.GET.get('page', 1)
    
    try:
        users = paginator.page(page)
    except PageNotAnInteger:
        users = paginator.page(1)
    except EmptyPage:
        users = paginator.page(paginator.num_pages)
    
    return render(request, 'adminside/admin/admin_user.html', {
        'users': users,
        'total_pages': paginator.num_pages,
        'current_page': int(page),
        'search_query': search_query,
        'status_filter': status_filter,
        'admin_filter': admin_filter
    })


@admin_required
def block_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    current_page = request.GET.get('page', '1')
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    admin_filter = request.GET.get('admin', '')
    
    if not user.is_blocked:
        user.is_blocked = True
        user.save()
        messages.success(request, f"User {user.full_name} has been blocked.")
    else:
        messages.info(request, f"User {user.full_name} is already blocked.")
    
    # Build the redirect URL with all parameters
    base_url = reverse('admindashboard:list_users')
    redirect_url = f"{base_url}?page={current_page}"
    if search_query:
        redirect_url += f"&search={search_query}"
    if status_filter:
        redirect_url += f"&status={status_filter}"
    if admin_filter:
        redirect_url += f"&admin={admin_filter}"
    
    return HttpResponseRedirect(redirect_url)


@admin_required
def unblock_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    current_page = request.GET.get('page', '1')
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    admin_filter = request.GET.get('admin', '')
    
    if user.is_blocked:
        user.is_blocked = False
        user.save()
        messages.success(request, f"User {user.full_name} has been unblocked.")
    else:
        messages.info(request, f"User {user.full_name} is not blocked.")
    
    # Build the redirect URL with all parameters
    base_url = reverse('admindashboard:list_users')
    redirect_url = f"{base_url}?page={current_page}"
    if search_query:
        redirect_url += f"&search={search_query}"
    if status_filter:
        redirect_url += f"&status={status_filter}"
    if admin_filter:
        redirect_url += f"&admin={admin_filter}"
    
    return HttpResponseRedirect(redirect_url)

@admin_required
def sales_report(request):
    filter_type = request.GET.get('filter', 'daily')
    today = timezone.now().date()
    
    # Set date range based on filter type
    if filter_type == 'daily':
        start_date = today
        end_date = today
    elif filter_type == 'weekly':
        start_date = today - timedelta(days=today.weekday())
        end_date = today
    elif filter_type == 'monthly':
        start_date = today.replace(day=1)
        end_date = today
    elif filter_type == 'yearly':
        start_date = today.replace(month=1, day=1)
        end_date = today
    else:  # Custom date range
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        if start_date and end_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            start_date = today
            end_date = today
    
    # Get orders for the date range
    orders = OrderMain.objects.filter(created_at__date__range=[start_date, end_date])
    
    # Calculate summary values
    total_sales = orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    total_discount = orders.aggregate(Sum('discount_amount'))['discount_amount__sum'] or 0
    
    # Calculate total refund amount
    total_refund = WalletTransaction.objects.filter(
        transaction_type='credit',
        timestamp__date__range=[start_date, end_date],
        description__icontains='refund'  # Only count refunds
    ).aggregate(Sum('amount'))['amount__sum'] or 0
    
    # Enhance order data with calculated values
    enhanced_orders = []
    for order in orders:
        # Calculate MRP total for the order
        order_mrp_total = Decimal('0.00')
        for item in order.items.all():
            original_price = item.product_variant.price
            order_mrp_total += Decimal(original_price) * item.quantity
        
        # Calculate item discount total
        item_discount_total = Decimal('0.00')
        for item in order.items.all():
            original_price = item.product_variant.price
            discounted_price = item.price
            item_discount = (original_price - discounted_price) * item.quantity
            item_discount_total += item_discount
        
        # Get refund amount for this order
        refund_amount = WalletTransaction.objects.filter(
            transaction_type='credit',
            description__icontains=order.order_id
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        # Calculate shipping charge
        shipping_charge = getattr(settings, "SHIPPING_CHARGE", Decimal('50.00'))
        
        # Calculate order subtotal (after item discounts but before coupon)
        order_subtotal = order_mrp_total - item_discount_total
        
        enhanced_orders.append({
            'order': order,
            'mrp_total': order_mrp_total,
            'item_discount_total': item_discount_total,
            'subtotal': order_subtotal,
            'coupon_discount': order.discount_amount,
            'shipping_charge': shipping_charge,
            'refund_amount': refund_amount
        })
    
    # --- Pagination Logic ---
    page = request.GET.get('page', 1)
    paginator = Paginator(enhanced_orders, ITEMS_PER_PAGE)

    try:
        paginated_orders = paginator.page(page)
    except PageNotAnInteger:
        paginated_orders = paginator.page(1)
    except EmptyPage:
        paginated_orders = paginator.page(paginator.num_pages)

    if request.GET.get('format') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="sales_report_{start_date}_to_{end_date}.csv"'
        writer = csv.writer(response)
        
        # Write header with filter information
        writer.writerow(['WordBloom Sales Report'])
        writer.writerow([f'Filter: {filter_type.capitalize()}'])
        writer.writerow([f'Period: {start_date} to {end_date}'])
        writer.writerow([f'Generated on: {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}'])
        writer.writerow([])  # Empty row for spacing
        
        writer.writerow(['Order ID', 'Date', 'Order MRP', 'Item Discount', 'Order Subtotal', 
                         'Coupon Discount', 'Shipping Charge', 'Total Amount', 'Refund Amount', 'Payment Method'])
        
        for order_data in enhanced_orders:
            order = order_data['order']
            writer.writerow([
                order.order_id,
                order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                f"{order_data['mrp_total']:.2f}",
                f"{order_data['item_discount_total']:.2f}",
                f"{order_data['subtotal']:.2f}",
                f"{order.discount_amount:.2f}",
                f"{order_data['shipping_charge']:.2f}",
                f"{order.total_amount:.2f}",
                f"{order_data['refund_amount']:.2f}",
                order.payment_method
            ])
        
        # Write summary
        writer.writerow([])  # Empty row for spacing
        writer.writerow(['Summary'])
        writer.writerow(['Total Sales:', f"{total_sales:.2f}"])
        writer.writerow(['Total Discount:', f"{total_discount:.2f}"])
        writer.writerow(['Total Refund:', f"{total_refund:.2f}"])
        
        return response
    
    elif request.GET.get('format') == 'pdf':
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="sales_report_{start_date}_to_{end_date}.pdf"'
        buffer = BytesIO()
        
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A3))
        elements = []
        
        # Add logo and company name
        logo_path = os.path.join(settings.BASE_DIR, 'static', 'userside', 'assets', 'imgs', 'theme', 'icons', 'logo_wordbloom.png')
        
        # Create a table for header with logo and title
        try:
            logo = Image(logo_path, width=50, height=50)
            header_data = [[logo, "WordBloom Sales Report"]]
            header_table = Table(header_data, colWidths=[80, 400])
            header_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                ('ALIGN', (1, 0), (1, 0), 'LEFT'),
                ('VALIGN', (0, 0), (1, 0), 'MIDDLE'),
                ('FONTNAME', (1, 0), (1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (1, 0), (1, 0), 16),
            ]))
            elements.append(header_table)
        except Exception:
            elements.append(Paragraph("WordBloom Sales Report", getSampleStyleSheet()['Title']))
        
        elements.append(Spacer(1, 10))
        
        # Add filter information
        filter_data = [
            ['Filter:', filter_type.capitalize()],
            ['Period:', f"{start_date} to {end_date}"],
            ['Generated on:', timezone.now().strftime("%Y-%m-%d %H:%M:%S")]
        ]
        filter_table = Table(filter_data, colWidths=[100, 380])
        filter_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ]))
        elements.append(filter_table)
        
        elements.append(Spacer(1, 20))
        
        # Create main data table
        data = [['Order ID', 'Date', 'MRP', 'Item Discount', 'Subtotal', 'Coupon', 'Shipping', 'Total', 'Refund', 'Payment']]
        
        for order_data in enhanced_orders:
            order = order_data['order']
            data.append([
                str(order.order_id),
                order.created_at.strftime('%Y-%m-%d'),
                f"Rs.{order_data['mrp_total']:.2f}",
                f"-Rs.{order_data['item_discount_total']:.2f}",
                f"Rs.{order_data['subtotal']:.2f}",
                f"-Rs.{order.discount_amount:.2f}",
                f"Rs.{order_data['shipping_charge']:.2f}",
                f"Rs.{order.total_amount:.2f}",
                f"Rs.{order_data['refund_amount']:.2f}",
                order.payment_method[:10]  # Limit length for PDF formatting
            ])
        
        # Create the table with appropriate column widths
        col_widths = [120, 100, 100, 100, 100, 100, 100, 100, 100, 150]
        table = Table(data, colWidths=col_widths)
        
        # Style the table
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 12),
            ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),  # Right-align numeric columns
            ('ALIGN', (-1, 1), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ])
        table.setStyle(style)
        elements.append(table)
        
        elements.append(Spacer(1, 20))
        
        # Add summary
        summary_data = [
            ['Summary'],
            ['Total Sales:', f"Rs.{total_sales:.2f}"],
            ['Total Discount:', f"- Rs.{total_discount:.2f}"],
            ['Total Refund:', f"Rs.{total_refund:.2f}"]
        ]
        summary_table = Table(summary_data, colWidths=[100, 200])
        summary_style = TableStyle([
            ('SPAN', (0, 0), (1, 0)),  # Span the header row
            ('BACKGROUND', (0, 0), (1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (1, 0), 8),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (1, -1), 1, colors.black)
        ])
        summary_table.setStyle(summary_style)
        elements.append(summary_table)
        
        doc.build(elements)
        pdf = buffer.getvalue()
        buffer.close()
        response.write(pdf)
        return response
    
    # Prepare context for HTML rendering
    context = {
        # 'orders': enhanced_orders,
        'orders': paginated_orders,
        'total_sales': total_sales,
        'total_discount': total_discount,
        'total_refund': total_refund,
        'filter_type': filter_type,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    return render(request, 'adminside/sales_report/sales_report.html', context)



# @never_cache
@cache_control(no_cache = True, must_revalidate = True, no_store = True)
@admin_required
def admin_logout(request):
    logout(request)
    messages.success(request, "You have been logged out successfully")
    return redirect('admindashboard:admin_login')
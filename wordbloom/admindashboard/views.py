from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.decorators.cache import never_cache, cache_control
from utils.decorators import admin_required
from django.contrib.auth.decorators import login_required
from accounts.models import User
from category.models import Category
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Value, CharField
from django.db.models.functions import Concat
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.db.models import Sum
from django.utils import timezone
from datetime import datetime
from datetime import timedelta
from orders.models import OrderMain
from django.shortcuts import render
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta
from django.http import HttpResponse
import csv
from io import BytesIO
from io import StringIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image, Spacer
from reportlab.lib import colors
import os
from django.conf import settings
from django.db.models import Count, Sum, F
from django.db.models.functions import ExtractYear, ExtractMonth
from django.utils import timezone
from datetime import timedelta
from orders.models import OrderItem
from django.db.models.functions import ExtractYear, ExtractDay


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


# @never_cache
# @cache_control(no_cache=True, must_revalidate=True, no_store=True)
# @admin_required
# def admin_dashboard(request):
#     if not request.user.is_staff:
#         return redirect('admindashboard:admin_login')
#     return render(request, 'adminside/admin/admin_dashboard.html')

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
    
    # Start with all users
    users = User.objects.filter(is_active=True)
    
    # Apply search filter from backend
    if search_query:
        # users = users.filter(
        #     Q(first_name__icontains=search_query) | 
        #     Q(last_name__icontains=search_query) |
        #     Q(full_name__icontains=search_query) |
        #     Q(email__icontains=search_query) |
        #     Q(phone_number__icontains=search_query)
        # )
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

    orders = OrderMain.objects.filter(created_at__date__range=[start_date, end_date])
    total_sales = orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    # Add discount calculation
    # total_discount = orders.aggregate(Sum('discount_amount'))['discount_amount__sum'] or 0
    # net_sales = total_sales - total_discount

    if request.GET.get('format') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="sales_report.csv"'
        writer = csv.writer(response)
        # Add discount header
        # writer.writerow(['Order ID', 'Date', 'Total Amount', 'Discount Amount', 'Net Amount'])
        writer.writerow(['Order ID', 'Date', 'Total Amount'])
        for order in orders:
            # Add discount and net amount
            # net_amount = order.total_amount - order.discount_amount
            # writer.writerow([order.order_id, order.created_at, order.total_amount, order.discount_amount, net_amount])
            writer.writerow([order.order_id, order.created_at, order.total_amount])
        return response

    elif request.GET.get('format') == 'pdf':
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="sales_report.pdf"'

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []

        # Add logo at the top
        logo_path = os.path.join(settings.BASE_DIR, 'static', 'userside', 'assets', 'imgs', 'theme', 'icons', 'logo_wordbloom.png')
        logo = Image(logo_path, width=50, height=50)
        elements.append(logo)
        elements.append(Spacer(1, 10))  # Add space after the logo

        # Create table data with or without discount
        # data = [['Order ID', 'Date', 'Total Amount', 'Discount', 'Net Amount']]
        data = [['Order ID', 'Date', 'Total Amount']]
        for order in orders:
            # Version with discount
            # net_amount = order.total_amount - order.discount_amount
            # data.append([
            #     str(order.order_id),
            #     order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            #     f"Rs.{order.total_amount:.2f}",
            #     f"Rs.{order.discount_amount:.2f}",
            #     f"Rs.{net_amount:.2f}"
            # ])
            
            # Version without discount
            data.append([
                str(order.order_id),
                order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                f"Rs.{order.total_amount:.2f}"
            ])

        # Create the table with style
        table = Table(data)
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ])
        table.setStyle(style)
        elements.append(table)

        # Add summary section at the bottom
        elements.append(Spacer(1, 20))
        summary_data = [
            ['Summary'],
            ['Total Sales:', f"Rs.{total_sales:.2f}"],
            # ['Total Discount:', f"Rs.{total_discount:.2f}"],
            # ['Net Sales:', f"Rs.{net_sales:.2f}"]
        ]
        summary_table = Table(summary_data)
        summary_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ])
        summary_table.setStyle(summary_style)
        elements.append(summary_table)

        # Build the PDF document
        doc.build(elements)
        
        pdf = buffer.getvalue()
        buffer.close()
        response.write(pdf)
        return response

    context = {
        'orders': orders,
        'total_sales': total_sales,
        # 'total_discount': total_discount,
        # 'net_sales': net_sales,
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
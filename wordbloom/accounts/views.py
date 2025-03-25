from django.shortcuts import render,redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from .forms import UserRegisterForm
from .models import User
from django.contrib.auth import login as auth_login, authenticate, get_backends
from django.core.mail import send_mail
from django.conf import settings
from django.utils.crypto import get_random_string
from django.utils.timezone import now
from datetime import timedelta
from datetime import datetime, timedelta
from django.db import IntegrityError
from django.contrib.auth import get_user_model
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_control
from django.views.decorators.cache import never_cache
from category.models import Category, CategoryOffer
from products.models import Author
from products.models import Product, Category
from products.models import Product, ProductVariant, VariantImage
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Prefetch
from django.shortcuts import render
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db import models
from django.db.models import Prefetch, Q, F
from products.models import Product, ProductVariant, VariantImage
from category.models import Category
from authors.models import Author
from django.db.models import Case, When, F, Value, Min, OuterRef, Subquery
from django.db.models import F, Q, Case, When, Prefetch, OuterRef, Subquery, DecimalField
from django.db.models.query import Prefetch
from decimal import Decimal, InvalidOperation, DecimalException
from userpanel.models import Wishlist
from django.contrib.auth.forms import AuthenticationForm
from .forms import UserRegisterForm, CustomPasswordResetForm, CustomSetPasswordForm


User = get_user_model()
ITEMS_PER_PAGE = 8

# Create your views here.

# @never_cache
# @cache_control(no_cache = True, must_revalidate = True, no_store = True)
# def home(request):
#     return render(request,"userside/account/index.html")

@never_cache
@cache_control(no_cache = True, must_revalidate = True, no_store = True)
def home(request):
    # Get active categories
    categories = Category.objects.filter(is_active=True)
    
    # Get featured books (for example, the most recent 4 active products)
    featured_products = Product.objects.filter(
        variants__is_active=True,
        author__is_active=True
    ).select_related('author').distinct().order_by('-product_id')[:4]
    
    # Annotate with preferred variant
    featured_products = featured_products.annotate(
        preferred_variant_id=Subquery(
            ProductVariant.objects.filter(
                product=OuterRef('pk'),
                is_active=True
            ).order_by(
                Case(
                    When(format='Paperback', then=0),  # Prioritize Paperback
                    When(format='Hardcover', then=1),  # Next prioritize Hardcover
                    default=2  # Fallback to other formats
                ),
                'id'  # Fallback to the first variant if multiple variants have the same format
            ).values('id')[:1]
        )
    )
    
    # Prefetch the preferred variant and its primary image
    featured_products = featured_products.prefetch_related(
        Prefetch(
            'variants',
            queryset=ProductVariant.objects.filter(
                is_active=True
            ).prefetch_related(
                Prefetch(
                    'images',
                    queryset=VariantImage.objects.filter(is_primary=True),
                    to_attr='primary_images'
                )
            ),
            to_attr='active_variants'
        )
    )
    
    # Check if products are in wishlist for authenticated users
    if request.user.is_authenticated:
        wishlisted_items = {}
        for product in featured_products:
            if product.active_variants:
                first_variant = product.active_variants[0]
                is_wishlisted = Wishlist.objects.filter(
                    user=request.user, 
                    product=product,
                    variant=first_variant
                ).exists()
                wishlisted_items[product.product_id] = is_wishlisted
    else:
        wishlisted_items = {}
    
    context = {
        'categories': categories,
        'featured_products': featured_products,
        'wishlisted_items': wishlisted_items,
    }
    
    return render(request, "userside/account/index.html", context)


@never_cache
def user_register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        
        if form.is_valid():
            # Extract data from the form
            email = form.cleaned_data.get('email')
            first_name = form.cleaned_data.get('first_name')
            last_name = form.cleaned_data.get('last_name')
            phone_number = form.cleaned_data.get('phone_number')
            password = form.cleaned_data.get('password')

            otp = get_random_string(length=6, allowed_chars='1234567890')  # Generate OTP
            print(otp)  # For debugging

            try:
                send_mail(
                    'Your OTP code',
                    f'Your OTP is {otp}',
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
            except Exception as e:
                messages.error(request, f'Error sending email: {e}')
                return redirect('accounts:user_register')

            # Store user details and OTP in the session
            request.session['user_registration_data'] = {
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'phone_number': phone_number,
                'password': password,
                'otp': otp,
                'otp_created_at': now().isoformat(),  # Save current time in ISO format
            }

            messages.success(request, f'An OTP has been sent to {email}. Please verify.')
            return redirect('accounts:verify_otp')  # Redirect to the OTP verification page
        else:
            messages.error(request, 'Please correct the errors below.')
            return render(request, 'userside/account/user_register.html', {'form': form, 'errors': form.errors})
    else:
        form = UserRegisterForm()

    return render(request, 'userside/account/user_register.html', {'form': form})

@never_cache
def verify_otp(request):
    MAX_ATTEMPTS = 5  # The maximum allowed attempts
    
    # Redirect authenticated users to the homepage
    if request.user.is_authenticated:
        return redirect('accounts:home')

    if request.method == 'POST':
        otp = ''.join([request.POST.get(f'otp_digit_{i}', '') for i in range(1, 7)])
        user_data = request.session.get('user_registration_data')

        if not user_data:
            messages.error(request, 'No registration data found. Please try registering again.')
            return redirect('accounts:user_register')

        saved_otp = user_data.get('otp')
        otp_created_at = user_data.get('otp_created_at')

        # Track OTP attempts
        otp_attempts = user_data.get('otp_attempts', 0) + 1
        if otp_attempts > MAX_ATTEMPTS:
            messages.error(request, 'Too many invalid OTP attempts. Please register again.')
            return redirect('accounts:user_register')

        user_data['otp_attempts'] = otp_attempts
        request.session['user_registration_data'] = user_data

        if not saved_otp or not otp_created_at:
            messages.error(request, 'Invalid OTP data. Please try registering again.')
            return redirect('accounts:user_register')

        otp_created_at = datetime.fromisoformat(otp_created_at)
        otp_age = now() - otp_created_at

        if otp_age > timedelta(minutes=2):
            messages.error(request, 'OTP has expired. Please click on Resend OTP.')
            return redirect('accounts:verify_otp')

        if otp == saved_otp:
            # Check if a user with the given email already exists
            if get_user_model().objects.filter(email=user_data['email']).exists():
                messages.error(request, 'A user with this email already exists. Please log in or use a different email.')
                return redirect('accounts:user_register')

            try:
                # Create the new user
                user = get_user_model().objects.create_user(
                    email=user_data['email'],
                    first_name=user_data['first_name'],
                    last_name=user_data['last_name'],
                    phone_number=user_data['phone_number'],
                    password=user_data['password']
                )
                user.is_active = True
                user.save()

                # Get the backend and set it explicitly
                backend = get_backends()[0]  # Choose the appropriate backend
                user.backend = f'{backend.__module__}.{backend.__class__.__name__}'

                auth_login(request, user)

                # Clean up session
                try:
                    del request.session['user_registration_data']
                except KeyError:
                    pass

                messages.success(request, 'Your account has been verified and created successfully!')
                return redirect('accounts:home')

            except IntegrityError:
                messages.error(request, 'An error occurred while creating your account. Please try again.')
                return redirect('accounts:user_register')

        else:
            messages.error(request, 'Invalid OTP. Please try again.')

    return render(request, 'userside/account/verify_otp.html')



@never_cache
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def resend_otp(request):
    # Retrieve user registration data stored in session
    user_data = request.session.get('user_registration_data')

    if not user_data:
        messages.error(request, 'No registration data found. Please try registering again.')
        return redirect('accounts:user_register')
    
    # Initialize or increment resend count
    user_data['resend_count'] = user_data.get('resend_count',0) + 1

    # Check if resend attempts exceed the limit
    if user_data['resend_count'] > 3:
        messages.error(request, 'Maximum resend attempts reached. Please register again.')
        return redirect('accounts:user_register')

    # Generate a new OTP
    new_otp = get_random_string(length=6, allowed_chars='1234567890')  # Generate new OTP
    print(new_otp)  # For debugging

    # Update OTP and timestamp in session
    user_data['otp'] = new_otp
    user_data['otp_created_at'] = now().isoformat()
    request.session['user_registration_data'] = user_data

    # Send the new OTP to the user's email
    send_mail(
        'Welcome to WordBloom - Your Online Book Store',
        f'Your new OTP code is {new_otp}',
        settings.DEFAULT_FROM_EMAIL,
        [user_data['email']],
        fail_silently=False,
    )

    messages.success(request, f'A new OTP has been sent to {user_data["email"]}.')
    return redirect('accounts:verify_otp')


@never_cache
@cache_control(no_cache = True, must_revalidate = True, no_store = True)
def user_login(request):
    # Redirect authenticate users to the homepage
    if request.user.is_authenticated:
        return redirect('accounts:home')
    if request.method == 'POST':
        # print("hi")
        email = request.POST.get('email')
        password = request.POST.get('password')
        # print("email",email)
        # print("pass",password)
        user = authenticate(request, username = email, password = password)
        print(user)
        if user is not None:
            if user.is_blocked:
                messages.error(request, 'Your account is blocked. Please contact support.')
                return redirect('accounts:user_login')

            auth_login(request, user)
            messages.success(request, f"Welcome back, {user.first_name}!")
            next_url = request.GET.get('next')
            return redirect(next_url or 'accounts:home')
        else:
            messages.error(request, 'Invalid email or password.')
    return render(request, 'userside/account/user_login.html')       

def shop(request):
    categories = Category.objects.filter(is_active=True)
    authors = Author.objects.filter(is_active=True)
    
    # Start with base query for products with active variants
    products = Product.objects.filter(
        variants__is_active=True,
        author__is_active=True
    ).select_related('author').distinct()
    

    # Annotate with preferred variant
    products = products.annotate(
        preferred_variant_id=Subquery(
            ProductVariant.objects.filter(
                product=OuterRef('pk'),
                is_active=True
            ).order_by(
                Case(
                    When(format='Paperback', then=0),  # Prioritize Paperback
                    When(format='Hardcover', then=1),  # Next prioritize Hardcover
                    default=2  # Fallback to other formats
                ),
                'id'  # Fallback to the first variant if multiple variants have the same format
            ).values('id')[:1]
        )
    )

    # Annotate with the minimum effective price across all variants
    products = products.annotate(
        min_effective_price=Min(
            Case(
                When(variants__discounted_price__isnull=False, 
                     then=F('variants__discounted_price')),
                default=F('variants__price'),
                output_field=models.DecimalField(),
            )
        )
    )

    # Prefetch the preferred variant and its primary image
    products = products.prefetch_related(
        Prefetch(
            'variants',
            queryset=ProductVariant.objects.filter(
                is_active=True
            ).prefetch_related(
                Prefetch(
                    'images',
                    queryset=VariantImage.objects.filter(is_primary=True),
                    to_attr='primary_images'
                )
            ),
            to_attr='active_variants'
        )
    )

    if request.user.is_authenticated:
         wishlisted_items = {}
         for product in products:
             if product.active_variants:
                first_variant = product.active_variants[0]
                is_wishlisted = Wishlist.objects.filter(user=request.user, product=product,variant=first_variant).exists()
                wishlisted_items[product.product_id]=  is_wishlisted
    else:
        wishlisted_items = {}

    # Apply filters
    category_id = request.GET.getlist('category')
    if category_id:
        products = products.filter(category_id__in=category_id)
    
    # Apply price filtering
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price or max_price:
        try:
            min_price = Decimal(min_price) if min_price else None
            max_price = Decimal(max_price) if max_price else None
            
            price_filter = Q()
            if min_price and max_price:
                price_filter = Q(min_effective_price__gte=min_price) & Q(min_effective_price__lte=max_price)
            elif min_price:
                price_filter = Q(min_effective_price__gte=min_price)
            elif max_price:
                price_filter = Q(min_effective_price__lte=max_price)
            
            products = products.filter(price_filter)
        except (ValueError, TypeError, DecimalException) as e:
            messages.error(request, f"Invalid price format: {e}")
            pass

    # Author filtering
    author_ids = request.GET.getlist('author')
    if author_ids:
        valid_author_ids = [int(aid) for aid in author_ids if aid.isdigit()]
        if valid_author_ids:
            products = products.filter(author_id__in=valid_author_ids)    

    # Sorting
    sort_by = request.GET.get('sort', 'popularity')
    if sort_by == 'price-low-high':
        products = products.order_by('min_effective_price', '-product_id')
    elif sort_by == 'price-high-low':
        products = products.order_by('-min_effective_price', '-product_id')
    elif sort_by == 'newest':
        products = products.order_by('-product_id')
    else:  # 'popularity' (default)
        products = products.order_by('product_id')

    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(products, ITEMS_PER_PAGE)
    try:
        products = paginator.page(page)
    except PageNotAnInteger:
        products = paginator.page(1)
    except EmptyPage:
        products = paginator.page(paginator.num_pages)
    
    context = {
        'categories': categories,
        'products': products,
        'authors': authors,
        'selected_categories': category_id,
        'min_price': min_price,
        'max_price': max_price,
        'selected_authors': author_ids,
        'sort_by': sort_by,
        'wishlisted_items': wishlisted_items,
    }
    return render(request, 'userside/product/shop_page.html', context)


# def product_detail(request, product_id):
#     product = get_object_or_404(Product, product_id=product_id)
    
#     # Get all active variants
#     active_variants = product.variants.filter(is_active=True)
    
#     # First try to get Paperback variant, if not available get the first active variant
#     default_variant = (
#         active_variants.filter(format='Paperback').first() or 
#         active_variants.first()
#     )
    
#     # Get images only for the default variant
#     default_variant_images = []
    
#     if default_variant:
#         default_variant_images = default_variant.images.all().order_by('display_order')
#         default_primary_image = default_variant_images.filter(is_primary=True).first()

#     # Prepare variant data (only include active variants)
#     variant_data = []
#     for variant in active_variants:
#         variant_data.append({
#             'id': variant.id,
#             'format': variant.format,
#             'price': float(variant.price),
#             'discounted_price': float(variant.discounted_price) if variant.discounted_price else None,
#             'stock': variant.stock,
#             'isbn': variant.isbn,
#             'page_count': variant.page_count,
#             'images': [{'url': image.image.url, 'is_primary': image.is_primary} 
#                       for image in variant.images.all().order_by('display_order')]
#         })
#     # Get wishlisted variants for this product (for authenticated users)
#     wishlisted_variant_ids = []
#     if request.user.is_authenticated:
#         wishlisted_variants = Wishlist.objects.filter(
#             user=request.user,
#             product=product
#         ).values_list('variant_id', flat=True)
#         wishlisted_variant_ids = list(wishlisted_variants)

#     context = {
#         'product': product,
#         'variants': active_variants,
#         'variant_data': variant_data,
#         'default_variant': default_variant,
#         'default_variant_images': default_variant_images,
#         'default_primary_image': default_primary_image,
#         'wishlisted_variant_ids': wishlisted_variant_ids,
#     }
#     return render(request, 'userside/account/product_details.html', context)


def product_detail(request, product_id):
    product = get_object_or_404(Product, product_id=product_id)
    
    # Get all active variants
    active_variants = product.variants.filter(is_active=True)

    # First try to get Paperback variant, if not available get the first active variant
    default_variant = (
        active_variants.filter(format='Paperback').first() or
        active_variants.first()
    )
    
    # Get images only for the default variant
    default_variant_images = []
    if default_variant:
        default_variant_images = default_variant.images.all().order_by('display_order')
        default_primary_image = default_variant_images.filter(is_primary=True).first()
    
    # Prepare variant data (only include active variants)
    variant_data = []
    for variant in active_variants:
        # Get full discount information
        discount_info = variant.get_discount_info()
        
        variant_data.append({
            'id': variant.id,
            'format': variant.format,
            'price': float(variant.price),
            'discounted_price': float(variant.discounted_price) if variant.discounted_price else None,
            'stock': variant.stock,
            'isbn': variant.isbn,
            'page_count': variant.page_count,
            'images': [{'url': image.image.url, 'is_primary': image.is_primary}
                       for image in variant.images.all().order_by('display_order')],
            'discount_info': {
                'type': discount_info.get('type', ''),
                'offer_name': discount_info.get('offer_name', ''),
                'original_price': float(discount_info.get('original_price', variant.price)),
                'effective_price': float(discount_info.get('effective_price', variant.price)),
                'discount_amount': float(discount_info.get('discount_amount', 0)),
                'discount_percentage': round((variant.price - discount_info.get('effective_price', variant.price)) / variant.price * 100, 2) if variant.price > discount_info.get('effective_price', variant.price) else 0
            }
        })
    
    # Get wishlisted variants for this product (for authenticated users)
    wishlisted_variant_ids = []
    if request.user.is_authenticated:
        wishlisted_variants = Wishlist.objects.filter(
            user=request.user,
            product=product
        ).values_list('variant_id', flat=True)
        wishlisted_variant_ids = list(wishlisted_variants)
    
    context = {
        'product': product,
        'variants': active_variants,
        'variant_data': variant_data,
        'default_variant': default_variant,
        'default_variant_images': default_variant_images,
        'default_primary_image': default_primary_image if 'default_primary_image' in locals() else None,
        'wishlisted_variant_ids': wishlisted_variant_ids,
    }
    
    return render(request, 'userside/account/product_details.html', context)



def category(request):
    return render(request, 'userside/product/category_page.html')

def authors(request):
    return render(request, 'userside/product/authors_page.html')

def contact(request):
    return render(request, 'userside/account/contact.html')

def aboutus(request):
    return render(request, 'userside/account/aboutus.html')

# def forgot_password(request):
#     return render(request, 'userside/account/forgot_password.html')

@login_required
@cache_control(no_cache = True, must_revalidate = True, no_store = True)
def user_logout(request):
    logout(request)
    request.session.flush()  # Ensure all session data is removed
    messages.success(request, "You have been logged out successfully")
    return redirect('accounts:home')
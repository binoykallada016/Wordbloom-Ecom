from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache, cache_control
from .models import Category, CategoryOffer
from django.utils import timezone
from utils.decorators import admin_required
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.urls import reverse
from django.http import HttpResponseRedirect

@never_cache
@admin_required
def category_list(request):
    # Get search parameter
    search_query = request.GET.get('search', '')
    
    # Base QuerySet
    categories = Category.objects.all().order_by('-id')
    
    # Apply search filter if search query exists
    if search_query:
        categories = categories.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Pagination
    page = request.GET.get('page', 1)
    items_per_page = 7
    
    paginator = Paginator(categories, items_per_page)
    
    try:
        categories = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page
        categories = paginator.page(1)
    except EmptyPage:
        # If page is out of range, deliver last page of results
        categories = paginator.page(paginator.num_pages)
    
    context = {
        'categories': categories,
        'search_query': search_query,
    }
    
    return render(request, 'adminside/category/admin_category_list.html', context)



@never_cache
@admin_required
def add_category(request):
    if request.method == 'POST':
        name = request.POST.get('categoryName').strip()
        description = request.POST.get('categoryDescription').strip()

        # Validate name length
        if not name or len(name) < 3:
            messages.error(request, 'Category name must be at least 3 characters long.')
            return redirect('category:add_category')

        # Check if category name already exists (case-insensitive check)
        if Category.objects.filter(name__iexact=name).exists():
            messages.error(request, 'Category name already exists.')
            return redirect('category:add_category')

        # Attempt to create the category
        try:
            Category.objects.create(name=name, description=description)
            messages.success(request, f'Category : {name} added successfully.')
        except IntegrityError:
            messages.error(request, 'Category name already exists.')  # Unique constraint error
            return redirect('category:add_category')
        except ValidationError as e:
            messages.error(request, f'Error: {e}') # Handle general validation errors
        return redirect('category:category_list')

    return render(request, 'adminside/category/admin_category_add.html')

@never_cache
# @cache_control(no_cache=True, must_revalidate=True, no_store=True)
@admin_required
def edit_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    
    if request.method == 'POST':
        name = request.POST.get('categoryName')
        description = request.POST.get('categoryDescription')
        
        # Check if another category with the same name exists
        if Category.objects.filter(name=name).exclude(id=category_id).exists():
            messages.error(request, f'A category with the name {name} already exists!')
            return redirect('category:category_list')

        try:
            category.name = name
            category.description = description
            category.save()
            messages.success(request, f'Category : {category.name} updated successfully.')
        except Exception as e:
            messages.error(request, f'Error updating category: {str(e)}')
        
        return redirect('category:category_list')
    
    # Render the template for editing category
    return render(request, 'adminside/category/admin_category_edit.html', {
        'category': category
    })


@never_cache
@admin_required
def delete_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    
    try:
        category.is_active = not category.is_active
        category.save()
        action = "restored" if category.is_active else "deactivated"
        messages.success(request, f'Category: {category.name} has been {action}.')
    except Exception as e:
        messages.error(request, f'Error updating category status: {str(e)}')
    
    return redirect('category:category_list')


@never_cache
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@admin_required
def add_category_offer(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    
    if request.method == 'POST':
        offer_name = request.POST.get('offerName')
        discount_type = request.POST.get('discountType')
        discount_value = request.POST.get('discountValue')
        minimum_purchase_amount = request.POST.get('minimumPurchaseAmount')
        
        try:
            # Deactivate existing offers for this category
            CategoryOffer.objects.filter(category=category, is_active=True).update(is_active=False)

            CategoryOffer.objects.create(
                category=category,
                offer_name=offer_name,
                discount_type=discount_type,
                discount_value=discount_value,
                minimum_purchase_amount=minimum_purchase_amount,
                start_date=timezone.now(),
                end_date=timezone.now() + timezone.timedelta(days=30),
                is_active=True  # The new offer as active
            )
            messages.success(request, f'Offer : {offer_name} added to category {category.name}.')
        except Exception as e:
            messages.error(request, f'Error adding category offer: {str(e)}')
        
        return redirect('category:category_list')
    
    return render(request, 'adminside/category/admin_category_list.html', {
        'category': category
    })
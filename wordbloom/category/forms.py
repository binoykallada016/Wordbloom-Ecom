from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from .models import Category
from .forms import CategoryForm, CategoryOfferForm

def add_category(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
            messages.success(request, f'Category "{category.name}" added successfully.')
            return redirect('category:category_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    
    return render(request, 'adminside/category/admin_category_list.html')

def add_category_offer(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    
    if request.method == 'POST':
        form = CategoryOfferForm(request.POST)
        if form.is_valid():
            offer = form.save(commit=False)
            offer.category = category
            offer.start_date = timezone.now()
            offer.end_date = timezone.now() + timezone.timedelta(days=30)
            offer.save()
            
            messages.success(request, f'Offer "{offer.offer_name}" added to category "{category.name}".')
            return redirect('category:category_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    
    return render(request, 'adminside/category/admin_category_list.html', {
        'category': category
    })
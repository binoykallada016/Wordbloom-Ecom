from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Author
from .forms import AuthorForm
from utils.decorators import admin_required
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

# Create your views here.

# def admin_authors(request):
#     authors = Author.objects.all().order_by('-created_at')
#     return render(request, 'adminside/authors/admin_authors.html', {'authors': authors})

# Define the number of items per page
ITEMS_PER_PAGE = 6  # You can adjust this value as needed

@admin_required
def admin_authors(request):
    search_query = request.GET.get('search', '')
    
    if search_query:
        authors = Author.objects.filter(
            Q(name__icontains=search_query) |
            Q(bio__icontains=search_query)
        ).order_by('-created_at')
    else:
        authors = Author.objects.all().order_by('-created_at')
    
    page = request.GET.get('page', 1)
    paginator = Paginator(authors, ITEMS_PER_PAGE)
    
    try:
        authors = paginator.page(page)
    except PageNotAnInteger:
        authors = paginator.page(1)
    except EmptyPage:
        authors = paginator.page(paginator.num_pages)
    
    context = {
        'authors': authors,
        'search_query': search_query,
    }
    
    return render(request, 'adminside/authors/admin_authors.html', context)


@admin_required
def admin_add_author(request):
    if request.method == 'POST':
        form = AuthorForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Author added successfully.')
            return redirect('authors:admin_authors')
    else:
        form = AuthorForm()
    return render(request, 'adminside/authors/admin_add_author.html', {'form': form})

@admin_required
def admin_edit_author(request, author_id):
    author = get_object_or_404(Author, author_id=author_id)
    if request.method == 'POST':
        form = AuthorForm(request.POST, instance=author)
        if form.is_valid():
            form.save()
            messages.success(request, 'Author updated successfully.')
            return redirect('authors:admin_authors')
    else:
        form = AuthorForm(instance=author)
    return render(request, 'adminside/authors/admin_edit_author.html', {'form': form, 'author': author})

@admin_required
def admin_delete_author(request, author_id):
    author = get_object_or_404(Author, author_id=author_id)
    author.soft_delete()
    messages.success(request, 'Author deleted successfully.')
    return redirect('authors:admin_authors')

@admin_required
def admin_restore_author(request, author_id):
    author = get_object_or_404(Author, author_id=author_id)
    author.restore()
    messages.success(request, 'Author restored successfully.')
    return redirect('authors:admin_authors')
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Author
from .forms import AuthorForm

# Create your views here.
def admin_authors(request):
    authors = Author.objects.all().order_by('-created_at')
    return render(request, 'adminside/authors/admin_authors.html', {'authors': authors})

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

def admin_delete_author(request, author_id):
    author = get_object_or_404(Author, author_id=author_id)
    author.soft_delete()
    messages.success(request, 'Author deleted successfully.')
    return redirect('authors:admin_authors')

def admin_restore_author(request, author_id):
    author = get_object_or_404(Author, author_id=author_id)
    author.restore()
    messages.success(request, 'Author restored successfully.')
    return redirect('authors:admin_authors')
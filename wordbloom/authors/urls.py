from django.urls import path
from . import views
app_name = 'authors'

urlpatterns = [
    path('admin/authors/', views.admin_authors, name='admin_authors'),
    path('admin/authors/add/', views.admin_add_author, name='admin_add_author'),
    path('admin/authors/<int:author_id>/edit/', views.admin_edit_author, name='admin_edit_author'),
    path('admin/authors/<int:author_id>/delete/', views.admin_delete_author, name='admin_delete_author'),
    path('admin/authors/<int:author_id>/restore/', views.admin_restore_author, name='admin_restore_author'),
]
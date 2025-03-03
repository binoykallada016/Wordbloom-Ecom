from django.urls import path
from . import views

app_name = 'category'

urlpatterns = [
    path('category-list/', views.category_list, name='category_list'),
    path('category-add/', views.add_category, name='add_category'),
    path('category-edit/<int:category_id>/', views.edit_category, name='edit_category'),
    path('category-delete/<int:category_id>/', views.delete_category, name='delete_category'),
    path('category-offer-add/<int:category_id>/', views.add_category_offer, name='add_category_offer'),
]

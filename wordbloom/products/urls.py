from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    
    path('admin/products/', views.admin_product_list, name='admin_product_list'),
    path('admin/products/add/', views.admin_product_add, name='admin_product_add'),
    path('admin/products/<int:product_id>/edit/', views.admin_product_edit, name='admin_product_edit'),
    path('admin/products/<int:product_id>/view/', views.admin_product_view, name='admin_product_view'),
    path('admin/products/<int:product_id>/delete/', views.admin_product_delete, name='admin_product_delete'),

    # Orders
    # path('orders_list/',views.admin_orders_list, name = 'admin_orders_list'),
    # path('orders_view_details/',views.admin_orders_view_details, name = 'admin_orders_view_details')
]

from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('place-order/', views.place_order, name='place-order'),
    path('order-confirmation/<str:order_id>/', views.order_confirmation, name='order-confirmation'),
    path('order-failure/<str:order_id>/', views.order_failure, name='order-failure'),
    path('admin/orders/', views.admin_order_list, name='admin-order-list'),
    path('admin/orders/<int:order_id>/', views.admin_order_detail, name='admin-order-detail'),
    path('admin/return-orders/', views.admin_return_orders, name='admin-return-orders'),    
    path('return-request/<str:order_id>/', views.return_request, name='return-request'),
    path('admin/change-order-status/<int:order_id>/', views.change_order_status, name='change_order_status'),
    path('razorpay-callback/', views.razorpay_callback, name='razorpay-callback'),
    path('retry-payment/<str:order_id>/', views.retry_payment, name='retry-payment'),
    # path('admin/approve-return/<int:order_id>/', views.approve_return, name='approve_return'),
    # path('admin/reject-return/<int:order_id>/', views.reject_return, name='reject_return'),
    path('admin/approve-return/<int:return_request_id>/', views.approve_return, name='approve_return'),
    path('admin/reject-return/<int:return_request_id>/', views.reject_return, name='reject_return'),
]
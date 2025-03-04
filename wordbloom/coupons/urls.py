from django.urls import path
from . import views

app_name = 'coupons'

urlpatterns = [
    path('', views.list_coupon, name='list-coupon'),
    path('create/', views.create_coupon, name='create-coupon'),
    path('edit/<int:pk>/', views.edit_coupon, name='edit_coupon'),
    path('status/<int:pk>/', views.coupon_status, name='coupon_status'),
    path('generate-code/', views.generate_coupon_code, name='generate_coupon_code'),
    path('apply/', views.apply_coupon, name='apply_coupon'),
    path('remove/', views.remove_coupon, name='remove_coupon'),
]
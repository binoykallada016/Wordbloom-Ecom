from django.urls import path
from . import views
app_name = 'accounts'

urlpatterns = [
    path('',views.home,name="home"),    
    path('register/', views.user_register, name='user_register'),
    path('otp_verification/',views.verify_otp, name = 'verify_otp'),
    path('resend_otp/', views.resend_otp, name = 'resend_otp'),    
    path('shop/', views.shop, name='shop'),
    path('product/<int:product_id>/', views.product_detail, name='product_detail'),
    path('category/',views.category, name = 'category'),
    path('authors/',views.authors, name = 'authors'),
    path('contact/', views.contact, name = 'contact'),
    path('about/', views.aboutus, name = 'aboutus'),
    path('login/', views.user_login, name = 'user_login'),
    path('reset_password/', views.forgot_password, name = 'forgot_password'),
    path('logout/', views.user_logout, name = 'logout'),
]
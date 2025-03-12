from django.urls import path, reverse_lazy
from . import views
from django.contrib.auth import views as auth_views
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
    # path('reset_password/', views.forgot_password, name = 'forgot_password'),
    path('logout/', views.user_logout, name = 'logout'),

    # Password reset URLs (using Django's built-in views)
    path('password_reset/', auth_views.PasswordResetView.as_view(
        template_name='userside/account/registration/password_reset_form.html',
        email_template_name='userside/account/registration/password_reset_email.html',
        subject_template_name='userside/account/registration/password_reset_subject.txt',
        success_url=reverse_lazy('accounts:password_reset_done')  # Use reverse_lazy
    ), name='password_reset'),

    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='userside/account/registration/password_reset_done.html'
    ), name='password_reset_done'),

    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='userside/account/registration/password_reset_confirm.html',
        success_url=reverse_lazy('accounts:password_reset_complete')  # Fix success_url
    ), name='password_reset_confirm'),

    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='userside/account/registration/password_reset_complete.html'
    ), name='password_reset_complete'),
]
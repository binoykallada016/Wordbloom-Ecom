from django.urls import path
from . import views
app_name='admindashboard'

urlpatterns = [
    # path('',views.admindashboard,name="admin_home"),
    path('',views.admin_login, name='admin_login'),
    path('admin-dashboard/',views.admin_dashboard, name='admin_dashboard'),
    path('admin-logout/',views.admin_logout,name='admin-logout'),
    # path('admin-user/', views.admin_user, name = 'admin_user'),
    path('users/', views.list_users, name='list_users'),
    path('users/block/<int:user_id>/', views.block_user, name='block_user'),
    path('users/unblock/<int:user_id>/', views.unblock_user, name='unblock_user'),
    path('sales-report/',views.sales_report, name = 'sales_report')
]
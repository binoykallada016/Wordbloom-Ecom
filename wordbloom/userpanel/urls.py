from django.urls import path
from . import views

app_name = 'userpanel'

urlpatterns = [
    path('profile/', views.profile, name='profile'),
    path('edit-profile/', views.edit_profile, name='edit_profile'),
    path('change-password/', views.change_password, name='change_password'),
    path('addresses/', views.manage_addresses, name='manage_addresses'),
    path('add-address/', views.add_address, name='add_address'),
    path('edit-address/<int:address_id>/', views.edit_address, name='edit_address'),
    path('delete-address/<int:address_id>/', views.delete_address, name='delete_address'),
    path('orders/', views.order_list, name='order_list'),
    path('order-detail/<str:order_id>/', views.user_order_detail, name='user_order_detail'),
    path('wishlist/', views.wishlist, name='wishlist'),
    path('remove-from-wishlist/', views.remove_from_wishlist, name='remove_from_wishlist'),
    path('add-to-wishlist/<int:product_id>/', views.add_to_wishlist, name='add_to_wishlist'),
    path('cancel-order/<str:order_id>/', views.cancel_order, name='cancel_order'),
    path('cancel-order-item/<str:item_id>/', views.cancel_item, name='cancel_item'),
    path('wallet/', views.wallet_view, name='wallet'),
    path('wallet/add-funds/', views.add_funds, name='add_funds'),
    path('wallet/refund/<int:order_id>/', views.refund_to_wallet, name='refund_to_wallet'),
    path('invoice/<str:order_id>/', views.generate_invoice, name = 'generate_invoice'),
]
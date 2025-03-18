from django.urls import path
from . import views

app_name = 'cart'

urlpatterns = [
    path('', views.cart_view, name='cart-view'),
    path('add/', views.add_to_cart, name='add-to-cart'),
    path('remove/<int:item_id>/', views.remove_item, name='remove-item'),
    # path('update/', views.update_cart_quantity, name='update-cart-quantity'),
    path('update-quantity/', views.update_cart_quantity, name='update-quantity'),
    path('checkout/', views.checkout, name='checkout'),
    path('add-address/', views.add_address, name='add-address'),
]
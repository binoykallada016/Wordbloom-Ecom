# from .models import CartItem
# from coupon.models import Coupon

# def cart_total(request):
#     total = 0
#     if request.user.is_authenticated:
#         cart_items = CartItem.objects.filter(cart__user=request.user)
#         for item in cart_items:
#             total += item.sub_total()

#         coupon_code = request.session.get('coupon_code')
#         if coupon_code:
#             try:
#                 coupon = Coupon.objects.get(code__iexact=coupon_code)
#                 total = total - (total * coupon.discount / 100)
#             except Coupon.DoesNotExist:
#                 pass

#     return {'cart_total': total}
from django.urls import path
from . import template_views

app_name = 'orders'

urlpatterns = [
    path('checkout/', template_views.checkout_view, name='checkout'),
    path('thanks/<int:order_id>/', template_views.thanks_view, name='thanks'),
    path('cart/partial/', template_views.cart_partial, name='cart-partial'),
    path('cart/widget/', template_views.cart_widget, name='cart-widget'),
    path('cart/add/<int:product_id>/', template_views.cart_add_htmx, name='cart-add-htmx'),
    path('cart/remove/<int:product_id>/', template_views.cart_remove_htmx, name='cart-remove-htmx'),
    path('cart/update/<int:product_id>/', template_views.cart_update_htmx, name='cart-update-htmx'),
]

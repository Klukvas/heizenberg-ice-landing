from django.urls import path
from .views import CartView, CartAddView, CartUpdateView, CartRemoveView, OrderCreateView
from .webhook_views import MonobankWebhookView

urlpatterns = [
    path('cart/', CartView.as_view(), name='api-cart'),
    path('cart/add/', CartAddView.as_view(), name='api-cart-add'),
    path('cart/update/', CartUpdateView.as_view(), name='api-cart-update'),
    path('cart/remove/', CartRemoveView.as_view(), name='api-cart-remove'),
    path('orders/create/', OrderCreateView.as_view(), name='api-order-create'),
    path('monobank/webhook/', MonobankWebhookView.as_view(), name='monobank-webhook'),
]

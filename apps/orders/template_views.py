from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseBadRequest
from django.template.loader import render_to_string
from django.db import transaction
from django.views.decorators.http import require_POST
from apps.catalog.models import Product
from apps.delivery.models import DeliveryZone
from apps.pages.models import SiteSettings
from .cart import Cart
from .models import Order, OrderItem, normalize_phone, phone_validator


def checkout_view(request):
    cart = Cart(request)
    if cart.get_count() == 0:
        return redirect('pages:index')

    zones = DeliveryZone.objects.filter(is_active=True)
    settings = SiteSettings.load()

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        delivery_type = request.POST.get('delivery_type', 'pickup')
        address = request.POST.get('address', '').strip()
        zone_id = request.POST.get('zone_id')
        payment_method = request.POST.get('payment_method', 'cash')
        comment = request.POST.get('comment', '').strip()

        valid_delivery_types = [c[0] for c in Order.DELIVERY_CHOICES]
        valid_payment_methods = [c[0] for c in Order.PAYMENT_CHOICES]

        errors = {}
        if not name:
            errors['name'] = "Вкажіть ім'я"
        if not phone:
            errors['phone'] = 'Вкажіть телефон'
        else:
            phone = normalize_phone(phone)
            try:
                phone_validator(phone)
            except ValidationError:
                errors['phone'] = 'Невірний формат. Використовуйте +380XXXXXXXXX або 0XXXXXXXXX'
        if delivery_type not in valid_delivery_types:
            errors['delivery_type'] = 'Невірний тип доставки'
        if payment_method not in valid_payment_methods:
            errors['payment_method'] = 'Невірний спосіб оплати'

        zone = None
        delivery_price = 0
        if delivery_type == 'delivery':
            if not address:
                errors['address'] = 'Вкажіть адресу доставки'
            if zone_id:
                try:
                    zone = DeliveryZone.objects.get(id=zone_id, is_active=True)
                    delivery_price = zone.delivery_price
                    if cart.get_total() < zone.min_order_amount:
                        errors['min_order'] = f'Мінімальна сума замовлення: {zone.min_order_amount} ₴'
                except DeliveryZone.DoesNotExist:
                    errors['zone'] = 'Зону не знайдено'

        if errors:
            return render(request, 'pages/checkout.html', {
                'cart': cart,
                'cart_items': cart.get_items(),
                'zones': zones,
                'settings': settings,
                'errors': errors,
                'form_data': request.POST,
            })

        if not request.session.session_key:
            request.session.create()

        cart_items = cart.get_items()
        total_price = sum(item['price'] * item['quantity'] for item in cart_items)

        with transaction.atomic():
            order = Order.objects.create(
                session_key=request.session.session_key,
                name=name,
                phone=phone,
                email=email,
                delivery_type=delivery_type,
                address=address,
                zone=zone,
                payment_method=payment_method,
                total_price=total_price,
                delivery_price=delivery_price,
                comment=comment,
            )

            order_items = [
                OrderItem(
                    order=order,
                    product=item['product'],
                    quantity=item['quantity'],
                    price=item['price'],
                )
                for item in cart_items
            ]
            OrderItem.objects.bulk_create(order_items)

        # Handle payment
        if order.payment_method == 'monobank':
            from .monobank import create_invoice
            base_url = request.build_absolute_uri('/')[:-1]
            result = create_invoice(order, base_url)
            if result:
                order.monobank_invoice_id = result['invoice_id']
                order.save(update_fields=['monobank_invoice_id'])
                cart.clear()
                return redirect(result['page_url'])
            else:
                # Monobank unavailable — delete order, keep cart, show error
                order.delete()
                return render(request, 'pages/checkout.html', {
                    'cart': cart,
                    'cart_items': cart.get_items(),
                    'zones': zones,
                    'settings': settings,
                    'errors': {'payment': 'Платіжний сервіс тимчасово недоступний. Спробуйте пізніше або оберіть оплату готівкою.'},
                    'form_data': request.POST,
                })

        cart.clear()
        return redirect('orders:thanks', order_id=order.id)

    return render(request, 'pages/checkout.html', {
        'cart': cart,
        'cart_items': cart.get_items(),
        'zones': zones,
        'settings': settings,
    })


def thanks_view(request, order_id):
    if not request.session.session_key:
        return redirect('pages:index')
    order = get_object_or_404(Order, id=order_id, session_key=request.session.session_key)
    settings = SiteSettings.load()
    return render(request, 'pages/thanks.html', {
        'order': order,
        'order_items': order.items.select_related('product').all(),
        'settings': settings,
    })


def cart_partial(request):
    cart = Cart(request)
    return render(request, 'partials/cart_dropdown.html', {
        'cart': cart,
        'cart_items': cart.get_items(),
    })


def cart_widget(request):
    cart = Cart(request)
    return render(request, 'partials/cart_widget.html', {
        'cart': cart,
    })


@require_POST
def cart_add_htmx(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_available=True)
    cart = Cart(request)
    cart.add(product, 1)

    html = render_to_string('partials/cart_widget.html', {'cart': cart}, request=request)
    response = HttpResponse(html)
    response['HX-Trigger'] = 'cartUpdated'
    return response


@require_POST
def cart_remove_htmx(request, product_id):
    cart = Cart(request)
    cart.remove(product_id)

    response = render(request, 'partials/cart_dropdown.html', {
        'cart': cart,
        'cart_items': cart.get_items(),
    })
    response['HX-Trigger'] = 'cartUpdated'
    return response


@require_POST
def cart_update_htmx(request, product_id):
    try:
        quantity = int(request.POST.get('quantity', 1))
    except (ValueError, TypeError):
        return HttpResponseBadRequest('Invalid quantity')
    cart = Cart(request)
    cart.update_quantity(product_id, quantity)

    response = render(request, 'partials/cart_dropdown.html', {
        'cart': cart,
        'cart_items': cart.get_items(),
    })
    response['HX-Trigger'] = 'cartUpdated'
    return response

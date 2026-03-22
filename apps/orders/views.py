from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction
from apps.catalog.models import Product
from apps.delivery.models import DeliveryZone
from .models import Order, OrderItem
from .cart import Cart
from .serializers import OrderCreateSerializer


class CartView(APIView):
    def get(self, request):
        cart = Cart(request)
        items = []
        for item in cart.get_items():
            product = item['product']
            items.append({
                'product_id': product.id,
                'name': product.name,
                'price': str(item['price']),
                'quantity': item['quantity'],
                'subtotal': str(item['subtotal']),
                'image': product.image.url if product.image else '',
                'weight_kg': str(product.weight_kg),
            })
        return Response({
            'items': items,
            'total': str(cart.get_total()),
            'count': cart.get_count(),
        })


class CartAddView(APIView):
    def post(self, request):
        product_id = request.data.get('product_id')
        try:
            quantity = int(request.data.get('quantity', 1))
        except (ValueError, TypeError):
            return Response(
                {'error': 'Невірна кількість'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            product = Product.objects.get(id=product_id, is_available=True)
        except Product.DoesNotExist:
            return Response(
                {'error': 'Товар не знайдено'},
                status=status.HTTP_404_NOT_FOUND
            )

        cart = Cart(request)
        cart.add(product, quantity)
        return Response({
            'count': cart.get_count(),
            'total': str(cart.get_total()),
        })


class CartUpdateView(APIView):
    def post(self, request):
        product_id = request.data.get('product_id')
        if product_id is None or not str(product_id).isdigit():
            return Response(
                {'error': 'Невірний product_id'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            quantity = int(request.data.get('quantity', 1))
        except (ValueError, TypeError):
            return Response(
                {'error': 'Невірна кількість'},
                status=status.HTTP_400_BAD_REQUEST
            )

        cart = Cart(request)
        cart.update_quantity(product_id, quantity)
        return Response({
            'count': cart.get_count(),
            'total': str(cart.get_total()),
        })


class CartRemoveView(APIView):
    def post(self, request):
        product_id = request.data.get('product_id')
        if product_id is None or not str(product_id).isdigit():
            return Response(
                {'error': 'Невірний product_id'},
                status=status.HTTP_400_BAD_REQUEST
            )
        cart = Cart(request)
        cart.remove(product_id)
        return Response({
            'count': cart.get_count(),
            'total': str(cart.get_total()),
        })


class OrderCreateView(APIView):
    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        cart = Cart(request)
        if cart.get_count() == 0:
            return Response(
                {'error': 'Кошик порожній'},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = serializer.validated_data
        delivery_price = 0
        zone = None

        if data['delivery_type'] == 'delivery':
            zone_id = data.get('zone_id')
            if zone_id:
                try:
                    zone = DeliveryZone.objects.get(id=zone_id, is_active=True)
                    delivery_price = zone.delivery_price
                    if cart.get_total() < zone.min_order_amount:
                        return Response(
                            {'error': f'Мінімальна сума замовлення для цієї зони: {zone.min_order_amount} ₴'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                except DeliveryZone.DoesNotExist:
                    return Response(
                        {'error': 'Зону доставки не знайдено'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

        if not request.session.session_key:
            request.session.create()

        cart_items = cart.get_items()
        total_price = sum(item['price'] * item['quantity'] for item in cart_items)

        with transaction.atomic():
            order = Order.objects.create(
                session_key=request.session.session_key,
                name=data['name'],
                phone=data['phone'],
                email=data.get('email', ''),
                delivery_type=data['delivery_type'],
                address=data.get('address', ''),
                zone=zone,
                payment_method=data['payment_method'],
                total_price=total_price,
                delivery_price=delivery_price,
                comment=data.get('comment', ''),
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

        cart.clear()

        return Response({
            'order_id': order.id,
            'total': str(order.total_price),
            'delivery_price': str(order.delivery_price),
            'grand_total': str(order.grand_total),
        }, status=status.HTTP_201_CREATED)

from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import TestCase, RequestFactory, override_settings
from rest_framework.test import APIRequestFactory, APIClient

from apps.catalog.models import Category, Product
from apps.delivery.models import DeliveryZone
from apps.orders.cart import Cart
from apps.orders.models import Order, OrderItem
from apps.orders.monobank import create_invoice, get_monobank_token


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_category(**kwargs):
    defaults = {'name': 'Ice Cream', 'slug': 'ice-cream'}
    defaults.update(kwargs)
    return Category.objects.create(**defaults)


def _create_product(category=None, **kwargs):
    if category is None:
        category = _create_category()
    defaults = {
        'name': 'Vanilla',
        'slug': 'vanilla',
        'price': Decimal('150.00'),
        'weight_kg': Decimal('0.50'),
        'category': category,
        'is_available': True,
    }
    defaults.update(kwargs)
    return Product.objects.create(**defaults)


def _create_delivery_zone(**kwargs):
    defaults = {
        'name': 'Centre',
        'delivery_price': Decimal('50.00'),
        'min_order_amount': Decimal('0.00'),
        'polygon': {'type': 'Polygon', 'coordinates': [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
        'is_active': True,
    }
    defaults.update(kwargs)
    return DeliveryZone.objects.create(**defaults)


def _build_request_with_session(method='get', path='/', data=None):
    """Return a Django request with a working session (not saved to DB)."""
    factory = RequestFactory()
    builder = getattr(factory, method)
    request = builder(path, data=data or {})
    middleware = SessionMiddleware(lambda req: None)
    middleware.process_request(request)
    request.session.save()
    return request


# =========================================================================
# 1. Cart unit tests
# =========================================================================

class CartAddTests(TestCase):
    def setUp(self):
        self.category = _create_category()
        self.product = _create_product(category=self.category)
        self.request = _build_request_with_session()

    def test_add_product_creates_entry(self):
        cart = Cart(self.request)
        cart.add(self.product, 1)

        self.assertIn(str(self.product.id), cart.cart)
        self.assertEqual(cart.cart[str(self.product.id)]['quantity'], 1)
        self.assertEqual(cart.cart[str(self.product.id)]['price'], str(self.product.price))

    def test_add_product_twice_increments_quantity(self):
        cart = Cart(self.request)
        cart.add(self.product, 1)
        cart.add(self.product, 2)

        self.assertEqual(cart.cart[str(self.product.id)]['quantity'], 3)

    def test_add_sets_session_modified(self):
        cart = Cart(self.request)
        cart.add(self.product, 1)

        self.assertTrue(self.request.session.modified)


class CartRemoveTests(TestCase):
    def setUp(self):
        self.category = _create_category()
        self.product = _create_product(category=self.category)
        self.request = _build_request_with_session()

    def test_remove_existing_product(self):
        cart = Cart(self.request)
        cart.add(self.product, 1)
        cart.remove(self.product.id)

        self.assertNotIn(str(self.product.id), cart.cart)

    def test_remove_nonexistent_product_is_noop(self):
        cart = Cart(self.request)
        cart.remove(999)

        self.assertEqual(len(cart.cart), 0)


class CartUpdateQuantityTests(TestCase):
    def setUp(self):
        self.category = _create_category()
        self.product = _create_product(category=self.category)
        self.request = _build_request_with_session()

    def test_update_quantity(self):
        cart = Cart(self.request)
        cart.add(self.product, 1)
        cart.update_quantity(self.product.id, 5)

        self.assertEqual(cart.cart[str(self.product.id)]['quantity'], 5)

    def test_update_quantity_to_zero_removes_item(self):
        cart = Cart(self.request)
        cart.add(self.product, 1)
        cart.update_quantity(self.product.id, 0)

        self.assertNotIn(str(self.product.id), cart.cart)

    def test_update_quantity_negative_removes_item(self):
        cart = Cart(self.request)
        cart.add(self.product, 1)
        cart.update_quantity(self.product.id, -1)

        self.assertNotIn(str(self.product.id), cart.cart)


class CartTotalAndCountTests(TestCase):
    def setUp(self):
        self.category = _create_category()
        self.p1 = _create_product(
            category=self.category,
            name='A',
            slug='a',
            price=Decimal('100.00'),
        )
        self.p2 = _create_product(
            category=self.category,
            name='B',
            slug='b',
            price=Decimal('200.00'),
        )
        self.request = _build_request_with_session()

    def test_get_total_empty_cart(self):
        cart = Cart(self.request)
        self.assertEqual(cart.get_total(), Decimal('0'))

    def test_get_total_with_items(self):
        cart = Cart(self.request)
        cart.add(self.p1, 2)
        cart.add(self.p2, 3)

        # 100*2 + 200*3 = 800
        self.assertEqual(cart.get_total(), Decimal('800.00'))

    def test_get_count_empty_cart(self):
        cart = Cart(self.request)
        self.assertEqual(cart.get_count(), 0)

    def test_get_count_with_items(self):
        cart = Cart(self.request)
        cart.add(self.p1, 2)
        cart.add(self.p2, 3)

        self.assertEqual(cart.get_count(), 5)

    def test_len_delegates_to_get_count(self):
        cart = Cart(self.request)
        cart.add(self.p1, 1)
        self.assertEqual(len(cart), 1)


class CartClearTests(TestCase):
    def setUp(self):
        self.category = _create_category()
        self.product = _create_product(category=self.category)
        self.request = _build_request_with_session()

    def test_clear_empties_cart(self):
        cart = Cart(self.request)
        cart.add(self.product, 3)
        cart.clear()

        self.assertEqual(len(cart.cart), 0)
        self.assertEqual(self.request.session['cart'], {})

    def test_clear_sets_session_modified(self):
        cart = Cart(self.request)
        cart.add(self.product, 1)
        self.request.session.modified = False
        cart.clear()

        self.assertTrue(self.request.session.modified)


class CartGetItemsTests(TestCase):
    def setUp(self):
        self.category = _create_category()
        self.product = _create_product(category=self.category)
        self.request = _build_request_with_session()

    def test_get_items_returns_correct_data(self):
        cart = Cart(self.request)
        cart.add(self.product, 2)

        items = cart.get_items()
        self.assertEqual(len(items), 1)

        item = items[0]
        self.assertEqual(item['product'], self.product)
        self.assertEqual(item['quantity'], 2)
        self.assertEqual(item['price'], self.product.price)
        self.assertEqual(item['subtotal'], self.product.price * 2)

    def test_get_items_empty_cart(self):
        cart = Cart(self.request)
        self.assertEqual(cart.get_items(), [])


class CartImmutabilityTests(TestCase):
    """Verify that Cart methods create new dicts instead of mutating in-place."""

    def setUp(self):
        self.category = _create_category()
        self.product = _create_product(category=self.category)
        self.request = _build_request_with_session()

    def test_add_creates_new_cart_dict(self):
        cart = Cart(self.request)
        original_cart = cart.cart
        cart.add(self.product, 1)

        # After add, cart.cart should be a NEW dict, not the same object
        self.assertIsNot(cart.cart, original_cart)

    def test_remove_creates_new_cart_dict(self):
        cart = Cart(self.request)
        cart.add(self.product, 1)
        cart_before_remove = cart.cart
        cart.remove(self.product.id)

        self.assertIsNot(cart.cart, cart_before_remove)

    def test_update_quantity_creates_new_cart_dict(self):
        cart = Cart(self.request)
        cart.add(self.product, 1)
        cart_before_update = cart.cart
        cart.update_quantity(self.product.id, 5)

        self.assertIsNot(cart.cart, cart_before_update)


# =========================================================================
# 2. Order model tests
# =========================================================================

class OrderModelTests(TestCase):
    def test_order_creation(self):
        order = Order.objects.create(
            session_key='test-session-key',
            name='John',
            phone='+380991234567',
            delivery_type='pickup',
            payment_method='cash',
            total_price=Decimal('300.00'),
        )
        self.assertEqual(order.status, 'new')
        self.assertFalse(order.is_paid)
        self.assertEqual(order.delivery_price, Decimal('0'))
        self.assertIsNotNone(order.created_at)

    def test_grand_total_property(self):
        order = Order.objects.create(
            session_key='key',
            name='User',
            phone='+380991234567',
            delivery_type='delivery',
            payment_method='cash',
            total_price=Decimal('500.00'),
            delivery_price=Decimal('50.00'),
        )
        self.assertEqual(order.grand_total, Decimal('550.00'))

    def test_grand_total_without_delivery(self):
        order = Order.objects.create(
            session_key='key',
            name='User',
            phone='+380991234567',
            delivery_type='pickup',
            payment_method='cash',
            total_price=Decimal('500.00'),
        )
        self.assertEqual(order.grand_total, Decimal('500.00'))

    def test_str_representation(self):
        order = Order.objects.create(
            session_key='key',
            name='User',
            phone='123',
            delivery_type='pickup',
            payment_method='cash',
            total_price=Decimal('100.00'),
        )
        self.assertEqual(str(order), f'Замовлення #{order.pk}')


# =========================================================================
# 3. OrderItem model tests
# =========================================================================

class OrderItemModelTests(TestCase):
    def setUp(self):
        self.category = _create_category()
        self.product = _create_product(category=self.category)
        self.order = Order.objects.create(
            session_key='key',
            name='User',
            phone='123',
            delivery_type='pickup',
            payment_method='cash',
            total_price=Decimal('300.00'),
        )

    def test_subtotal_property(self):
        item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=3,
            price=Decimal('100.00'),
        )
        self.assertEqual(item.subtotal, Decimal('300.00'))

    def test_str_representation(self):
        item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=2,
            price=Decimal('100.00'),
        )
        self.assertEqual(str(item), f'{self.product.name} x2')


# =========================================================================
# 4. Checkout view tests
# =========================================================================

@override_settings(ROOT_URLCONF='config.urls')
class CheckoutViewTests(TestCase):
    def setUp(self):
        self.category = _create_category()
        self.product = _create_product(category=self.category)
        from apps.pages.models import SiteSettings
        SiteSettings.load()

    def _add_to_session_cart(self, session, product, quantity=1):
        cart = session.get('cart', {})
        pid = str(product.id)
        new_cart = dict(cart)
        new_cart[pid] = {'quantity': quantity, 'price': str(product.price)}
        session['cart'] = new_cart
        session.save()

    def test_get_renders_form_when_cart_not_empty(self):
        session = self.client.session
        self._add_to_session_cart(session, self.product)
        session.save()
        self.client.cookies['sessionid'] = session.session_key

        response = self.client.get('/checkout/')
        self.assertEqual(response.status_code, 200)

    def test_get_redirects_when_cart_empty(self):
        response = self.client.get('/checkout/')
        self.assertEqual(response.status_code, 302)

    def test_post_with_valid_data_creates_order(self):
        session = self.client.session
        self._add_to_session_cart(session, self.product, 2)
        session.save()
        self.client.cookies['sessionid'] = session.session_key

        data = {
            'name': 'Test User',
            'phone': '+380991234567',
            'delivery_type': 'pickup',
            'payment_method': 'cash',
        }
        response = self.client.post('/checkout/', data)

        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.first()
        self.assertEqual(order.name, 'Test User')
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.total_price, self.product.price * 2)
        # Should redirect to thanks page
        self.assertEqual(response.status_code, 302)
        self.assertIn(f'/thanks/{order.id}/', response.url)

    def test_post_with_empty_cart_redirects(self):
        data = {
            'name': 'Test User',
            'phone': '+380991234567',
            'delivery_type': 'pickup',
            'payment_method': 'cash',
        }
        response = self.client.post('/checkout/', data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.count(), 0)

    def test_post_with_invalid_delivery_type_shows_error(self):
        session = self.client.session
        self._add_to_session_cart(session, self.product)
        session.save()
        self.client.cookies['sessionid'] = session.session_key

        data = {
            'name': 'Test User',
            'phone': '+380991234567',
            'delivery_type': 'teleport',
            'payment_method': 'cash',
        }
        response = self.client.post('/checkout/', data)

        self.assertEqual(response.status_code, 200)
        self.assertIn('errors', response.context)
        self.assertIn('delivery_type', response.context['errors'])
        self.assertEqual(Order.objects.count(), 0)

    def test_post_validates_required_name(self):
        session = self.client.session
        self._add_to_session_cart(session, self.product)
        session.save()
        self.client.cookies['sessionid'] = session.session_key

        data = {
            'name': '',
            'phone': '+380991234567',
            'delivery_type': 'pickup',
            'payment_method': 'cash',
        }
        response = self.client.post('/checkout/', data)

        self.assertEqual(response.status_code, 200)
        self.assertIn('name', response.context['errors'])

    def test_post_validates_required_phone(self):
        session = self.client.session
        self._add_to_session_cart(session, self.product)
        session.save()
        self.client.cookies['sessionid'] = session.session_key

        data = {
            'name': 'Test',
            'phone': '',
            'delivery_type': 'pickup',
            'payment_method': 'cash',
        }
        response = self.client.post('/checkout/', data)

        self.assertEqual(response.status_code, 200)
        self.assertIn('phone', response.context['errors'])

    def test_post_clears_cart_after_order(self):
        session = self.client.session
        self._add_to_session_cart(session, self.product, 1)
        session.save()
        self.client.cookies['sessionid'] = session.session_key

        data = {
            'name': 'Test',
            'phone': '+380991234567',
            'delivery_type': 'pickup',
            'payment_method': 'cash',
        }
        self.client.post('/checkout/', data)

        # Reload session
        updated_session = self.client.session
        self.assertEqual(updated_session.get('cart', {}), {})


# =========================================================================
# 5. Thanks view tests
# =========================================================================

@override_settings(ROOT_URLCONF='config.urls')
class ThanksViewTests(TestCase):
    def setUp(self):
        from apps.pages.models import SiteSettings
        SiteSettings.load()

    def test_thanks_accessible_with_correct_session(self):
        # Create a session and order with matching session_key
        session = self.client.session
        session.create()
        session_key = session.session_key

        order = Order.objects.create(
            session_key=session_key,
            name='User',
            phone='123',
            delivery_type='pickup',
            payment_method='cash',
            total_price=Decimal('100.00'),
        )

        self.client.cookies['sessionid'] = session_key
        response = self.client.get(f'/thanks/{order.id}/')
        self.assertEqual(response.status_code, 200)

    def test_thanks_redirects_if_no_session(self):
        order = Order.objects.create(
            session_key='some-other-session',
            name='User',
            phone='123',
            delivery_type='pickup',
            payment_method='cash',
            total_price=Decimal('100.00'),
        )
        response = self.client.get(f'/thanks/{order.id}/')
        # Should either redirect or return 404 (session mismatch)
        self.assertIn(response.status_code, [302, 404])

    def test_thanks_404_for_wrong_session(self):
        session = self.client.session
        session.create()
        self.client.cookies['sessionid'] = session.session_key

        order = Order.objects.create(
            session_key='different-session-key',
            name='User',
            phone='123',
            delivery_type='pickup',
            payment_method='cash',
            total_price=Decimal('100.00'),
        )
        response = self.client.get(f'/thanks/{order.id}/')
        self.assertEqual(response.status_code, 404)


# =========================================================================
# 6. Cart HTMX views tests
# =========================================================================

@override_settings(ROOT_URLCONF='config.urls')
class CartHTMXViewTests(TestCase):
    def setUp(self):
        self.category = _create_category()
        self.product = _create_product(category=self.category)

    def test_cart_add_htmx_post_creates_cart_entry(self):
        response = self.client.post(f'/cart/add/{self.product.id}/')
        self.assertEqual(response.status_code, 200)

        session = self.client.session
        cart = session.get('cart', {})
        self.assertIn(str(self.product.id), cart)
        self.assertEqual(cart[str(self.product.id)]['quantity'], 1)

    def test_cart_add_htmx_sets_hx_trigger(self):
        response = self.client.post(f'/cart/add/{self.product.id}/')
        self.assertEqual(response['HX-Trigger'], 'cartUpdated')

    def test_cart_add_htmx_get_returns_405(self):
        response = self.client.get(f'/cart/add/{self.product.id}/')
        self.assertEqual(response.status_code, 405)

    def test_cart_remove_htmx_removes_item(self):
        # First add the product
        self.client.post(f'/cart/add/{self.product.id}/')

        # Then remove it
        response = self.client.post(f'/cart/remove/{self.product.id}/')
        self.assertEqual(response.status_code, 200)

        session = self.client.session
        cart = session.get('cart', {})
        self.assertNotIn(str(self.product.id), cart)

    def test_cart_remove_htmx_get_returns_405(self):
        response = self.client.get(f'/cart/remove/{self.product.id}/')
        self.assertEqual(response.status_code, 405)

    def test_cart_add_htmx_nonexistent_product_returns_404(self):
        response = self.client.post('/cart/add/99999/')
        self.assertEqual(response.status_code, 404)

    def test_cart_add_htmx_unavailable_product_returns_404(self):
        self.product.is_available = False
        self.product.save()
        response = self.client.post(f'/cart/add/{self.product.id}/')
        self.assertEqual(response.status_code, 404)


# =========================================================================
# 7. API CartAddView tests
# =========================================================================

@override_settings(ROOT_URLCONF='config.urls')
class APICartAddViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.category = _create_category()
        self.product = _create_product(category=self.category)

    def test_add_product_returns_count_and_total(self):
        response = self.client.post(
            '/api/cart/add/',
            {'product_id': self.product.id, 'quantity': 2},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(response.data['total'], str(self.product.price * 2))

    def test_add_nonexistent_product_returns_404(self):
        response = self.client.post(
            '/api/cart/add/',
            {'product_id': 99999, 'quantity': 1},
            format='json',
        )
        self.assertEqual(response.status_code, 404)

    def test_add_invalid_quantity_returns_400(self):
        response = self.client.post(
            '/api/cart/add/',
            {'product_id': self.product.id, 'quantity': 'abc'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_add_accumulates_quantity(self):
        self.client.post(
            '/api/cart/add/',
            {'product_id': self.product.id, 'quantity': 1},
            format='json',
        )
        response = self.client.post(
            '/api/cart/add/',
            {'product_id': self.product.id, 'quantity': 3},
            format='json',
        )
        self.assertEqual(response.data['count'], 4)


# =========================================================================
# 8. API OrderCreateView tests
# =========================================================================

@override_settings(ROOT_URLCONF='config.urls')
class APIOrderCreateViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.category = _create_category()
        self.product = _create_product(category=self.category)

    def _add_product_to_api_cart(self):
        self.client.post(
            '/api/cart/add/',
            {'product_id': self.product.id, 'quantity': 2},
            format='json',
        )

    def test_create_order_with_valid_data(self):
        self._add_product_to_api_cart()

        data = {
            'name': 'Test User',
            'phone': '+380991234567',
            'delivery_type': 'pickup',
            'payment_method': 'cash',
        }
        response = self.client.post('/api/orders/create/', data, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertIn('order_id', response.data)
        self.assertEqual(response.data['total'], str(self.product.price * 2))

        created_order = Order.objects.get(id=response.data['order_id'])
        self.assertEqual(Decimal(response.data['delivery_price']), Decimal('0'))
        self.assertEqual(created_order.items.count(), 1)

    def test_create_order_empty_cart_returns_400(self):
        data = {
            'name': 'Test User',
            'phone': '+380991234567',
            'delivery_type': 'pickup',
            'payment_method': 'cash',
        }
        response = self.client.post('/api/orders/create/', data, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.data)

    def test_create_order_missing_required_fields(self):
        self._add_product_to_api_cart()

        response = self.client.post('/api/orders/create/', {}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_create_order_invalid_delivery_type(self):
        self._add_product_to_api_cart()

        data = {
            'name': 'Test',
            'phone': '123',
            'delivery_type': 'drone',
            'payment_method': 'cash',
        }
        response = self.client.post('/api/orders/create/', data, format='json')
        self.assertEqual(response.status_code, 400)

    def test_create_order_clears_cart(self):
        self._add_product_to_api_cart()

        data = {
            'name': 'Test',
            'phone': '123',
            'delivery_type': 'pickup',
            'payment_method': 'cash',
        }
        self.client.post('/api/orders/create/', data, format='json')

        # Verify cart is now empty
        response = self.client.get('/api/cart/')
        self.assertEqual(response.data['count'], 0)


# =========================================================================
# 9. MonobankWebhookView tests
# =========================================================================

@override_settings(ROOT_URLCONF='config.urls')
class MonobankWebhookViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.order = Order.objects.create(
            session_key='test-key',
            name='User',
            phone='123',
            delivery_type='pickup',
            payment_method='monobank',
            total_price=Decimal('500.00'),
            monobank_invoice_id='test-invoice-123',
        )

    @patch('apps.orders.webhook_views._verify_webhook_signature', return_value=True)
    def test_post_with_unknown_invoice_returns_200(self, mock_sig):
        response = self.client.post(
            '/api/monobank/webhook/',
            {'invoiceId': 'unknown-invoice', 'status': 'success'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)

    def test_post_without_signature_returns_400(self):
        response = self.client.post(
            '/api/monobank/webhook/',
            {'invoiceId': 'test', 'status': 'success'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    @patch('apps.orders.webhook_views._verify_webhook_signature', return_value=True)
    def test_post_without_invoice_id_returns_400(self, mock_sig):
        response = self.client.post(
            '/api/monobank/webhook/',
            {'status': 'success'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    @patch('apps.orders.webhook_views._verify_webhook_signature', return_value=True)
    @patch('apps.orders.webhook_views.verify_invoice_status')
    def test_webhook_marks_order_paid_on_success(self, mock_verify, mock_sig):
        mock_verify.return_value = 'success'

        response = self.client.post(
            '/api/monobank/webhook/',
            {'invoiceId': 'test-invoice-123', 'status': 'success'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)

        self.order.refresh_from_db()
        self.assertTrue(self.order.is_paid)
        self.assertEqual(self.order.status, 'confirmed')

    @patch('apps.orders.webhook_views._verify_webhook_signature', return_value=True)
    @patch('apps.orders.webhook_views.verify_invoice_status')
    def test_webhook_does_not_downgrade_status(self, mock_verify, mock_sig):
        mock_verify.return_value = 'success'
        self.order.status = 'delivering'
        self.order.save()

        self.client.post(
            '/api/monobank/webhook/',
            {'invoiceId': 'test-invoice-123', 'status': 'success'},
            format='json',
        )

        self.order.refresh_from_db()
        self.assertTrue(self.order.is_paid)
        self.assertEqual(self.order.status, 'delivering')

    @patch('apps.orders.webhook_views._verify_webhook_signature', return_value=True)
    @patch('apps.orders.webhook_views.verify_invoice_status')
    def test_webhook_failure_does_not_mark_paid(self, mock_verify, mock_sig):
        mock_verify.return_value = 'failure'

        self.client.post(
            '/api/monobank/webhook/',
            {'invoiceId': 'test-invoice-123', 'status': 'failure'},
            format='json',
        )

        self.order.refresh_from_db()
        self.assertFalse(self.order.is_paid)
        self.assertEqual(self.order.status, 'new')

    @patch('apps.orders.webhook_views._verify_webhook_signature', return_value=True)
    @patch('apps.orders.webhook_views.verify_invoice_status')
    def test_webhook_idempotent_for_already_paid(self, mock_verify, mock_sig):
        mock_verify.return_value = 'success'
        self.order.is_paid = True
        self.order.status = 'confirmed'
        self.order.save()

        response = self.client.post(
            '/api/monobank/webhook/',
            {'invoiceId': 'test-invoice-123', 'status': 'success'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)

        self.order.refresh_from_db()
        self.assertTrue(self.order.is_paid)


# =========================================================================
# 10. Monobank service tests
# =========================================================================

class MonobankGetTokenTests(TestCase):
    @override_settings(MONOBANK_TOKEN='test-token-xyz')
    def test_get_monobank_token_returns_configured_value(self):
        self.assertEqual(get_monobank_token(), 'test-token-xyz')

    @override_settings(MONOBANK_TOKEN='')
    def test_get_monobank_token_returns_empty_when_not_set(self):
        self.assertEqual(get_monobank_token(), '')

    def test_get_monobank_token_returns_empty_when_attr_missing(self):
        with self.settings(MONOBANK_TOKEN=None):
            self.assertEqual(get_monobank_token(), '')


class MonobankCreateInvoiceTests(TestCase):
    def setUp(self):
        self.category = _create_category()
        self.product = _create_product(category=self.category)
        self.order = Order.objects.create(
            session_key='key',
            name='User',
            phone='123',
            delivery_type='pickup',
            payment_method='monobank',
            total_price=Decimal('300.00'),
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=2,
            price=Decimal('150.00'),
        )

    @override_settings(MONOBANK_TOKEN='')
    def test_create_invoice_returns_none_when_no_token(self):
        result = create_invoice(self.order, 'https://example.com')
        self.assertIsNone(result)

    @override_settings(MONOBANK_TOKEN='valid-token')
    @patch('apps.orders.monobank.requests.post')
    def test_create_invoice_returns_data_on_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'invoiceId': 'inv-abc',
            'pageUrl': 'https://pay.mono/inv-abc',
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = create_invoice(self.order, 'https://example.com')

        self.assertIsNotNone(result)
        self.assertEqual(result['invoice_id'], 'inv-abc')
        self.assertEqual(result['page_url'], 'https://pay.mono/inv-abc')

        # Verify request was made with correct data
        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get('json') or call_kwargs[1].get('json')
        self.assertEqual(payload['amount'], 30000)  # 300.00 * 100
        self.assertEqual(payload['ccy'], 980)

    @override_settings(MONOBANK_TOKEN='valid-token')
    @patch('apps.orders.monobank.requests.post')
    def test_create_invoice_returns_none_on_request_error(self, mock_post):
        import requests as req_lib
        mock_post.side_effect = req_lib.exceptions.ConnectionError('timeout')

        result = create_invoice(self.order, 'https://example.com')
        self.assertIsNone(result)

    @override_settings(MONOBANK_TOKEN='valid-token')
    @patch('apps.orders.monobank.requests.post')
    def test_create_invoice_includes_delivery_in_basket(self, mock_post):
        self.order.delivery_price = Decimal('50.00')
        self.order.save()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            'invoiceId': 'inv-xyz',
            'pageUrl': 'https://pay.mono/inv-xyz',
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = create_invoice(self.order, 'https://example.com')

        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get('json') or call_kwargs[1].get('json')
        basket = payload['merchantPaymInfo']['basketOrder']
        # Should have product item + delivery item
        self.assertEqual(len(basket), 2)
        delivery_item = basket[-1]
        self.assertEqual(delivery_item['name'], 'Доставка')
        self.assertEqual(delivery_item['sum'], 5000)  # 50.00 * 100

"""
Test Monobank Acquiring integration.

Usage:
    python manage.py test_monobank              # check token + create test invoice
    python manage.py test_monobank --check INV  # check invoice status by ID
"""
import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.orders.monobank import (
    create_invoice,
    get_monobank_token,
    verify_invoice_status,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Test Monobank Acquiring API integration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check',
            type=str,
            help='Check status of an existing invoice by ID',
        )
        parser.add_argument(
            '--url',
            type=str,
            default='https://example.com',
            help='Base URL for redirect/webhook (default: https://example.com)',
        )

    def handle(self, *args, **options):
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write('  Monobank Acquiring — Integration Test')
        self.stdout.write('=' * 50 + '\n')

        # Step 1: Check token
        token = get_monobank_token()
        if not token:
            self.stdout.write(self.style.ERROR(
                'MONOBANK_TOKEN не налаштовано!\n\n'
                'Кроки:\n'
                '1. Відкрийте https://web.monobank.ua\n'
                '2. Перейдіть: Підприємець → Еквайринг → API\n'
                '3. Скопіюйте токен мерчанта\n'
                '4. Додайте в .env:\n'
                '   MONOBANK_TOKEN=ваш-токен\n'
                '5. Перезапустіть сервер\n'
            ))
            return

        masked_token = token[:8] + '...' + token[-4:] if len(token) > 12 else '***'
        self.stdout.write(self.style.SUCCESS(f'Token: {masked_token}'))

        # Step 2: Check existing invoice
        if options['check']:
            self._check_invoice(options['check'])
            return

        # Step 3: Create test invoice
        self._create_test_invoice(options['url'])

    def _check_invoice(self, invoice_id):
        self.stdout.write(f'\nChecking invoice: {invoice_id}')

        status = verify_invoice_status(invoice_id)
        if status is None:
            self.stdout.write(self.style.ERROR('Failed to check status'))
        else:
            color = {
                'success': self.style.SUCCESS,
                'created': self.style.WARNING,
                'processing': self.style.WARNING,
                'hold': self.style.WARNING,
                'failure': self.style.ERROR,
                'reversed': self.style.ERROR,
                'expired': self.style.ERROR,
            }.get(status, self.style.NOTICE)

            self.stdout.write(color(f'Status: {status}'))

    def _create_test_invoice(self, base_url):
        from apps.catalog.models import Category, Product
        from apps.orders.models import Order, OrderItem

        self.stdout.write('\nCreating test invoice (1.00 ₴)...\n')

        # Create minimal test order
        category, _ = Category.objects.get_or_create(
            slug='test',
            defaults={'name': 'Test', 'order': 999},
        )
        product, _ = Product.objects.get_or_create(
            slug='monobank-test',
            defaults={
                'name': 'Тестовий товар',
                'price': 1,
                'weight_kg': 1,
                'category': category,
                'is_available': False,
            },
        )

        order = Order.objects.create(
            session_key='test-monobank',
            name='Test Monobank',
            phone='+380000000000',
            delivery_type='pickup',
            payment_method='monobank',
            total_price=1,
            delivery_price=0,
            comment='Integration test — можна скасувати',
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=1,
            price=1,
        )

        result = create_invoice(order, base_url)

        if result is None:
            self.stdout.write(self.style.ERROR(
                'Failed to create invoice!\n'
                'Перевірте:\n'
                '- Чи правильний токен?\n'
                '- Чи активний еквайринг у кабінеті Monobank?\n'
                '- Деталі помилки в логах (--verbosity=2)\n'
            ))
            order.delete()
            return

        order.monobank_invoice_id = result['invoice_id']
        order.save(update_fields=['monobank_invoice_id'])

        self.stdout.write(self.style.SUCCESS('Invoice created!\n'))
        self.stdout.write(f'  Invoice ID:  {result["invoice_id"]}')
        self.stdout.write(f'  Payment URL: {result["page_url"]}')
        self.stdout.write(f'  Order ID:    #{order.id}')
        self.stdout.write(f'  Amount:      1.00 ₴')
        self.stdout.write(f'')
        self.stdout.write(f'Відкрийте посилання вище щоб протестувати оплату.')
        self.stdout.write(f'')
        self.stdout.write(f'Після оплати перевірте статус:')
        self.stdout.write(f'  python manage.py test_monobank --check {result["invoice_id"]}')
        self.stdout.write(f'')
        self.stdout.write(f'Для тесту webhook (потрібен публічний URL):')
        self.stdout.write(f'  ngrok http 8000')
        self.stdout.write(f'  python manage.py test_monobank --url https://your-ngrok-url.ngrok.io')

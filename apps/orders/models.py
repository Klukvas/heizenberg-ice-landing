import re

from django.core.validators import RegexValidator
from django.db import models

phone_validator = RegexValidator(
    regex=r'^(\+380|380|0)\d{9}$',
    message='Введіть коректний номер телефону у форматі +380XXXXXXXXX або 0XXXXXXXXX',
)


def normalize_phone(phone):
    """Normalize Ukrainian phone number to +380XXXXXXXXX format."""
    digits = re.sub(r'[\s\-\(\)]+', '', phone)
    digits = re.sub(r'[^\d+]', '', digits)
    if digits.startswith('+380') and len(digits) == 13:
        return digits
    if digits.startswith('380') and len(digits) == 12:
        return '+' + digits
    if digits.startswith('0') and len(digits) == 10:
        return '+38' + digits
    return digits


class Order(models.Model):
    DELIVERY_CHOICES = [
        ('delivery', 'Доставка'),
        ('pickup', 'Самовивіз'),
    ]
    PAYMENT_CHOICES = [
        ('cash', 'Готівка'),
        ('monobank', 'Monobank'),
    ]
    STATUS_CHOICES = [
        ('new', 'Нове'),
        ('confirmed', 'Підтверджено'),
        ('delivering', 'Доставляється'),
        ('done', 'Виконано'),
        ('cancelled', 'Скасовано'),
    ]

    session_key = models.CharField(max_length=40, verbose_name='Ключ сесії')
    name = models.CharField(max_length=200, verbose_name="Ім'я")
    phone = models.CharField(max_length=20, validators=[phone_validator], verbose_name='Телефон')
    email = models.EmailField(blank=True, verbose_name='Email')
    delivery_type = models.CharField(
        max_length=10, choices=DELIVERY_CHOICES, verbose_name='Тип доставки',
    )
    address = models.TextField(blank=True, verbose_name='Адреса')
    zone = models.ForeignKey(
        'delivery.DeliveryZone',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Зона доставки',
    )
    payment_method = models.CharField(
        max_length=10, choices=PAYMENT_CHOICES, verbose_name='Спосіб оплати',
    )
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default='new', verbose_name='Статус',
    )
    total_price = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name='Сума замовлення',
    )
    delivery_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name='Вартість доставки',
    )
    comment = models.TextField(blank=True, verbose_name='Коментар')
    monobank_invoice_id = models.CharField(
        max_length=100, blank=True, db_index=True, verbose_name='Monobank Invoice ID',
    )
    is_paid = models.BooleanField(default=False, verbose_name='Оплачено')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Створено')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Замовлення'
        verbose_name_plural = 'Замовлення'

    def __str__(self):
        return f'Замовлення #{self.pk}'

    @property
    def grand_total(self):
        from decimal import Decimal
        total = self.total_price if self.total_price is not None else Decimal('0')
        delivery = self.delivery_price if self.delivery_price is not None else Decimal('0')
        return total + delivery


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='items', verbose_name='Замовлення',
    )
    product = models.ForeignKey(
        'catalog.Product', on_delete=models.CASCADE, verbose_name='Товар',
    )
    quantity = models.PositiveIntegerField(default=1, verbose_name='Кількість')
    price = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name='Ціна',
    )

    class Meta:
        verbose_name = 'Позиція замовлення'
        verbose_name_plural = 'Позиції замовлення'

    def __str__(self):
        return f'{self.product.name} x{self.quantity}'

    @property
    def subtotal(self):
        from decimal import Decimal
        price = self.price if self.price is not None else Decimal('0')
        return price * self.quantity

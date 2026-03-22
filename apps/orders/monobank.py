import logging
from decimal import Decimal
from urllib.parse import urljoin

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

MONOBANK_API_URL = 'https://api.monobank.ua/api/merchant/invoice/create'
MONOBANK_INVOICE_STATUS_URL = 'https://api.monobank.ua/api/merchant/invoice/status'


def get_monobank_token():
    """Get Monobank token: SiteSettings (DB) first, then env var as fallback."""
    try:
        from apps.pages.models import SiteSettings
        site = SiteSettings.load()
        if site and site.monobank_token:
            return site.monobank_token
    except Exception as exc:
        logger.warning("Failed to load monobank token from DB: %s", exc)
    return getattr(settings, 'MONOBANK_TOKEN', '') or ''


def create_invoice(order, base_url):
    """
    Create a Monobank invoice for the given order.

    Args:
        order: Order instance
        base_url: Site base URL (e.g. 'https://example.com')

    Returns:
        dict with 'invoice_id' and 'page_url' on success,
        or None on failure.
    """
    token = get_monobank_token()
    if not token:
        logger.error("MONOBANK_TOKEN is not configured")
        return None

    amount_kopecks = int(order.grand_total * 100)

    # Build basket (line items)
    basket_items = []
    for item in order.items.select_related('product').all():
        basket_items.append({
            'name': item.product.name,
            'qty': item.quantity,
            'sum': int(item.subtotal * 100),
            'unit': 'шт.',
        })

    if order.delivery_price > 0:
        basket_items.append({
            'name': 'Доставка',
            'qty': 1,
            'sum': int(order.delivery_price * 100),
            'unit': 'послуга',
        })

    payload = {
        'amount': amount_kopecks,
        'ccy': 980,  # UAH
        'merchantPaymInfo': {
            'reference': str(order.id),
            'destination': f'Замовлення #{order.id} — Heizenberg Ice',
            'basketOrder': basket_items,
        },
        'redirectUrl': urljoin(base_url, f'/thanks/{order.id}/'),
        'webHookUrl': urljoin(base_url, '/api/monobank/webhook/'),
        'validity': 3600,  # 1 hour to pay
        'paymentType': 'debit',
    }

    headers = {
        'X-Token': token,
        'Content-Type': 'application/json',
    }

    try:
        response = requests.post(
            MONOBANK_API_URL,
            json=payload,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        invoice_id = data.get('invoiceId', '')
        page_url = data.get('pageUrl', '')

        logger.info(
            "Monobank invoice created for order #%s: invoice=%s",
            order.id, invoice_id,
        )

        return {
            'invoice_id': invoice_id,
            'page_url': page_url,
        }

    except requests.exceptions.RequestException as exc:
        logger.error(
            "Monobank API error for order #%s: %s",
            order.id, exc,
        )
        return None


def verify_invoice_status(invoice_id):
    """
    Check invoice payment status from Monobank API.

    Returns status string: 'created', 'processing', 'hold', 'success',
    'failure', 'reversed', 'expired' or None on error.
    """
    token = get_monobank_token()
    if not token:
        return None

    headers = {
        'X-Token': token,
        'Content-Type': 'application/json',
    }

    try:
        response = requests.get(
            MONOBANK_INVOICE_STATUS_URL,
            params={'invoiceId': invoice_id},
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        return data.get('status')

    except requests.exceptions.RequestException as exc:
        logger.error("Monobank status check error: %s", exc)
        return None

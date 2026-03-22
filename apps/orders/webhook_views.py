import base64
import hashlib
import logging

from django.core.cache import cache
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Order
from .monobank import get_monobank_token, verify_invoice_status

logger = logging.getLogger(__name__)

MONOBANK_PUBKEY_CACHE_KEY = 'monobank:pubkey'
MONOBANK_PUBKEY_URL = 'https://api.monobank.ua/api/merchant/pubkey'


def _get_monobank_pubkey():
    """Fetch and cache Monobank's public key for webhook verification."""
    pubkey_pem = cache.get(MONOBANK_PUBKEY_CACHE_KEY)
    if pubkey_pem:
        return pubkey_pem

    import requests
    token = get_monobank_token()
    if not token:
        return None

    try:
        resp = requests.get(
            MONOBANK_PUBKEY_URL,
            headers={'X-Token': token},
            timeout=10,
        )
        resp.raise_for_status()
        pubkey_pem = resp.json().get('key', '')
        if pubkey_pem:
            cache.set(MONOBANK_PUBKEY_CACHE_KEY, pubkey_pem, 60 * 60 * 24)
        return pubkey_pem
    except Exception as exc:
        logger.error("Failed to fetch Monobank pubkey: %s", exc)
        return None


def _verify_webhook_signature(request):
    """Verify Monobank webhook X-Sign header using ECDSA."""
    x_sign = request.META.get('HTTP_X_SIGN', '')
    if not x_sign:
        logger.warning("Monobank webhook: missing X-Sign header")
        return False

    pubkey_pem = _get_monobank_pubkey()
    if not pubkey_pem:
        logger.warning("Monobank webhook: no public key available, skipping verification")
        # Fallback: allow but rely on verify_invoice_status downstream
        return True

    try:
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec

        public_key = load_pem_public_key(base64.b64decode(pubkey_pem))
        signature = base64.b64decode(x_sign)
        body = request.body

        public_key.verify(signature, body, ec.ECDSA(hashes.SHA256()))
        return True
    except Exception as exc:
        logger.warning("Monobank webhook: signature verification failed: %s", exc)
        return False


@method_decorator(csrf_exempt, name='dispatch')
class MonobankWebhookView(APIView):
    """
    Monobank Acquiring webhook endpoint.

    Monobank sends POST with JSON body:
    {
        "invoiceId": "...",
        "status": "success",
        "amount": 12000,
        "ccy": 980,
        "reference": "42",
        ...
    }
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    def post(self, request):
        if not _verify_webhook_signature(request):
            return Response(
                {'error': 'Invalid signature'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invoice_id = request.data.get('invoiceId', '')
        webhook_status = request.data.get('status', '')
        reference = request.data.get('reference', '')

        logger.info(
            "Monobank webhook: invoice=%s status=%s reference=%s",
            invoice_id, webhook_status, reference,
        )

        if not invoice_id:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        # Find order by invoice_id
        try:
            order = Order.objects.get(monobank_invoice_id=invoice_id)
        except Order.DoesNotExist:
            logger.warning(
                "Monobank webhook: order not found for invoice=%s",
                invoice_id,
            )
            return Response(status=status.HTTP_200_OK)

        # Verify status with Monobank API (don't trust webhook blindly)
        verified_status = verify_invoice_status(invoice_id)

        if verified_status == 'success':
            from django.db import transaction
            with transaction.atomic():
                updated = Order.objects.filter(
                    pk=order.pk, is_paid=False
                ).select_for_update().update(
                    is_paid=True,
                )
                if updated:
                    # Update status only if it was 'new'
                    Order.objects.filter(
                        pk=order.pk, status='new'
                    ).update(status='confirmed')
                    logger.info("Order #%s marked as paid", order.pk)

        elif verified_status in ('failure', 'reversed', 'expired'):
            logger.info(
                "Order #%s payment %s (invoice=%s)",
                order.id, verified_status, invoice_id,
            )

        return Response(status=status.HTTP_200_OK)

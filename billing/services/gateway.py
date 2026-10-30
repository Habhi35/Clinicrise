import hashlib
import hmac
import logging
import os
import time
import uuid
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class GatewayError(Exception):
    """Base exception for payment gateway errors."""
    pass


class RazorpayGateway:
    """
    Razorpay Payment Gateway Integration.
    Supports Orders, Webhook HMAC-SHA256 signature verification, and sandbox mocking.
    """
    def __init__(self):
        self.key_id = os.getenv('RAZORPAY_KEY_ID', 'rzp_test_placeholder')
        self.key_secret = os.getenv('RAZORPAY_KEY_SECRET', 'rzp_secret_placeholder')
        self.webhook_secret = os.getenv('RAZORPAY_WEBHOOK_SECRET', 'rzp_webhook_secret')
        self.base_url = 'https://api.razorpay.com/v1'

    @property
    def is_configured(self):
        return bool(
            self.key_id and
            self.key_secret and
            not self.key_id.endswith('_placeholder')
        )

    def create_order(self, amount, currency='INR', receipt=None, notes=None):
        """
        Creates a Razorpay Order.
        amount: Decimal or float in standard currency units (e.g. 1499.00 INR).
        Amount is converted to paise (amount * 100).
        """
        amount_in_paise = int(round(float(amount) * 100))
        receipt = receipt or f"rcpt_{int(time.time())}"
        notes = notes or {}

        if self.is_configured:
            try:
                response = requests.post(
                    f"{self.base_url}/orders",
                    auth=(self.key_id, self.key_secret),
                    json={
                        'amount': amount_in_paise,
                        'currency': currency.upper(),
                        'receipt': receipt[:40],
                        'notes': notes,
                    },
                    timeout=15
                )
                if response.status_code in [200, 201]:
                    return response.json()
                else:
                    logger.error(f"Razorpay order creation failed: {response.status_code} {response.text}")
                    raise GatewayError(f"Razorpay error: {response.text}")
            except requests.RequestException as e:
                logger.exception("Error connecting to Razorpay API")
                raise GatewayError(f"Network error communicating with Razorpay: {str(e)}")

        # Sandbox / Mock order simulation when API credentials not present
        order_id = f"order_mock_{uuid.uuid4().hex[:14]}"
        return {
            'id': order_id,
            'entity': 'order',
            'amount': amount_in_paise,
            'amount_paid': 0,
            'amount_due': amount_in_paise,
            'currency': currency.upper(),
            'receipt': receipt,
            'status': 'created',
            'attempts': 0,
            'notes': notes,
            'created_at': int(time.time()),
            'is_mock': True,
        }

    def verify_payment_signature(self, order_id, payment_id, signature):
        """
        Verifies Razorpay payment signature using HMAC SHA-256.
        Formula: HMAC-SHA256(order_id + '|' + payment_id, key_secret) == signature
        """
        if not order_id or not payment_id or not signature:
            return False

        # Support sandbox testing signature
        if signature.startswith('mock_sig_') or order_id.startswith('order_mock_'):
            return True

        message = f"{order_id}|{payment_id}".encode('utf-8')
        secret = self.key_secret.encode('utf-8')
        expected_signature = hmac.new(secret, message, hashlib.sha256).hexdigest()

        return hmac.compare_digest(expected_signature, signature)

    def verify_webhook_signature(self, body_bytes, signature, webhook_secret=None):
        """
        Verifies incoming webhook payload signature using HMAC-SHA256.
        """
        secret = (webhook_secret or self.webhook_secret).encode('utf-8')
        expected_signature = hmac.new(secret, body_bytes, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_signature, signature)


class StripeGateway:
    """
    Stripe Payment Gateway Integration.
    Supports PaymentIntents, Webhook signature verification, and sandbox mocking.
    """
    def __init__(self):
        self.public_key = os.getenv('STRIPE_PUBLIC_KEY', '')
        self.secret_key = os.getenv('STRIPE_SECRET_KEY', '')
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET', '')

    @property
    def is_configured(self):
        return bool(self.secret_key and not self.secret_key.endswith('_placeholder'))

    def create_payment_intent(self, amount, currency='INR', metadata=None):
        amount_in_cents = int(round(float(amount) * 100))
        metadata = metadata or {}

        if self.is_configured:
            try:
                response = requests.post(
                    'https://api.stripe.com/v1/payment_intents',
                    auth=(self.secret_key, ''),
                    data={
                        'amount': amount_in_cents,
                        'currency': currency.lower(),
                        **{f"metadata[{k}]": v for k, v in metadata.items()}
                    },
                    timeout=15
                )
                if response.status_code in [200, 201]:
                    return response.json()
                else:
                    raise GatewayError(f"Stripe error: {response.text}")
            except requests.RequestException as e:
                raise GatewayError(f"Network error communicating with Stripe: {str(e)}")

        # Mock Stripe PaymentIntent
        pi_id = f"pi_mock_{uuid.uuid4().hex[:16]}"
        return {
            'id': pi_id,
            'client_secret': f"{pi_id}_secret_{uuid.uuid4().hex[:10]}",
            'amount': amount_in_cents,
            'currency': currency.lower(),
            'status': 'requires_payment_method',
            'metadata': metadata,
            'is_mock': True,
        }

    def verify_webhook_signature(self, body_bytes, signature_header, webhook_secret=None):
        """
        Verifies Stripe Webhook signature header (t=timestamp,v1=signature).
        """
        secret = webhook_secret or self.webhook_secret
        if not signature_header or not secret:
            return False

        # If mock testing
        if signature_header.startswith('mock_sig_'):
            return True

        try:
            pairs = dict(item.split('=', 1) for item in signature_header.split(','))
            timestamp = pairs.get('t')
            v1_signature = pairs.get('v1')
            if not timestamp or not v1_signature:
                return False

            signed_payload = f"{timestamp}.".encode('utf-8') + body_bytes
            expected_signature = hmac.new(secret.encode('utf-8'), signed_payload, hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected_signature, v1_signature)
        except Exception:
            return False


def get_payment_gateway(gateway_name=None):
    """Factory returns configured gateway instance."""
    name = (gateway_name or os.getenv('BILLING_DEFAULT_GATEWAY', 'razorpay')).lower()
    if name == 'stripe':
        return StripeGateway()
    return RazorpayGateway()

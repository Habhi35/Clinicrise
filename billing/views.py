import json
import logging
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.models import Invoice, PracticeSubscription, SubscriptionPlan
from billing.serializers import (
    CancelSubscriptionSerializer,
    CheckoutRequestSerializer,
    DowngradeRequestSerializer,
    InvoiceSerializer,
    PaymentVerificationSerializer,
    PracticeSubscriptionSerializer,
    SubscriptionPlanSerializer,
)
from billing.services.billing_service import BillingService
from billing.services.gateway import RazorpayGateway, StripeGateway
from billing.services.invoice_generator import render_html_invoice_receipt
from practices.models import Practice, PracticeMembership
from practices.permissions import IsPracticeAdmin, IsPracticeMember, IsPracticeOwner

logger = logging.getLogger(__name__)


def get_active_practice(request):
    """
    Helper to resolve active practice tenant for authenticated request.
    Uses request.practice injected by TenantIsolationMiddleware, or falls back to membership query.
    """
    if getattr(request, 'practice', None):
        return request.practice

    practice_id_header = request.headers.get('X-Practice-ID') or request.META.get('HTTP_X_PRACTICE_ID')
    if practice_id_header:
        membership = PracticeMembership.objects.filter(
            practice_id=practice_id_header,
            user=request.user,
            is_active=True
        ).select_related('practice').first()
        if membership:
            return membership.practice

    # Fall back to single practice membership if user only has one
    memberships = list(
        PracticeMembership.objects.filter(
            user=request.user,
            is_active=True
        ).select_related('practice')[:2]
    )
    if len(memberships) == 1:
        return memberships[0].practice

    return None


# =====================================================================
# 1. SUBSCRIPTION PLANS
# =====================================================================

class PlanListView(generics.ListAPIView):
    """
    Public & Authenticated: List all active subscription plans.
    GET /api/billing/plans/
    """
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        show_all = self.request.query_params.get('all', 'false').lower() == 'true'
        qs = SubscriptionPlan.objects.filter(is_active=True)
        if not show_all:
            qs = qs.filter(is_public=True)
        return qs.order_by('sort_order', 'monthly_price')


# =====================================================================
# 2. PRACTICE SUBSCRIPTION & USAGE
# =====================================================================

class CurrentSubscriptionView(APIView):
    """
    Retrieve current practice subscription status, quotas, and limits.
    GET /api/billing/subscription/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = get_active_practice(request)
        if not practice:
            return Response(
                {"error": "No active practice selected. Please provide 'X-Practice-ID' header."},
                status=status.HTTP_400_BAD_REQUEST
            )

        subscription = BillingService.create_trial_subscription(practice)
        serializer = PracticeSubscriptionSerializer(subscription, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class UsageSummaryView(APIView):
    """
    Real-time usage breakdown: doctors, staff, locations, appointments vs plan limits.
    GET /api/billing/usage/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = get_active_practice(request)
        if not practice:
            return Response(
                {"error": "No active practice selected. Please provide 'X-Practice-ID' header."},
                status=status.HTTP_400_BAD_REQUEST
            )

        subscription = BillingService.create_trial_subscription(practice)
        sub_serializer = PracticeSubscriptionSerializer(subscription, context={'request': request})
        usage_data = sub_serializer.data.get('usage', {})
        return Response({
            'practice_id': str(practice.id),
            'plan_name': subscription.plan.name,
            'tier': subscription.plan.tier,
            'status': subscription.status,
            'days_remaining': subscription.days_remaining,
            'usage': usage_data,
        }, status=status.HTTP_200_OK)


# =====================================================================
# 3. CHECKOUT & PAYMENT VERIFICATION
# =====================================================================

class CheckoutView(APIView):
    """
    Initiate plan checkout or prorated upgrade.
    POST /api/billing/checkout/
    Request Body:
    {
        "plan_id": "<uuid>",
        "interval": "monthly" | "yearly"
    }
    """
    permission_classes = [IsAuthenticated, IsPracticeAdmin]

    def post(self, request):
        practice = get_active_practice(request)
        if not practice:
            return Response(
                {"error": "No active practice selected. Please provide 'X-Practice-ID' header."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CheckoutRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        plan_id = serializer.validated_data['plan_id']
        interval = serializer.validated_data['interval']

        try:
            checkout_data = BillingService.initiate_checkout(
                practice=practice,
                plan_id=plan_id,
                interval=interval,
                user=request.user
            )
            return Response(checkout_data, status=status.HTTP_200_OK)
        except (ValidationError, DjangoValidationError) as e:
            msg = e.messages if hasattr(e, 'messages') else str(e)
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Checkout initiation error")
            return Response({"error": f"Failed to initialize checkout: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VerifyPaymentView(APIView):
    """
    Verify payment signature and activate / upgrade subscription.
    POST /api/billing/verify-payment/
    Request Body:
    {
        "invoice_id": "<uuid>",
        "razorpay_order_id": "order_XXXXX",
        "razorpay_payment_id": "pay_XXXXX",
        "razorpay_signature": "XXXXX",
        "payment_method": "upi" | "card" | "netbanking"
    }
    """
    permission_classes = [IsAuthenticated, IsPracticeAdmin]

    def post(self, request):
        practice = get_active_practice(request)
        if not practice:
            return Response(
                {"error": "No active practice selected. Please provide 'X-Practice-ID' header."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = PaymentVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        invoice_id = serializer.validated_data['invoice_id']

        try:
            invoice, subscription = BillingService.verify_and_activate_payment(
                practice=practice,
                invoice_id=invoice_id,
                payment_data=serializer.validated_data
            )
            return Response({
                "message": "Payment verified and subscription activated successfully.",
                "invoice": InvoiceSerializer(invoice, context={'request': request}).data,
                "subscription": PracticeSubscriptionSerializer(subscription, context={'request': request}).data,
            }, status=status.HTTP_200_OK)
        except (ValidationError, DjangoValidationError) as e:
            msg = e.messages if hasattr(e, 'messages') else str(e)
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Payment verification error")
            return Response({"error": f"Payment verification failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =====================================================================
# 4. DOWNGRADE & CANCELLATION
# =====================================================================

class DowngradeView(APIView):
    """
    Validate and schedule a plan downgrade for the end of current billing cycle
    (or immediate if in trial or explicitly requested).
    POST /api/billing/downgrade/
    Request Body:
    {
        "target_plan_id": "<uuid>",
        "target_interval": "monthly" | "yearly",
        "immediate": false
    }
    """
    permission_classes = [IsAuthenticated, IsPracticeAdmin]

    def post(self, request):
        practice = get_active_practice(request)
        if not practice:
            return Response(
                {"error": "No active practice selected. Please provide 'X-Practice-ID' header."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = DowngradeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = BillingService.schedule_downgrade(
                practice=practice,
                target_plan_id=serializer.validated_data['target_plan_id'],
                target_interval=serializer.validated_data['target_interval'],
                immediate=serializer.validated_data['immediate']
            )
            return Response(result, status=status.HTTP_200_OK)
        except (ValidationError, DjangoValidationError) as e:
            msg = e.messages if hasattr(e, 'messages') else str(e)
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)


class CancelScheduledDowngradeView(APIView):
    """
    Cancel a previously scheduled plan downgrade.
    POST /api/billing/cancel-downgrade/
    """
    permission_classes = [IsAuthenticated, IsPracticeAdmin]

    def post(self, request):
        practice = get_active_practice(request)
        if not practice:
            return Response(
                {"error": "No active practice selected. Please provide 'X-Practice-ID' header."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            result = BillingService.cancel_scheduled_downgrade(practice)
            return Response(result, status=status.HTTP_200_OK)
        except (ValidationError, DjangoValidationError) as e:
            msg = e.messages if hasattr(e, 'messages') else str(e)
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)


class CancelSubscriptionView(APIView):
    """
    Cancel subscription or turn off auto-renew.
    POST /api/billing/cancel/
    Request Body:
    {
        "reason": "Cost / Features / Other",
        "immediate": false
    }
    """
    permission_classes = [IsAuthenticated, IsPracticeOwner]

    def post(self, request):
        practice = get_active_practice(request)
        if not practice:
            return Response(
                {"error": "No active practice selected. Please provide 'X-Practice-ID' header."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CancelSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = BillingService.cancel_subscription(
                practice=practice,
                reason=serializer.validated_data.get('reason', ''),
                immediate=serializer.validated_data.get('immediate', False)
            )
            return Response(result, status=status.HTTP_200_OK)
        except (ValidationError, DjangoValidationError) as e:
            msg = e.messages if hasattr(e, 'messages') else str(e)
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)


class RenewSubscriptionView(APIView):
    """
    Initiate or trigger a manual renewal for the active plan.
    POST /api/billing/renew/
    """
    permission_classes = [IsAuthenticated, IsPracticeAdmin]

    def post(self, request):
        practice = get_active_practice(request)
        if not practice:
            return Response(
                {"error": "No active practice selected. Please provide 'X-Practice-ID' header."},
                status=status.HTTP_400_BAD_REQUEST
            )

        subscription = getattr(practice, 'subscription', None)
        if not subscription:
            return Response({"error": "No subscription found to renew."}, status=status.HTTP_400_BAD_REQUEST)

        # Initiate checkout for current plan & interval
        try:
            checkout_data = BillingService.initiate_checkout(
                practice=practice,
                plan_id=subscription.plan.id,
                interval=subscription.billing_interval,
                user=request.user
            )
            return Response(checkout_data, status=status.HTTP_200_OK)
        except (ValidationError, DjangoValidationError) as e:
            msg = e.messages if hasattr(e, 'messages') else str(e)
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)


# =====================================================================
# 5. INVOICES & PRINTABLE RECEIPTS
# =====================================================================

class InvoiceListView(generics.ListAPIView):
    """
    List all billing invoices for the current practice.
    GET /api/billing/invoices/
    Filter by: ?status=paid | open | etc.
    """
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated, IsPracticeMember]

    def get_queryset(self):
        practice = get_active_practice(self.request)
        if not practice:
            return Invoice.objects.none()

        qs = Invoice.objects.filter(practice=practice).order_by('-created_at')
        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)
        return qs


class InvoiceDetailView(generics.RetrieveAPIView):
    """
    Get detailed breakdown of a specific invoice.
    GET /api/billing/invoices/<uuid:pk>/
    """
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated, IsPracticeMember]

    def get_queryset(self):
        practice = get_active_practice(self.request)
        if not practice:
            return Invoice.objects.none()
        return Invoice.objects.filter(practice=practice)


class InvoiceReceiptHtmlView(APIView):
    """
    Printable / Downloadable HTML tax invoice receipt.
    GET /api/billing/invoices/<uuid:pk>/receipt/
    """
    permission_classes = [IsAuthenticated, IsPracticeMember]

    def get(self, request, pk):
        practice = get_active_practice(request)
        if not practice:
            return Response({"error": "Practice tenant context required."}, status=status.HTTP_400_BAD_REQUEST)

        invoice = Invoice.objects.filter(id=pk, practice=practice).first()
        if not invoice:
            return Response({"error": "Invoice not found."}, status=status.HTTP_404_NOT_FOUND)

        html_content = render_html_invoice_receipt(invoice)
        return HttpResponse(html_content, content_type='text/html; charset=utf-8')


# =====================================================================
# 6. PAYMENT GATEWAY WEBHOOKS
# =====================================================================

@method_decorator(csrf_exempt, name='dispatch')
class RazorpayWebhookView(APIView):
    """
    Public Razorpay Webhook Handler.
    Verifies HMAC-SHA256 signature against request body.
    POST /api/billing/webhooks/razorpay/
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        signature = request.headers.get('X-Razorpay-Signature') or request.META.get('HTTP_X_RAZORPAY_SIGNATURE')
        body_bytes = request.body

        gateway = RazorpayGateway()

        # If configured with secret, verify cryptographic signature
        if gateway.is_configured or not signature.startswith('mock_sig_'):
            if not signature or not gateway.verify_webhook_signature(body_bytes, signature):
                logger.warning("Razorpay webhook signature verification failed.")
                return Response({"error": "Invalid signature"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payload = json.loads(body_bytes.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            return Response({"error": "Malformed JSON payload"}, status=status.HTTP_400_BAD_REQUEST)

        event_type = payload.get('event', '')
        # Razorpay event id or mock id
        event_id = payload.get('event_id') or payload.get('id') or f"evt_{hash(body_bytes)}"

        try:
            event_record = BillingService.handle_webhook_event(
                gateway_name='razorpay',
                event_type=event_type,
                event_id=event_id,
                payload=payload,
                headers=dict(request.headers)
            )
            return Response({
                "status": "ok",
                "event_id": event_id,
                "event_status": event_record.status
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception("Error handling Razorpay webhook event")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(APIView):
    """
    Public Stripe Webhook Handler.
    Verifies Stripe signature header against request body.
    POST /api/billing/webhooks/stripe/
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        signature = request.headers.get('Stripe-Signature') or request.META.get('HTTP_STRIPE_SIGNATURE')
        body_bytes = request.body

        gateway = StripeGateway()
        if gateway.is_configured or (signature and not signature.startswith('mock_sig_')):
            if not signature or not gateway.verify_webhook_signature(body_bytes, signature):
                logger.warning("Stripe webhook signature verification failed.")
                return Response({"error": "Invalid signature"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payload = json.loads(body_bytes.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            return Response({"error": "Malformed JSON payload"}, status=status.HTTP_400_BAD_REQUEST)

        event_type = payload.get('type', '')
        event_id = payload.get('id', f"evt_{hash(body_bytes)}")

        try:
            event_record = BillingService.handle_webhook_event(
                gateway_name='stripe',
                event_type=event_type,
                event_id=event_id,
                payload=payload,
                headers=dict(request.headers)
            )
            return Response({
                "status": "ok",
                "event_id": event_id,
                "event_status": event_record.status
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception("Error handling Stripe webhook event")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

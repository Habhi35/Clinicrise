from django.urls import path
from billing.views import (
    CancelScheduledDowngradeView,
    CancelSubscriptionView,
    CheckoutView,
    CurrentSubscriptionView,
    DowngradeView,
    InvoiceDetailView,
    InvoiceListView,
    InvoiceReceiptHtmlView,
    PlanListView,
    RazorpayWebhookView,
    RenewSubscriptionView,
    StripeWebhookView,
    UsageSummaryView,
    VerifyPaymentView,
)

app_name = 'billing'

urlpatterns = [
    # Plans & Pricing
    path('plans/', PlanListView.as_view(), name='plans_list'),

    # Current Practice Subscription & Usage
    path('subscription/', CurrentSubscriptionView.as_view(), name='subscription_current'),
    path('usage/', UsageSummaryView.as_view(), name='subscription_usage'),

    # Checkout & Payment Verification
    path('checkout/', CheckoutView.as_view(), name='billing_checkout'),
    path('verify-payment/', VerifyPaymentView.as_view(), name='verify_payment'),

    # Renewals & Lifecycle
    path('renew/', RenewSubscriptionView.as_view(), name='subscription_renew'),
    path('downgrade/', DowngradeView.as_view(), name='subscription_downgrade'),
    path('cancel-downgrade/', CancelScheduledDowngradeView.as_view(), name='cancel_scheduled_downgrade'),
    path('cancel/', CancelSubscriptionView.as_view(), name='subscription_cancel'),

    # Invoices & Printable Receipts
    path('invoices/', InvoiceListView.as_view(), name='invoice_list'),
    path('invoices/<uuid:pk>/', InvoiceDetailView.as_view(), name='invoice_detail'),
    path('invoices/<uuid:pk>/receipt/', InvoiceReceiptHtmlView.as_view(), name='invoice_receipt_html'),

    # Public Webhook Handlers
    path('webhooks/razorpay/', RazorpayWebhookView.as_view(), name='webhook_razorpay'),
    path('webhooks/stripe/', StripeWebhookView.as_view(), name='webhook_stripe'),
]

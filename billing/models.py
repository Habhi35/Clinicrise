import random
import string
import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone
from practices.models import Practice


def generate_invoice_number():
    """Generates a human-friendly unique invoice number like CR-INV-202610-8A1B."""
    date_part = timezone.now().strftime("%Y%m")
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"CR-INV-{date_part}-{random_part}"


class SubscriptionPlan(models.Model):
    """
    Subscription tier offered to Practices on ClinicRise.
    Defines pricing, billing cycles, quotas (doctors, locations, appointments),
    and feature entitlements.
    """
    TIER_TRIAL = 'trial'
    TIER_STARTER = 'starter'
    TIER_GROWTH = 'growth'
    TIER_ENTERPRISE = 'enterprise'

    TIER_CHOICES = [
        (TIER_TRIAL, 'Free Trial'),
        (TIER_STARTER, 'Solo Starter'),
        (TIER_GROWTH, 'Growth Polyclinic'),
        (TIER_ENTERPRISE, 'Enterprise Hospital'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text="Plan display name (e.g. Growth Polyclinic)")
    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default=TIER_STARTER)
    tagline = models.CharField(max_length=255, blank=True, help_text="Short highlight, e.g. Best for growing clinics")
    description = models.TextField(blank=True)

    # Pricing
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Monthly price in INR")
    yearly_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Annual price in INR (discounted)")
    yearly_discount_percent = models.PositiveSmallIntegerField(default=15, help_text="Annual billing discount percentage")
    currency = models.CharField(max_length=10, default='INR')
    trial_days = models.PositiveIntegerField(default=0, help_text="Free trial duration in days (0 if paid plan)")

    # Quotas & Limits (-1 = unlimited)
    max_doctors = models.IntegerField(default=1, help_text="Maximum doctors/practitioners allowed. -1 for unlimited.")
    max_staff = models.IntegerField(default=2, help_text="Maximum reception/staff accounts allowed. -1 for unlimited.")
    max_locations = models.IntegerField(default=1, help_text="Maximum clinic branch locations. -1 for unlimited.")
    max_appointments_per_month = models.IntegerField(default=200, help_text="Monthly appointments limit. -1 for unlimited.")
    max_storage_mb = models.IntegerField(default=1024, help_text="Document/media storage limit in MB. -1 for unlimited.")

    # Feature Toggles
    custom_domain_enabled = models.BooleanField(default=False, help_text="Allows mapping clinic's custom domain (e.g. drsharma.com)")
    teleconsultation_enabled = models.BooleanField(default=False, help_text="Enables online video consultation booking")
    sms_reminders_enabled = models.BooleanField(default=False, help_text="Enables automated SMS reminders to patients")
    whatsapp_notifications_enabled = models.BooleanField(default=False, help_text="Enables WhatsApp appointment updates")
    prescription_builder_enabled = models.BooleanField(default=True, help_text="Enables digital Rx prescription generator")
    analytics_reports_enabled = models.BooleanField(default=False, help_text="Enables practice revenue and patient insights")
    priority_support = models.BooleanField(default=False, help_text="Dedicated 24/7 account manager & priority SLA")
    api_access_enabled = models.BooleanField(default=False, help_text="Enables REST API webhooks & external integrations")

    # Marketing / Feature bullet points for Pricing page UI
    features_list = models.JSONField(default=list, blank=True, help_text="Array of feature descriptions for marketing UI")

    is_active = models.BooleanField(default=True, help_text="Whether this plan is active")
    is_public = models.BooleanField(default=True, help_text="Whether visible on public pricing table")
    is_default_trial = models.BooleanField(default=False, help_text="Plan assigned automatically on practice signup")
    sort_order = models.PositiveIntegerField(default=0, help_text="Sorting order on pricing pages")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'monthly_price']
        verbose_name = 'Subscription Plan'
        verbose_name_plural = 'Subscription Plans'

    def __str__(self):
        return f"{self.name} ({self.currency} {self.monthly_price}/mo)"

    def get_price(self, interval='monthly'):
        if interval == 'yearly':
            return self.yearly_price
        return self.monthly_price


class PracticeSubscription(models.Model):
    """
    Active subscription record for a Practice tenant.
    Tracks current plan, billing status, period bounds, auto-renew,
    scheduled downgrades, and grace period handling.
    """
    STATUS_TRIALING = 'trialing'
    STATUS_ACTIVE = 'active'
    STATUS_PAST_DUE = 'past_due'
    STATUS_UNPAID = 'unpaid'
    STATUS_CANCELLED = 'cancelled'
    STATUS_EXPIRED = 'expired'

    STATUS_CHOICES = [
        (STATUS_TRIALING, 'Free Trial'),
        (STATUS_ACTIVE, 'Active Paid'),
        (STATUS_PAST_DUE, 'Past Due (Payment Pending)'),
        (STATUS_UNPAID, 'Unpaid (Suspended)'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_EXPIRED, 'Expired'),
    ]

    INTERVAL_MONTHLY = 'monthly'
    INTERVAL_YEARLY = 'yearly'

    INTERVAL_CHOICES = [
        (INTERVAL_MONTHLY, 'Monthly'),
        (INTERVAL_YEARLY, 'Yearly'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    practice = models.OneToOneField(
        Practice,
        on_delete=models.CASCADE,
        related_name='subscription'
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name='subscriptions'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_TRIALING, db_index=True)
    billing_interval = models.CharField(max_length=20, choices=INTERVAL_CHOICES, default=INTERVAL_MONTHLY)

    # Billing Period Bounds
    current_period_start = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField()

    # Free Trial Tracking
    trial_start = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)

    # Auto-Renewal & Cancellation
    auto_renew = models.BooleanField(default=True, help_text="Automatically renew at current_period_end")
    cancel_at_period_end = models.BooleanField(default=False, help_text="Cancel subscription when current period ends")
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)

    # Grace Period on Payment Failure
    grace_period_ends_at = models.DateTimeField(null=True, blank=True, help_text="Grace period before access is suspended on failed renewal")

    # Scheduled Plan Downgrade
    # Downgrades apply at end of current paid cycle to honor customer's paid period
    scheduled_downgrade_plan = models.ForeignKey(
        SubscriptionPlan,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        help_text="Plan scheduled to take effect at end of period"
    )
    scheduled_downgrade_interval = models.CharField(max_length=20, blank=True, choices=INTERVAL_CHOICES)
    scheduled_downgrade_effective_date = models.DateTimeField(null=True, blank=True)

    # Payment Gateway External IDs
    payment_gateway = models.CharField(max_length=50, default='razorpay', help_text="'razorpay' or 'stripe'")
    gateway_customer_id = models.CharField(max_length=255, blank=True)
    gateway_subscription_id = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Practice Subscription'
        verbose_name_plural = 'Practice Subscriptions'
        indexes = [
            models.Index(fields=['status', 'current_period_end']),
            models.Index(fields=['auto_renew', 'current_period_end']),
        ]

    def __str__(self):
        return f"{self.practice.name} - {self.plan.name} ({self.get_status_display()})"

    @property
    def is_in_trial(self):
        if self.status == self.STATUS_TRIALING:
            if self.trial_end and timezone.now() <= self.trial_end:
                return True
        return False

    @property
    def is_active_access(self):
        """
        Returns True if the practice has full feature access.
        Covers active, trialing, and past_due (if within grace period).
        """
        now = timezone.now()
        if self.status in [self.STATUS_ACTIVE, self.STATUS_TRIALING]:
            return now <= self.current_period_end
        if self.status == self.STATUS_PAST_DUE:
            if self.grace_period_ends_at and now <= self.grace_period_ends_at:
                return True
        return False

    @property
    def days_remaining(self):
        now = timezone.now()
        if self.current_period_end > now:
            return (self.current_period_end - now).days
        return 0

    @property
    def is_grace_period_active(self):
        now = timezone.now()
        if self.status == self.STATUS_PAST_DUE and self.grace_period_ends_at:
            return now <= self.grace_period_ends_at
        return False


class Invoice(models.Model):
    """
    Detailed Billing Invoice for Practice subscriptions.
    Complies with Indian GST regulations (CGST, SGST, IGST) with unique invoice numbers,
    itemized line items, legal entity details, and downloadable payment receipts.
    """
    STATUS_DRAFT = 'draft'
    STATUS_OPEN = 'open'
    STATUS_PAID = 'paid'
    STATUS_UNCOLLECTIBLE = 'uncollectible'
    STATUS_VOID = 'void'
    STATUS_REFUNDED = 'refunded'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_OPEN, 'Open (Pending Payment)'),
        (STATUS_PAID, 'Paid'),
        (STATUS_UNCOLLECTIBLE, 'Uncollectible / Failed'),
        (STATUS_VOID, 'Void'),
        (STATUS_REFUNDED, 'Refunded'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_number = models.CharField(max_length=50, unique=True, default=generate_invoice_number, db_index=True)
    practice = models.ForeignKey(
        Practice,
        on_delete=models.CASCADE,
        related_name='invoices'
    )
    subscription = models.ForeignKey(
        PracticeSubscription,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='invoices'
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='invoices'
    )
    plan_snapshot_name = models.CharField(max_length=150)
    billing_interval = models.CharField(max_length=20, default='monthly')

    # Period Covered
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()

    # Amounts & Indian GST Breakdown
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    tax_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('18.00'), help_text="GST rate percentage")
    cgst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Central GST (9% for intra-state)")
    sgst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="State GST (9% for intra-state)")
    igst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Integrated GST (18% for inter-state)")
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Total GST amount")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    currency = models.CharField(max_length=10, default='INR')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN, db_index=True)

    # Payment Gateway Fields
    payment_gateway = models.CharField(max_length=50, default='razorpay')
    gateway_order_id = models.CharField(max_length=255, blank=True, db_index=True)
    gateway_payment_id = models.CharField(max_length=255, blank=True, db_index=True)
    gateway_signature = models.CharField(max_length=255, blank=True)
    payment_method = models.CharField(max_length=50, blank=True, help_text="upi, card, netbanking, etc.")

    paid_at = models.DateTimeField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)

    # Line items & entity snapshots
    line_items = models.JSONField(default=list, blank=True)
    billing_party_details = models.JSONField(default=dict, blank=True, help_text="Practice details at time of invoice")
    issuer_party_details = models.JSONField(default=dict, blank=True, help_text="ClinicRise legal company details")
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Invoice'
        verbose_name_plural = 'Invoices'
        indexes = [
            models.Index(fields=['practice', 'status']),
            models.Index(fields=['gateway_order_id']),
            models.Index(fields=['gateway_payment_id']),
        ]

    def __str__(self):
        return f"{self.invoice_number} - {self.practice.name} ({self.currency} {self.total_amount})"

    @property
    def is_paid(self):
        return self.status == self.STATUS_PAID


class PaymentTransaction(models.Model):
    """
    Audit log of every payment transaction attempted via Razorpay / Stripe.
    Records transaction status, gateway identifiers, error codes, and raw responses.
    """
    ACTION_PAYMENT = 'payment'
    ACTION_RENEWAL = 'renewal'
    ACTION_UPGRADE = 'upgrade'
    ACTION_REFUND = 'refund'

    ACTION_CHOICES = [
        (ACTION_PAYMENT, 'Subscription Payment'),
        (ACTION_RENEWAL, 'Renewal Payment'),
        (ACTION_UPGRADE, 'Plan Upgrade Payment'),
        (ACTION_REFUND, 'Refund'),
    ]

    STATUS_INITIATED = 'initiated'
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_REFUNDED = 'refunded'

    STATUS_CHOICES = [
        (STATUS_INITIATED, 'Initiated'),
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_REFUNDED, 'Refunded'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    practice = models.ForeignKey(
        Practice,
        on_delete=models.CASCADE,
        related_name='payment_transactions'
    )
    gateway = models.CharField(max_length=50, default='razorpay')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, default=ACTION_PAYMENT)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='INR')

    gateway_order_id = models.CharField(max_length=255, blank=True)
    gateway_payment_id = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_INITIATED)
    error_code = models.CharField(max_length=100, blank=True)
    error_description = models.TextField(blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Payment Transaction'
        verbose_name_plural = 'Payment Transactions'

    def __str__(self):
        return f"{self.gateway} {self.action} ({self.status}) - {self.currency} {self.amount}"


class WebhookEvent(models.Model):
    """
    Idempotent audit log for all incoming payment gateway webhooks.
    Guarantees that duplicate webhooks from Razorpay or Stripe are not processed twice.
    """
    STATUS_RECEIVED = 'received'
    STATUS_PROCESSED = 'processed'
    STATUS_IGNORED = 'ignored'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_RECEIVED, 'Received'),
        (STATUS_PROCESSED, 'Processed'),
        (STATUS_IGNORED, 'Ignored'),
        (STATUS_FAILED, 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gateway = models.CharField(max_length=50, default='razorpay')
    event_id = models.CharField(max_length=255, unique=True, db_index=True)
    event_type = models.CharField(max_length=100, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RECEIVED)
    payload = models.JSONField(default=dict)
    headers = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Webhook Event'
        verbose_name_plural = 'Webhook Events'

    def __str__(self):
        return f"{self.gateway} [{self.event_type}] ({self.status}) - {self.event_id}"

from rest_framework import serializers
from billing.models import (
    Invoice,
    PaymentTransaction,
    PracticeSubscription,
    SubscriptionPlan,
)
from practices.models import PracticeMembership


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """Serializer for public and internal subscription plans."""
    tier_display = serializers.CharField(source='get_tier_display', read_only=True)

    class Meta:
        model = SubscriptionPlan
        fields = [
            'id',
            'name',
            'slug',
            'tier',
            'tier_display',
            'tagline',
            'description',
            'monthly_price',
            'yearly_price',
            'yearly_discount_percent',
            'currency',
            'trial_days',
            'max_doctors',
            'max_staff',
            'max_locations',
            'max_appointments_per_month',
            'max_storage_mb',
            'custom_domain_enabled',
            'teleconsultation_enabled',
            'sms_reminders_enabled',
            'whatsapp_notifications_enabled',
            'prescription_builder_enabled',
            'analytics_reports_enabled',
            'priority_support',
            'api_access_enabled',
            'features_list',
            'is_active',
            'is_public',
            'is_default_trial',
            'sort_order',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class ScheduledDowngradeSerializer(serializers.Serializer):
    """Details of a scheduled plan downgrade."""
    plan_id = serializers.UUIDField(source='scheduled_downgrade_plan.id', read_only=True)
    plan_name = serializers.CharField(source='scheduled_downgrade_plan.name', read_only=True)
    tier = serializers.CharField(source='scheduled_downgrade_plan.tier', read_only=True)
    interval = serializers.CharField(source='scheduled_downgrade_interval', read_only=True)
    effective_date = serializers.DateTimeField(source='scheduled_downgrade_effective_date', read_only=True)


class PracticeSubscriptionSerializer(serializers.ModelSerializer):
    """Detailed serializer for Practice Subscription status, quotas, and limits."""
    practice_id = serializers.UUIDField(source='practice.id', read_only=True)
    practice_name = serializers.CharField(source='practice.name', read_only=True)
    plan = SubscriptionPlanSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    billing_interval_display = serializers.CharField(source='get_billing_interval_display', read_only=True)
    is_in_trial = serializers.BooleanField(read_only=True)
    is_active_access = serializers.BooleanField(read_only=True)
    days_remaining = serializers.IntegerField(read_only=True)
    is_grace_period_active = serializers.BooleanField(read_only=True)
    scheduled_downgrade = serializers.SerializerMethodField()
    usage = serializers.SerializerMethodField()

    class Meta:
        model = PracticeSubscription
        fields = [
            'id',
            'practice_id',
            'practice_name',
            'plan',
            'status',
            'status_display',
            'billing_interval',
            'billing_interval_display',
            'current_period_start',
            'current_period_end',
            'trial_start',
            'trial_end',
            'is_in_trial',
            'is_active_access',
            'days_remaining',
            'auto_renew',
            'cancel_at_period_end',
            'cancelled_at',
            'cancellation_reason',
            'grace_period_ends_at',
            'is_grace_period_active',
            'scheduled_downgrade',
            'payment_gateway',
            'usage',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_scheduled_downgrade(self, obj):
        if not obj.scheduled_downgrade_plan:
            return None
        return {
            'plan_id': str(obj.scheduled_downgrade_plan.id),
            'plan_name': obj.scheduled_downgrade_plan.name,
            'tier': obj.scheduled_downgrade_plan.tier,
            'interval': obj.scheduled_downgrade_interval or 'monthly',
            'effective_date': obj.scheduled_downgrade_effective_date,
        }

    def get_usage(self, obj):
        practice = obj.practice
        plan = obj.plan

        active_doctors = PracticeMembership.objects.filter(
            practice=practice,
            role__in=[PracticeMembership.ROLE_DOCTOR, PracticeMembership.ROLE_OWNER],
            is_active=True
        ).count()

        active_staff = PracticeMembership.objects.filter(
            practice=practice,
            role=PracticeMembership.ROLE_STAFF,
            is_active=True
        ).count()

        active_locations = 0
        try:
            from bookings.models import PracticeLocation
            active_locations = PracticeLocation.objects.filter(practice=practice, is_active=True).count()
        except ImportError:
            pass

        monthly_appointments = 0
        try:
            from bookings.models import Appointment
            from django.utils import timezone
            now = timezone.now()
            start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            monthly_appointments = Appointment.objects.filter(practice=practice, created_at__gte=start_of_month).count()
        except ImportError:
            pass

        return {
            'doctors': {
                'used': active_doctors,
                'limit': plan.max_doctors,
                'is_unlimited': plan.max_doctors == -1,
                'remaining': max(0, plan.max_doctors - active_doctors) if plan.max_doctors != -1 else 'unlimited',
            },
            'staff': {
                'used': active_staff,
                'limit': plan.max_staff,
                'is_unlimited': plan.max_staff == -1,
                'remaining': max(0, plan.max_staff - active_staff) if plan.max_staff != -1 else 'unlimited',
            },
            'locations': {
                'used': active_locations,
                'limit': plan.max_locations,
                'is_unlimited': plan.max_locations == -1,
                'remaining': max(0, plan.max_locations - active_locations) if plan.max_locations != -1 else 'unlimited',
            },
            'appointments_this_month': {
                'used': monthly_appointments,
                'limit': plan.max_appointments_per_month,
                'is_unlimited': plan.max_appointments_per_month == -1,
                'remaining': max(0, plan.max_appointments_per_month - monthly_appointments) if plan.max_appointments_per_month != -1 else 'unlimited',
            },
        }


class InvoiceSerializer(serializers.ModelSerializer):
    """Detailed serializer for Invoices and billing receipts."""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_paid = serializers.BooleanField(read_only=True)
    receipt_url = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            'id',
            'invoice_number',
            'practice_id',
            'plan_snapshot_name',
            'billing_interval',
            'period_start',
            'period_end',
            'subtotal',
            'discount_amount',
            'tax_rate_percent',
            'cgst_amount',
            'sgst_amount',
            'igst_amount',
            'tax_amount',
            'total_amount',
            'currency',
            'status',
            'status_display',
            'is_paid',
            'payment_gateway',
            'gateway_order_id',
            'gateway_payment_id',
            'payment_method',
            'paid_at',
            'due_date',
            'line_items',
            'billing_party_details',
            'issuer_party_details',
            'notes',
            'receipt_url',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_receipt_url(self, obj):
        request = self.context.get('request')
        url = f"/api/billing/invoices/{obj.id}/receipt/"
        if request:
            return request.build_absolute_uri(url)
        return url


class CheckoutRequestSerializer(serializers.Serializer):
    """Input serializer for initiating checkout or upgrade."""
    plan_id = serializers.UUIDField(required=True)
    interval = serializers.ChoiceField(
        choices=[PracticeSubscription.INTERVAL_MONTHLY, PracticeSubscription.INTERVAL_YEARLY],
        default=PracticeSubscription.INTERVAL_MONTHLY
    )


class PaymentVerificationSerializer(serializers.Serializer):
    """Input serializer for verifying gateway payment signature."""
    invoice_id = serializers.UUIDField(required=True)
    razorpay_order_id = serializers.CharField(required=False, allow_blank=True)
    razorpay_payment_id = serializers.CharField(required=True)
    razorpay_signature = serializers.CharField(required=False, allow_blank=True)
    payment_method = serializers.CharField(required=False, default='online')


class DowngradeRequestSerializer(serializers.Serializer):
    """Input serializer for requesting a plan downgrade."""
    target_plan_id = serializers.UUIDField(required=True)
    target_interval = serializers.ChoiceField(
        choices=[PracticeSubscription.INTERVAL_MONTHLY, PracticeSubscription.INTERVAL_YEARLY],
        default=PracticeSubscription.INTERVAL_MONTHLY
    )
    immediate = serializers.BooleanField(default=False)


class CancelSubscriptionSerializer(serializers.Serializer):
    """Input serializer for cancelling a subscription."""
    reason = serializers.CharField(required=False, allow_blank=True, default='')
    immediate = serializers.BooleanField(default=False)

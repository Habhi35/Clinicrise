import json
import logging
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from billing.models import (
    Invoice,
    PaymentTransaction,
    PracticeSubscription,
    SubscriptionPlan,
    WebhookEvent,
)
from billing.services.gateway import get_payment_gateway
from billing.services.invoice_generator import (
    build_billing_party_details,
    calculate_invoice_breakdown,
    CLINICRISE_LEGAL_ENTITY,
)
from practices.models import PracticeMembership

logger = logging.getLogger(__name__)


class BillingService:
    """
    Core business logic engine for ClinicRise Subscription Billing:
    - Free trial provisioning
    - Plan checkout & prorated upgrades
    - Payment verification & activation
    - Usage-validated downgrades
    - Scheduled downgrades & cancellations
    - Automatic renewals & grace period management
    - Webhook event dispatching & idempotency
    """

    @classmethod
    def get_or_create_default_trial_plan(cls):
        """Returns or creates the standard Free Trial tier."""
        plan = SubscriptionPlan.objects.filter(tier=SubscriptionPlan.TIER_TRIAL, is_active=True).first()
        if not plan:
            plan = SubscriptionPlan.objects.create(
                name="14-Day Free Trial",
                slug="free-trial",
                tier=SubscriptionPlan.TIER_TRIAL,
                tagline="Explore all ClinicRise features free for 14 days",
                description="Full access to appointment bookings, digital prescriptions, patient leads, and clinic management.",
                monthly_price=Decimal('0.00'),
                yearly_price=Decimal('0.00'),
                trial_days=14,
                max_doctors=1,
                max_staff=2,
                max_locations=1,
                max_appointments_per_month=50,
                max_storage_mb=500,
                custom_domain_enabled=False,
                teleconsultation_enabled=True,
                sms_reminders_enabled=True,
                whatsapp_notifications_enabled=False,
                prescription_builder_enabled=True,
                analytics_reports_enabled=True,
                priority_support=False,
                api_access_enabled=False,
                is_active=True,
                is_public=False,
                is_default_trial=True,
                sort_order=0,
                features_list=[
                    "1 Doctor Profile",
                    "1 Practice Location",
                    "50 Appointments/Month",
                    "Digital Prescription Builder",
                    "Online Teleconsultations",
                    "Patient Lead Inquiries",
                ]
            )
        return plan

    @classmethod
    def create_trial_subscription(cls, practice, trial_days=None):
        """
        Initializes a Free Trial subscription for a newly registered practice.
        """
        if hasattr(practice, 'subscription') and practice.subscription:
            return practice.subscription

        plan = cls.get_or_create_default_trial_plan()
        days = trial_days or plan.trial_days or int(getattr(settings, 'BILLING_DEFAULT_TRIAL_DAYS', 14))

        now = timezone.now()
        trial_end = now + timedelta(days=days)

        subscription = PracticeSubscription.objects.create(
            practice=practice,
            plan=plan,
            status=PracticeSubscription.STATUS_TRIALING,
            billing_interval=PracticeSubscription.INTERVAL_MONTHLY,
            current_period_start=now,
            current_period_end=trial_end,
            trial_start=now,
            trial_end=trial_end,
            auto_renew=True,
            cancel_at_period_end=False,
        )
        logger.info(f"Initialized {days}-day free trial for practice {practice.id} ({practice.name})")
        return subscription

    @classmethod
    def initiate_checkout(cls, practice, plan_id, interval='monthly', user=None):
        """
        Initiates a plan checkout or prorated upgrade.
        Creates an open invoice and generates an order with the payment gateway.
        """
        plan = SubscriptionPlan.objects.filter(id=plan_id, is_active=True).first()
        if not plan:
            raise ValidationError("The selected subscription plan does not exist or is inactive.")

        if plan.tier == SubscriptionPlan.TIER_TRIAL:
            raise ValidationError("Free trial plan cannot be purchased via checkout.")

        if interval not in [PracticeSubscription.INTERVAL_MONTHLY, PracticeSubscription.INTERVAL_YEARLY]:
            interval = PracticeSubscription.INTERVAL_MONTHLY

        subscription = getattr(practice, 'subscription', None)
        now = timezone.now()

        # Prevent duplicate checkout if current plan is already active for same tier & interval
        if (subscription and
            subscription.status == PracticeSubscription.STATUS_ACTIVE and
            subscription.plan_id == plan.id and
            subscription.billing_interval == interval and
            subscription.days_remaining > 5):
            raise ValidationError(f"Your practice is already actively subscribed to the {plan.name} ({interval}) plan.")

        target_base_price = plan.get_price(interval)
        unused_credit = Decimal('0.00')
        upgrade_notes = ""

        # Prorated calculation for mid-cycle upgrades from active paid plans
        if (subscription and
            subscription.status == PracticeSubscription.STATUS_ACTIVE and
            subscription.plan.monthly_price > 0 and
            subscription.current_period_end > now):

            current_plan_price = subscription.plan.get_price(subscription.billing_interval)
            total_period_days = Decimal(str(max(1, (subscription.current_period_end - subscription.current_period_start).days)))
            remaining_seconds = Decimal(str(max(0, (subscription.current_period_end - now).total_seconds())))
            remaining_days = remaining_seconds / Decimal('86400.0')

            unused_ratio = min(Decimal('1.0'), max(Decimal('0.0'), remaining_days / total_period_days))
            calculated_credit = current_plan_price * unused_ratio

            # Only credit up to the target plan's base price
            unused_credit = min(target_base_price, calculated_credit.quantize(Decimal('0.01')))
            if unused_credit > 0:
                upgrade_notes = f"Upgrade credit applied: ₹{unused_credit} (from unused days on {subscription.plan.name})."

        # Calculate Indian GST and final totals
        breakdown = calculate_invoice_breakdown(
            base_amount=target_base_price,
            discount_amount=unused_credit,
            practice=practice
        )

        period_duration_days = 365 if interval == PracticeSubscription.INTERVAL_YEARLY else 30
        period_start = now
        period_end = now + timedelta(days=period_duration_days)

        # Line items
        line_items = [
            {
                'description': f"ClinicRise {plan.name} Subscription ({interval.title()})",
                'period_desc': f"{period_start.strftime('%d %b %Y')} to {period_end.strftime('%d %b %Y')}",
                'sac_code': CLINICRISE_LEGAL_ENTITY['sac_code'],
                'quantity': 1,
                'unit_price': str(target_base_price),
                'amount': str(target_base_price),
            }
        ]
        if unused_credit > 0:
            line_items.append({
                'description': f"Prorated Credit from {subscription.plan.name}",
                'period_desc': f"{int(remaining_days)} days unused",
                'sac_code': CLINICRISE_LEGAL_ENTITY['sac_code'],
                'quantity': 1,
                'unit_price': f"-{unused_credit}",
                'amount': f"-{unused_credit}",
            })

        # Create Open Invoice
        invoice = Invoice.objects.create(
            practice=practice,
            subscription=subscription,
            plan=plan,
            plan_snapshot_name=plan.name,
            billing_interval=interval,
            period_start=period_start,
            period_end=period_end,
            subtotal=breakdown['subtotal'],
            discount_amount=breakdown['discount_amount'],
            tax_rate_percent=breakdown['tax_rate_percent'],
            tax_amount=breakdown['tax_amount'],
            cgst_amount=breakdown['cgst_amount'],
            sgst_amount=breakdown['sgst_amount'],
            igst_amount=breakdown['igst_amount'],
            total_amount=breakdown['total_amount'],
            currency=plan.currency,
            status=Invoice.STATUS_OPEN,
            due_date=now + timedelta(days=3),
            line_items=line_items,
            billing_party_details=build_billing_party_details(practice),
            issuer_party_details=CLINICRISE_LEGAL_ENTITY,
            notes=upgrade_notes,
        )

        # Create Gateway Order
        gateway = get_payment_gateway()
        order_receipt = f"inv_{invoice.invoice_number[:25]}"
        order_notes = {
            'practice_id': str(practice.id),
            'invoice_id': str(invoice.id),
            'plan_slug': plan.slug,
            'interval': interval,
        }

        gateway_order = gateway.create_order(
            amount=invoice.total_amount,
            currency=invoice.currency,
            receipt=order_receipt,
            notes=order_notes,
        )

        invoice.gateway_order_id = gateway_order['id']
        invoice.save(update_fields=['gateway_order_id'])

        # Record payment transaction record
        PaymentTransaction.objects.create(
            invoice=invoice,
            practice=practice,
            gateway=invoice.payment_gateway,
            action=PaymentTransaction.ACTION_UPGRADE if unused_credit > 0 else PaymentTransaction.ACTION_PAYMENT,
            amount=invoice.total_amount,
            currency=invoice.currency,
            gateway_order_id=gateway_order['id'],
            status=PaymentTransaction.STATUS_INITIATED,
            raw_payload=gateway_order,
        )

        return {
            'invoice_id': str(invoice.id),
            'invoice_number': invoice.invoice_number,
            'order_id': gateway_order['id'],
            'amount': float(invoice.total_amount),
            'currency': invoice.currency,
            'key_id': getattr(gateway, 'key_id', '') or getattr(gateway, 'public_key', ''),
            'plan': {
                'id': str(plan.id),
                'name': plan.name,
                'tier': plan.tier,
                'interval': interval,
            },
            'breakdown': {
                'base_price': float(target_base_price),
                'discount_credit': float(breakdown['discount_amount']),
                'subtotal': float(breakdown['subtotal']),
                'tax_rate_percent': float(breakdown['tax_rate_percent']),
                'tax_amount': float(breakdown['tax_amount']),
                'cgst_amount': float(breakdown['cgst_amount']),
                'sgst_amount': float(breakdown['sgst_amount']),
                'igst_amount': float(breakdown['igst_amount']),
                'total_amount': float(breakdown['total_amount']),
            },
            'is_mock': gateway_order.get('is_mock', False),
        }

    @classmethod
    @transaction.atomic
    def verify_and_activate_payment(cls, practice, invoice_id, payment_data):
        """
        Verifies payment gateway signature and activates/upgrades subscription.
        """
        invoice = Invoice.objects.select_for_update().filter(id=invoice_id, practice=practice).first()
        if not invoice:
            raise ValidationError("Invoice not found for this practice.")

        if invoice.status == Invoice.STATUS_PAID:
            # Idempotent response if already paid
            return invoice, getattr(practice, 'subscription', None)

        gateway = get_payment_gateway(invoice.payment_gateway)
        order_id = payment_data.get('razorpay_order_id') or invoice.gateway_order_id
        payment_id = payment_data.get('razorpay_payment_id') or payment_data.get('payment_id')
        signature = payment_data.get('razorpay_signature') or payment_data.get('signature')

        if not payment_id:
            raise ValidationError("Missing payment ID.")

        is_valid = gateway.verify_payment_signature(
            order_id=order_id,
            payment_id=payment_id,
            signature=signature
        )

        safe_payload = json.loads(json.dumps(payment_data, default=str)) if payment_data else {}
        if not is_valid:
            PaymentTransaction.objects.create(
                invoice=invoice,
                practice=practice,
                gateway=invoice.payment_gateway,
                action=PaymentTransaction.ACTION_PAYMENT,
                amount=invoice.total_amount,
                currency=invoice.currency,
                gateway_order_id=order_id,
                gateway_payment_id=payment_id,
                status=PaymentTransaction.STATUS_FAILED,
                error_code='INVALID_SIGNATURE',
                error_description='Cryptographic signature verification failed.',
                raw_payload=safe_payload,
            )
            raise ValidationError("Payment signature verification failed. Untrusted payment.")

        now = timezone.now()
        period_duration_days = 365 if invoice.billing_interval == PracticeSubscription.INTERVAL_YEARLY else 30
        period_end = now + timedelta(days=period_duration_days)

        # Update invoice
        invoice.status = Invoice.STATUS_PAID
        invoice.gateway_payment_id = payment_id
        invoice.gateway_signature = signature or ''
        invoice.paid_at = now
        invoice.payment_method = payment_data.get('payment_method', 'online')
        invoice.period_start = now
        invoice.period_end = period_end
        invoice.save()

        # Record successful transaction
        PaymentTransaction.objects.create(
            invoice=invoice,
            practice=practice,
            gateway=invoice.payment_gateway,
            action=PaymentTransaction.ACTION_PAYMENT,
            amount=invoice.total_amount,
            currency=invoice.currency,
            gateway_order_id=order_id,
            gateway_payment_id=payment_id,
            status=PaymentTransaction.STATUS_SUCCESS,
            raw_payload=safe_payload,
        )

        # Update or create subscription
        subscription = getattr(practice, 'subscription', None)
        if not subscription:
            subscription = PracticeSubscription(practice=practice)

        subscription.plan = invoice.plan
        subscription.status = PracticeSubscription.STATUS_ACTIVE
        subscription.billing_interval = invoice.billing_interval
        subscription.current_period_start = now
        subscription.current_period_end = period_end
        subscription.auto_renew = True
        subscription.cancel_at_period_end = False
        subscription.cancelled_at = None
        subscription.cancellation_reason = ''
        subscription.grace_period_ends_at = None
        # Clear any pending scheduled downgrade upon fresh upgrade/payment
        subscription.scheduled_downgrade_plan = None
        subscription.scheduled_downgrade_interval = ''
        subscription.scheduled_downgrade_effective_date = None
        subscription.payment_gateway = invoice.payment_gateway
        subscription.save()

        logger.info(f"Successfully activated subscription for practice {practice.id} to {invoice.plan.name}")
        return invoice, subscription

    @classmethod
    def validate_downgrade_limits(cls, practice, target_plan):
        """
        Validates whether the practice's current active usage complies with target plan's quotas.
        If current usage exceeds target plan limits, raises detailed ValidationError.
        """
        # 1. Doctor limit check
        active_doctors = PracticeMembership.objects.filter(
            practice=practice,
            role__in=[PracticeMembership.ROLE_DOCTOR, PracticeMembership.ROLE_OWNER],
            is_active=True
        ).count()

        if target_plan.max_doctors != -1 and active_doctors > target_plan.max_doctors:
            excess = active_doctors - target_plan.max_doctors
            raise ValidationError(
                f"Cannot downgrade to '{target_plan.name}': Your practice currently has {active_doctors} active doctors, "
                f"but {target_plan.name} allows a maximum of {target_plan.max_doctors}. "
                f"Please deactivate or remove {excess} doctor(s) before downgrading."
            )

        # 2. Staff limit check
        active_staff = PracticeMembership.objects.filter(
            practice=practice,
            role=PracticeMembership.ROLE_STAFF,
            is_active=True
        ).count()

        if target_plan.max_staff != -1 and active_staff > target_plan.max_staff:
            excess = active_staff - target_plan.max_staff
            raise ValidationError(
                f"Cannot downgrade to '{target_plan.name}': Your practice currently has {active_staff} active staff accounts, "
                f"but {target_plan.name} allows a maximum of {target_plan.max_staff}. "
                f"Please remove {excess} staff account(s) before downgrading."
            )

        # 3. Location limit check
        try:
            from bookings.models import PracticeLocation
            active_locations = PracticeLocation.objects.filter(practice=practice, is_active=True).count()
            if target_plan.max_locations != -1 and active_locations > target_plan.max_locations:
                excess = active_locations - target_plan.max_locations
                raise ValidationError(
                    f"Cannot downgrade to '{target_plan.name}': Your practice currently has {active_locations} branch locations, "
                    f"but {target_plan.name} allows a maximum of {target_plan.max_locations}. "
                    f"Please deactivate {excess} location(s) before downgrading."
                )
        except ImportError:
            pass

        return True

    @classmethod
    def schedule_downgrade(cls, practice, target_plan_id, target_interval='monthly', immediate=False):
        """
        Schedules or immediately applies a plan downgrade.
        Performs quota validation first.
        """
        subscription = getattr(practice, 'subscription', None)
        if not subscription:
            raise ValidationError("Practice does not have an active subscription.")

        target_plan = SubscriptionPlan.objects.filter(id=target_plan_id, is_active=True).first()
        if not target_plan:
            raise ValidationError("Target plan does not exist or is inactive.")

        if target_plan.id == subscription.plan_id and target_interval == subscription.billing_interval:
            raise ValidationError("Your practice is already on this plan and billing cycle.")

        # Validate active resource counts against target quotas
        cls.validate_downgrade_limits(practice, target_plan)

        now = timezone.now()

        # If immediate downgrade requested OR if currently in free trial
        if immediate or subscription.status == PracticeSubscription.STATUS_TRIALING:
            subscription.plan = target_plan
            subscription.billing_interval = target_interval
            subscription.scheduled_downgrade_plan = None
            subscription.scheduled_downgrade_interval = ''
            subscription.scheduled_downgrade_effective_date = None
            subscription.save(update_fields=[
                'plan', 'billing_interval', 'scheduled_downgrade_plan',
                'scheduled_downgrade_interval', 'scheduled_downgrade_effective_date', 'updated_at'
            ])
            return {
                'mode': 'immediate',
                'plan': target_plan.name,
                'interval': target_interval,
                'effective_date': subscription.current_period_end.isoformat(),
                'message': f"Downgrade to '{target_plan.name}' applied immediately."
            }

        # Otherwise schedule downgrade for end of current paid billing period
        subscription.scheduled_downgrade_plan = target_plan
        subscription.scheduled_downgrade_interval = target_interval
        subscription.scheduled_downgrade_effective_date = subscription.current_period_end
        subscription.save(update_fields=[
            'scheduled_downgrade_plan', 'scheduled_downgrade_interval',
            'scheduled_downgrade_effective_date', 'updated_at'
        ])

        return {
            'mode': 'scheduled',
            'plan': target_plan.name,
            'interval': target_interval,
            'effective_date': subscription.current_period_end.isoformat(),
            'message': f"Downgrade to '{target_plan.name}' scheduled. You retain full access to your current plan until {subscription.current_period_end.strftime('%d %b %Y')}."
        }

    @classmethod
    def cancel_scheduled_downgrade(cls, practice):
        """Cancels a pending scheduled downgrade."""
        subscription = getattr(practice, 'subscription', None)
        if not subscription or not subscription.scheduled_downgrade_plan:
            raise ValidationError("No scheduled downgrade found to cancel.")

        prev_plan_name = subscription.scheduled_downgrade_plan.name
        subscription.scheduled_downgrade_plan = None
        subscription.scheduled_downgrade_interval = ''
        subscription.scheduled_downgrade_effective_date = None
        subscription.save(update_fields=[
            'scheduled_downgrade_plan', 'scheduled_downgrade_interval',
            'scheduled_downgrade_effective_date', 'updated_at'
        ])
        return {
            'message': f"Scheduled downgrade to '{prev_plan_name}' has been cancelled. Your current plan will renew normally."
        }

    @classmethod
    def cancel_subscription(cls, practice, reason='', immediate=False):
        """
        Cancels subscription.
        By default (immediate=False), subscription stays active until end of current paid cycle.
        """
        subscription = getattr(practice, 'subscription', None)
        if not subscription:
            raise ValidationError("No subscription found for this practice.")

        now = timezone.now()
        if immediate:
            subscription.status = PracticeSubscription.STATUS_CANCELLED
            subscription.auto_renew = False
            subscription.cancelled_at = now
            subscription.cancellation_reason = reason
            subscription.save()
            return {
                'mode': 'immediate',
                'status': 'cancelled',
                'message': 'Subscription has been cancelled immediately.'
            }

        subscription.cancel_at_period_end = True
        subscription.auto_renew = False
        subscription.cancellation_reason = reason
        subscription.save(update_fields=['cancel_at_period_end', 'auto_renew', 'cancellation_reason', 'updated_at'])
        return {
            'mode': 'period_end',
            'status': subscription.status,
            'effective_date': subscription.current_period_end.isoformat(),
            'message': f"Subscription auto-renew turned off. Access remains active until {subscription.current_period_end.strftime('%d %b %Y')}."
        }

    @classmethod
    def renew_subscription(cls, subscription):
        """
        Processes renewal when subscription period end arrives.
        Executes scheduled downgrades if present.
        """
        practice = subscription.practice
        now = timezone.now()

        # If a scheduled downgrade is due, apply it!
        if subscription.scheduled_downgrade_plan:
            logger.info(f"Applying scheduled downgrade to {subscription.scheduled_downgrade_plan.name} on renewal")
            subscription.plan = subscription.scheduled_downgrade_plan
            if subscription.scheduled_downgrade_interval:
                subscription.billing_interval = subscription.scheduled_downgrade_interval
            subscription.scheduled_downgrade_plan = None
            subscription.scheduled_downgrade_interval = ''
            subscription.scheduled_downgrade_effective_date = None

        interval = subscription.billing_interval
        duration_days = 365 if interval == PracticeSubscription.INTERVAL_YEARLY else 30
        new_start = subscription.current_period_end
        new_end = new_start + timedelta(days=duration_days)

        subscription.current_period_start = new_start
        subscription.current_period_end = new_end
        subscription.status = PracticeSubscription.STATUS_ACTIVE
        subscription.grace_period_ends_at = None
        subscription.save()

        # Generate Renewal Invoice
        target_price = subscription.plan.get_price(interval)
        breakdown = calculate_invoice_breakdown(base_amount=target_price, practice=practice)

        invoice = Invoice.objects.create(
            practice=practice,
            subscription=subscription,
            plan=subscription.plan,
            plan_snapshot_name=subscription.plan.name,
            billing_interval=interval,
            period_start=new_start,
            period_end=new_end,
            subtotal=breakdown['subtotal'],
            discount_amount=breakdown['discount_amount'],
            tax_rate_percent=breakdown['tax_rate_percent'],
            tax_amount=breakdown['tax_amount'],
            cgst_amount=breakdown['cgst_amount'],
            sgst_amount=breakdown['sgst_amount'],
            igst_amount=breakdown['igst_amount'],
            total_amount=breakdown['total_amount'],
            currency=subscription.plan.currency,
            status=Invoice.STATUS_PAID,  # Marked paid for recurring auto-charge
            paid_at=now,
            payment_gateway=subscription.payment_gateway,
            payment_method='recurring_auto_debit',
            line_items=[{
                'description': f"ClinicRise {subscription.plan.name} Renewal ({interval.title()})",
                'period_desc': f"{new_start.strftime('%d %b %Y')} to {new_end.strftime('%d %b %Y')}",
                'sac_code': CLINICRISE_LEGAL_ENTITY['sac_code'],
                'quantity': 1,
                'unit_price': str(target_price),
                'amount': str(target_price),
            }],
            billing_party_details=build_billing_party_details(practice),
            issuer_party_details=CLINICRISE_LEGAL_ENTITY,
            notes="Automatic subscription renewal charge.",
        )

        PaymentTransaction.objects.create(
            invoice=invoice,
            practice=practice,
            gateway=subscription.payment_gateway,
            action=PaymentTransaction.ACTION_RENEWAL,
            amount=invoice.total_amount,
            currency=invoice.currency,
            status=PaymentTransaction.STATUS_SUCCESS,
        )

        return subscription, invoice

    @classmethod
    def process_expired_subscriptions(cls):
        """
        Background job/cron:
        - Handles subscriptions whose current_period_end has passed
        - Transitions to cancelled, expired, or past_due with grace period
        """
        now = timezone.now()
        grace_days = int(getattr(settings, 'BILLING_GRACE_PERIOD_DAYS', 5))
        stats = {'renewed': 0, 'grace_period': 0, 'expired': 0, 'cancelled': 0}

        # 1. Expire past_due subscriptions whose grace period has lapsed
        expired_past_due = PracticeSubscription.objects.filter(
            status=PracticeSubscription.STATUS_PAST_DUE,
            grace_period_ends_at__lte=now
        )
        for sub in expired_past_due:
            sub.status = PracticeSubscription.STATUS_UNPAID
            sub.save(update_fields=['status', 'updated_at'])
            stats['expired'] += 1

        # 2. Subscriptions reaching period end
        expired_active = PracticeSubscription.objects.filter(
            status__in=[PracticeSubscription.STATUS_ACTIVE, PracticeSubscription.STATUS_TRIALING],
            current_period_end__lte=now
        )

        for sub in expired_active:
            if sub.cancel_at_period_end:
                sub.status = PracticeSubscription.STATUS_CANCELLED
                sub.cancelled_at = now
                sub.save(update_fields=['status', 'cancelled_at', 'updated_at'])
                stats['cancelled'] += 1
            elif sub.status == PracticeSubscription.STATUS_TRIALING:
                sub.status = PracticeSubscription.STATUS_EXPIRED
                sub.save(update_fields=['status', 'updated_at'])
                stats['expired'] += 1
            elif sub.auto_renew:
                # If auto-renew is on, either renew or enter grace period
                # In real recurring gateway, gateway triggers subscription.charged webhook.
                # If webhook didn't arrive, grant grace period
                sub.status = PracticeSubscription.STATUS_PAST_DUE
                sub.grace_period_ends_at = now + timedelta(days=grace_days)
                sub.save(update_fields=['status', 'grace_period_ends_at', 'updated_at'])
                stats['grace_period'] += 1
            else:
                sub.status = PracticeSubscription.STATUS_EXPIRED
                sub.save(update_fields=['status', 'updated_at'])
                stats['expired'] += 1

        return stats

    @classmethod
    @transaction.atomic
    def handle_webhook_event(cls, gateway_name, event_type, event_id, payload, headers=None):
        """
        Idempotent Webhook event dispatcher.
        Prevents duplicate execution using WebhookEvent database table.
        """
        existing = WebhookEvent.objects.filter(event_id=event_id).first()
        if existing and existing.status == WebhookEvent.STATUS_PROCESSED:
            logger.info(f"Duplicate webhook {event_id} ignored (already processed).")
            return existing

        event_record, _ = WebhookEvent.objects.get_or_create(
            event_id=event_id,
            defaults={
                'gateway': gateway_name,
                'event_type': event_type,
                'status': WebhookEvent.STATUS_RECEIVED,
                'payload': payload,
                'headers': headers or {},
            }
        )

        try:
            if event_type in ['payment.captured', 'payment.authorized']:
                # Extract payment entity
                payment_entity = payload.get('payload', {}).get('payment', {}).get('entity', payload.get('payment', {}))
                order_id = payment_entity.get('order_id')
                payment_id = payment_entity.get('id')
                method = payment_entity.get('method', 'online')

                if order_id:
                    invoice = Invoice.objects.filter(gateway_order_id=order_id).first()
                    if invoice and invoice.status != Invoice.STATUS_PAID:
                        cls.verify_and_activate_payment(
                            practice=invoice.practice,
                            invoice_id=invoice.id,
                            payment_data={
                                'razorpay_order_id': order_id,
                                'razorpay_payment_id': payment_id,
                                'razorpay_signature': 'mock_sig_webhook',
                                'payment_method': method,
                            }
                        )

            elif event_type == 'payment.failed':
                payment_entity = payload.get('payload', {}).get('payment', {}).get('entity', payload.get('payment', {}))
                order_id = payment_entity.get('order_id')
                error_desc = payment_entity.get('error_description', 'Payment failed')

                if order_id:
                    invoice = Invoice.objects.filter(gateway_order_id=order_id).first()
                    if invoice:
                        PaymentTransaction.objects.create(
                            invoice=invoice,
                            practice=invoice.practice,
                            gateway=gateway_name,
                            action=PaymentTransaction.ACTION_PAYMENT,
                            amount=invoice.total_amount,
                            currency=invoice.currency,
                            gateway_order_id=order_id,
                            status=PaymentTransaction.STATUS_FAILED,
                            error_description=error_desc,
                            raw_payload=payload,
                        )

            elif event_type in ['subscription.charged', 'invoice.paid']:
                sub_entity = payload.get('payload', {}).get('subscription', {}).get('entity', {})
                gateway_sub_id = sub_entity.get('id')
                if gateway_sub_id:
                    sub = PracticeSubscription.objects.filter(gateway_subscription_id=gateway_sub_id).first()
                    if sub:
                        cls.renew_subscription(sub)

            elif event_type in ['subscription.cancelled', 'subscription.halted']:
                sub_entity = payload.get('payload', {}).get('subscription', {}).get('entity', {})
                gateway_sub_id = sub_entity.get('id')
                if gateway_sub_id:
                    sub = PracticeSubscription.objects.filter(gateway_subscription_id=gateway_sub_id).first()
                    if sub:
                        sub.status = PracticeSubscription.STATUS_CANCELLED
                        sub.save(update_fields=['status', 'updated_at'])

            event_record.status = WebhookEvent.STATUS_PROCESSED
            event_record.processed_at = timezone.now()
            event_record.save()
            return event_record

        except Exception as e:
            logger.exception(f"Error processing webhook event {event_id}: {str(e)}")
            event_record.status = WebhookEvent.STATUS_FAILED
            event_record.error_message = str(e)
            event_record.save()
            raise

import json
import uuid
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from billing.models import (
    Invoice,
    PaymentTransaction,
    PracticeSubscription,
    SubscriptionPlan,
    WebhookEvent,
)
from billing.services.billing_service import BillingService
from billing.services.gateway import RazorpayGateway
from billing.services.invoice_generator import calculate_invoice_breakdown
from practices.models import Practice, PracticeMembership

User = get_user_model()


class BillingSystemTestCase(TestCase):
    """
    Comprehensive test suite for ClinicRise Subscription Billing:
    - Plans & pricing
    - Trial auto-provisioning
    - GST & Invoice breakdown
    - Checkout session generation
    - Signature verification & activation
    - Prorated upgrades
    - Usage-checked downgrades
    - Cancellation & Renewals
    - Webhooks & Idempotency
    - API Endpoints
    """

    def setUp(self):
        self.client = APIClient()

        # Create Doctor / Practice Owner User
        self.owner = User.objects.create_user(
            email='dr.rajesh@clinicrise.com',
            phone_number='+919876543210',
            full_name='Dr. Rajesh Sharma',
            is_active=True,
        )

        # Create Practice Tenant
        self.practice = Practice.objects.create(
            name='Apollo Dental Care',
            owner=self.owner,
            state='Telangana',
            city='Hyderabad',
            country='India',
            currency='INR',
            gst_number='36ABCDE1234F1Z5',
        )

        self.membership = PracticeMembership.objects.create(
            practice=self.practice,
            user=self.owner,
            role=PracticeMembership.ROLE_OWNER,
            is_active=True,
        )

        # Create or update standard plans
        self.trial_plan, _ = SubscriptionPlan.objects.update_or_create(
            slug='free-trial',
            defaults={
                'name': '14-Day Free Trial',
                'tier': SubscriptionPlan.TIER_TRIAL,
                'monthly_price': Decimal('0.00'),
                'yearly_price': Decimal('0.00'),
                'trial_days': 14,
                'max_doctors': 1,
                'max_staff': 2,
                'max_locations': 1,
                'max_appointments_per_month': 50,
                'is_active': True,
                'is_public': False,
                'is_default_trial': True,
            }
        )

        self.starter_plan, _ = SubscriptionPlan.objects.update_or_create(
            slug='solo-starter',
            defaults={
                'name': 'Solo Practitioner',
                'tier': SubscriptionPlan.TIER_STARTER,
                'monthly_price': Decimal('1499.00'),
                'yearly_price': Decimal('14990.00'),
                'yearly_discount_percent': 17,
                'currency': 'INR',
                'trial_days': 0,
                'max_doctors': 1,
                'max_staff': 3,
                'max_locations': 1,
                'max_appointments_per_month': 250,
                'teleconsultation_enabled': True,
                'sms_reminders_enabled': True,
                'is_active': True,
                'is_public': True,
            }
        )

        self.growth_plan, _ = SubscriptionPlan.objects.update_or_create(
            slug='growth-polyclinic',
            defaults={
                'name': 'Growth Polyclinic',
                'tier': SubscriptionPlan.TIER_GROWTH,
                'monthly_price': Decimal('3999.00'),
                'yearly_price': Decimal('39990.00'),
                'yearly_discount_percent': 17,
                'currency': 'INR',
                'trial_days': 0,
                'max_doctors': 5,
                'max_staff': 10,
                'max_locations': 2,
                'max_appointments_per_month': 1000,
                'custom_domain_enabled': True,
                'teleconsultation_enabled': True,
                'whatsapp_notifications_enabled': True,
                'is_active': True,
                'is_public': True,
            }
        )

        # Authenticate client
        self.client.force_authenticate(user=self.owner)
        self.headers = {'HTTP_X_PRACTICE_ID': str(self.practice.id)}

    def test_trial_auto_provisioning(self):
        """Test that free trial is initialized correctly for practice."""
        subscription = BillingService.create_trial_subscription(self.practice)
        self.assertIsNotNone(subscription)
        self.assertEqual(subscription.status, PracticeSubscription.STATUS_TRIALING)
        self.assertEqual(subscription.plan, self.trial_plan)
        self.assertTrue(subscription.is_in_trial)
        self.assertTrue(subscription.is_active_access)
        self.assertGreaterEqual(subscription.days_remaining, 13)

    def test_gst_invoice_breakdown_intra_state(self):
        """Test Indian GST 18% calculation (CGST 9% + SGST 9%) for Telangana practice."""
        breakdown = calculate_invoice_breakdown(
            base_amount=Decimal('1000.00'),
            discount_amount=Decimal('0.00'),
            practice=self.practice
        )
        self.assertEqual(breakdown['subtotal'], Decimal('1000.00'))
        self.assertEqual(breakdown['cgst_amount'], Decimal('90.00'))
        self.assertEqual(breakdown['sgst_amount'], Decimal('90.00'))
        self.assertEqual(breakdown['igst_amount'], Decimal('0.00'))
        self.assertEqual(breakdown['tax_amount'], Decimal('180.00'))
        self.assertEqual(breakdown['total_amount'], Decimal('1180.00'))

    def test_gst_invoice_breakdown_inter_state(self):
        """Test Indian GST 18% calculation (IGST 18%) for out-of-state practice (e.g. Maharashtra)."""
        practice_mh = Practice.objects.create(
            name='Mumbai Dental Studio',
            owner=self.owner,
            state='Maharashtra',
            country='India',
        )
        breakdown = calculate_invoice_breakdown(
            base_amount=Decimal('1000.00'),
            discount_amount=Decimal('0.00'),
            practice=practice_mh
        )
        self.assertEqual(breakdown['subtotal'], Decimal('1000.00'))
        self.assertEqual(breakdown['cgst_amount'], Decimal('0.00'))
        self.assertEqual(breakdown['sgst_amount'], Decimal('0.00'))
        self.assertEqual(breakdown['igst_amount'], Decimal('180.00'))
        self.assertEqual(breakdown['tax_amount'], Decimal('180.00'))
        self.assertEqual(breakdown['total_amount'], Decimal('1180.00'))

    def test_checkout_api_and_order_creation(self):
        """Test POST /api/billing/checkout/ creates open invoice and order payload."""
        response = self.client.post(
            '/api/billing/checkout/',
            data={'plan_id': str(self.starter_plan.id), 'interval': 'monthly'},
            format='json',
            **self.headers
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('invoice_id', data)
        self.assertIn('order_id', data)
        self.assertIn('amount', data)
        self.assertEqual(data['currency'], 'INR')

        invoice = Invoice.objects.get(id=data['invoice_id'])
        self.assertEqual(invoice.status, Invoice.STATUS_OPEN)
        self.assertEqual(invoice.plan, self.starter_plan)
        self.assertGreater(invoice.total_amount, Decimal('0.00'))

    def test_payment_verification_and_activation(self):
        """Test verifying signature activates subscription and marks invoice paid."""
        # Initiate checkout
        checkout = BillingService.initiate_checkout(
            practice=self.practice,
            plan_id=self.starter_plan.id,
            interval='monthly',
            user=self.owner
        )
        invoice_id = checkout['invoice_id']
        order_id = checkout['order_id']

        # Verify payment with valid mock signature
        response = self.client.post(
            '/api/billing/verify-payment/',
            data={
                'invoice_id': invoice_id,
                'razorpay_order_id': order_id,
                'razorpay_payment_id': 'pay_test_12345678',
                'razorpay_signature': 'mock_sig_valid',
                'payment_method': 'upi',
            },
            format='json',
            **self.headers
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        invoice = Invoice.objects.get(id=invoice_id)
        self.assertEqual(invoice.status, Invoice.STATUS_PAID)
        self.assertEqual(invoice.gateway_payment_id, 'pay_test_12345678')

        sub = PracticeSubscription.objects.get(practice=self.practice)
        self.assertEqual(sub.status, PracticeSubscription.STATUS_ACTIVE)
        self.assertEqual(sub.plan, self.starter_plan)
        self.assertTrue(sub.is_active_access)

    def test_prorated_upgrade_discount(self):
        """Test that mid-period upgrade applies unused credit from current paid plan."""
        PracticeSubscription.objects.filter(practice=self.practice).delete()
        # Set practice currently on Starter plan with 15 days remaining
        now = timezone.now()
        sub = PracticeSubscription.objects.create(
            practice=self.practice,
            plan=self.starter_plan,
            status=PracticeSubscription.STATUS_ACTIVE,
            billing_interval='monthly',
            current_period_start=now - timedelta(days=15),
            current_period_end=now + timedelta(days=15),
        )

        checkout = BillingService.initiate_checkout(
            practice=self.practice,
            plan_id=self.growth_plan.id,
            interval='monthly',
            user=self.owner
        )

        breakdown = checkout['breakdown']
        self.assertGreater(breakdown['discount_credit'], 0)
        self.assertEqual(breakdown['base_price'], 3999.00)
        # Net subtotal is less than full 3999 base price
        self.assertLess(breakdown['subtotal'], 3999.00)

    def test_downgrade_validation_blocks_when_quota_exceeded(self):
        """Test that downgrade is rejected if current doctor count exceeds target plan limit."""
        PracticeSubscription.objects.filter(practice=self.practice).delete()
        # Set practice on Growth plan (allows 5 doctors)
        sub = PracticeSubscription.objects.create(
            practice=self.practice,
            plan=self.growth_plan,
            status=PracticeSubscription.STATUS_ACTIVE,
            billing_interval='monthly',
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=20),
        )

        # Add 2 more doctors to practice (total 3 doctors: owner + 2 doctors)
        for i in range(2):
            doc_user = User.objects.create_user(
                email=f'doc_{i}@clinicrise.com',
                phone_number=f'+9198765432{11+i}',
                full_name=f'Doctor {i}',
                is_active=True,
            )
            PracticeMembership.objects.create(
                practice=self.practice,
                user=doc_user,
                role=PracticeMembership.ROLE_DOCTOR,
                is_active=True,
            )

        # Attempt to downgrade to Starter Plan (allows max 1 doctor)
        response = self.client.post(
            '/api/billing/downgrade/',
            data={'target_plan_id': str(self.starter_plan.id), 'target_interval': 'monthly'},
            format='json',
            **self.headers
        )
        # Must fail with validation error explaining excess doctors
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('allows a maximum of 1', str(response.json()))

    def test_downgrade_schedules_at_period_end(self):
        """Test that valid downgrade schedules for current_period_end."""
        PracticeSubscription.objects.filter(practice=self.practice).delete()
        sub = PracticeSubscription.objects.create(
            practice=self.practice,
            plan=self.growth_plan,
            status=PracticeSubscription.STATUS_ACTIVE,
            billing_interval='monthly',
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=20),
        )

        # With only 1 doctor (owner), downgrade to Starter is valid
        response = self.client.post(
            '/api/billing/downgrade/',
            data={'target_plan_id': str(self.starter_plan.id), 'target_interval': 'monthly'},
            format='json',
            **self.headers
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['mode'], 'scheduled')

        sub.refresh_from_db()
        self.assertEqual(sub.scheduled_downgrade_plan, self.starter_plan)
        self.assertEqual(sub.plan, self.growth_plan)  # Retains growth plan until period end

        # Cancel scheduled downgrade
        cancel_resp = self.client.post(
            '/api/billing/cancel-downgrade/',
            format='json',
            **self.headers
        )
        self.assertEqual(cancel_resp.status_code, status.HTTP_200_OK)
        sub.refresh_from_db()
        self.assertIsNone(sub.scheduled_downgrade_plan)

    def test_cancellation_and_period_end(self):
        """Test cancelling subscription retains access until period end."""
        PracticeSubscription.objects.filter(practice=self.practice).delete()
        sub = PracticeSubscription.objects.create(
            practice=self.practice,
            plan=self.starter_plan,
            status=PracticeSubscription.STATUS_ACTIVE,
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=10),
            auto_renew=True,
        )

        response = self.client.post(
            '/api/billing/cancel/',
            data={'reason': 'Moving clinic location', 'immediate': False},
            format='json',
            **self.headers
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        sub.refresh_from_db()
        self.assertTrue(sub.cancel_at_period_end)
        self.assertFalse(sub.auto_renew)
        self.assertTrue(sub.is_active_access)  # Still active until period end

    def test_webhook_payment_captured_and_idempotency(self):
        """Test Razorpay payment.captured webhook activates invoice and duplicate is ignored."""
        checkout = BillingService.initiate_checkout(
            practice=self.practice,
            plan_id=self.starter_plan.id,
            interval='monthly',
            user=self.owner
        )
        invoice = Invoice.objects.get(id=checkout['invoice_id'])

        payload = {
            'event': 'payment.captured',
            'event_id': f'evt_test_{uuid.uuid4().hex[:12]}',
            'payload': {
                'payment': {
                    'entity': {
                        'id': 'pay_webhook_test_999',
                        'order_id': checkout['order_id'],
                        'amount': int(invoice.total_amount * 100),
                        'currency': 'INR',
                        'status': 'captured',
                        'method': 'upi',
                    }
                }
            }
        }

        # First webhook call
        response = self.client.post(
            '/api/billing/webhooks/razorpay/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE='mock_sig_test'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.STATUS_PAID)

        # Duplicate webhook call with same event_id must return 200 without error
        dup_resp = self.client.post(
            '/api/billing/webhooks/razorpay/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE='mock_sig_test'
        )
        self.assertEqual(dup_resp.status_code, status.HTTP_200_OK)

    def test_invoice_receipt_html(self):
        """Test GET /api/billing/invoices/<id>/receipt/ returns printable HTML."""
        checkout = BillingService.initiate_checkout(
            practice=self.practice,
            plan_id=self.starter_plan.id,
            interval='monthly',
            user=self.owner
        )
        invoice_id = checkout['invoice_id']

        response = self.client.get(
            f'/api/billing/invoices/{invoice_id}/receipt/',
            **self.headers
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(b'TAX INVOICE', response.content)
        self.assertIn(b'Apollo Dental Care', response.content)
        self.assertIn(b'ClinicRise', response.content)

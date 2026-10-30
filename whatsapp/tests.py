import uuid
from datetime import date, time, timedelta
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from practices.models import DoctorProfile, DoctorSchedule, Practice, PracticeMembership
from bookings.models import BookingRequest, DoctorSessionCapacity, PracticeLocation
from leads.models import Lead
from security.models import ConsentRecord

from whatsapp.models import (
    WhatsAppConfig,
    WhatsAppTemplate,
    WhatsAppOptOut,
    WhatsAppReminder,
    WhatsAppMessageLog,
    normalize_phone_number,
)
from whatsapp.services.template_service import WhatsAppTemplateService
from whatsapp.services.opt_out_service import WhatsAppOptOutService
from whatsapp.services.message_service import WhatsAppMessageService
from whatsapp.services.reminder_service import WhatsAppReminderService
from whatsapp.services.webhook_service import WhatsAppWebhookService

User = get_user_model()


class WhatsAppAutomationTestCase(APITestCase):
    """
    Comprehensive test suite for ClinicRise WhatsApp Automation:
    - Confirmation templates
    - Scheduled reminders queue
    - Opt-outs and consent compliance
    - Message logs and delivery receipts
    - Meta WhatsApp Webhooks
    - Management APIs and Analytics
    """

    def setUp(self):
        # 1. Setup Practice Owner & Doctor
        self.owner = User.objects.create_user(
            email='dr.rajesh@apollohyd.com',
            phone_number='+919876543210',
            first_name='Rajesh',
            last_name='Sharma',
            is_email_verified=True,
            is_phone_verified=True
        )

        self.practice = Practice.objects.create(
            name='Apollo Dental & Orthodontics',
            slug='apollo-dental-hyd',
            owner=self.owner,
            clinic_type='dental_clinic',
            phone_number='+919876543210',
            email='care@apollohyd.com',
            address='Road No 36, Jubilee Hills, Hyderabad',
            city='Hyderabad',
            state='Telangana'
        )

        self.membership = PracticeMembership.objects.create(
            practice=self.practice,
            user=self.owner,
            role=PracticeMembership.ROLE_OWNER,
            is_active=True
        )

        self.doctor_profile = DoctorProfile.objects.create(
            user=self.owner,
            title='Dr.',
            specialization='Orthodontist',
            qualifications='BDS, MDS',
            experience_years=12,
            is_verified=True
        )

        self.location = PracticeLocation.objects.create(
            practice=self.practice,
            name='Jubilee Hills Main Clinic',
            code='JH-01',
            address='Road No 36, Jubilee Hills, Hyderabad',
            google_maps_url='https://maps.google.com/?q=Apollo+Dental',
            is_primary=True
        )

        # Doctor Schedules for all 7 days of the week
        for dow in range(7):
            DoctorSchedule.objects.create(
                practice=self.practice,
                doctor=self.doctor_profile,
                day_of_week=dow,
                session_name="General OPD",
                start_time=time(8, 0),
                end_time=time(20, 0),
                slot_duration_minutes=15,
                is_active=True
            )

        DoctorSessionCapacity.objects.create(
            practice=self.practice,
            doctor=self.doctor_profile,
            session_name="Morning General OPD",
            booking_mode=DoctorSessionCapacity.MODE_TOKEN,
            max_tokens_per_session=50
        )

        # 2. WhatsApp Configuration
        self.config = WhatsAppMessageService.get_or_create_config(self.practice)
        self.config.provider = WhatsAppConfig.PROVIDER_MOCK
        self.config.display_phone_number = '+919876543210'
        self.config.save()

        # Seed templates
        WhatsAppTemplateService.seed_default_templates(self.practice)

        # Authenticate client
        self.client.force_authenticate(user=self.owner)
        self.auth_headers = {'HTTP_X_PRACTICE_ID': str(self.practice.id)}

    # =================================================================
    # 1. Template Engine Tests
    # =================================================================

    def test_seed_default_templates(self):
        """Verifies default clinical templates are seeded with correct variables and categories."""
        templates = WhatsAppTemplate.objects.filter(practice=self.practice)
        self.assertGreaterEqual(templates.count(), 8)

        slot_tpl = templates.filter(template_name='appointment_confirmation_slot').first()
        self.assertIsNotNone(slot_tpl)
        self.assertEqual(slot_tpl.category, WhatsAppTemplate.CATEGORY_UTILITY)
        self.assertIn("{{1}}", slot_tpl.body_text)
        self.assertIn("STOP", slot_tpl.footer_text)

        token_tpl = templates.filter(template_name='appointment_confirmation_token').first()
        self.assertIsNotNone(token_tpl)
        self.assertIn("Token Number", token_tpl.body_text)

        review_tpl = templates.filter(template_name='post_visit_review_request').first()
        self.assertIsNotNone(review_tpl)
        self.assertEqual(review_tpl.category, WhatsAppTemplate.CATEGORY_MARKETING)

    def test_render_template_dynamic_substitutions(self):
        """Tests parameter replacement in clinical template."""
        tpl = WhatsAppTemplate.objects.get(
            practice=self.practice,
            template_name='appointment_confirmation_slot'
        )

        context = {
            "patient_name": "Meera Nambiar",
            "doctor_name": "Dr. Rajesh Sharma",
            "appointment_date": "Wednesday, 28 Oct 2026",
            "start_time": "10:30 AM",
            "clinic_name": "Apollo Dental",
            "clinic_address": "Jubilee Hills",
            "booking_reference": "CR-202610-8F9A"
        }

        rendered, resolved = WhatsAppTemplateService.render_template(tpl, context)
        self.assertIn("Hello Meera Nambiar", rendered)
        self.assertIn("Dr. Rajesh Sharma", rendered)
        self.assertIn("Wednesday, 28 Oct 2026 at 10:30 AM", rendered)
        self.assertIn("CR-202610-8F9A", rendered)
        self.assertNotIn("{{1}}", rendered)

    # =================================================================
    # 2. Opt-Out & Consent Compliance Tests
    # =================================================================

    def test_register_opt_out_and_block_messaging(self):
        """Opted-out patients must be completely blocked from outbound WhatsApp messages."""
        patient_phone = "+919988776655"

        # 1. Register opt-out
        opt_record = WhatsAppOptOutService.register_opt_out(
            practice=self.practice,
            phone_number=patient_phone,
            reason=WhatsAppOptOut.REASON_KEYWORD_STOP,
            patient_name="Ananya Roy"
        )

        self.assertTrue(opt_record.is_opted_out)
        self.assertTrue(WhatsAppOptOutService.is_opted_out(self.practice, patient_phone))

        # 2. Check Security Consent Record sync
        withdrawn_consent = ConsentRecord.objects.filter(
            practice=self.practice,
            patient_identifier=patient_phone,
            consent_type=ConsentRecord.TYPE_WHATSAPP_NOTIFICATIONS,
            status=ConsentRecord.STATUS_WITHDRAWN
        ).exists()
        self.assertTrue(withdrawn_consent)

        # 3. Attempt message dispatch - MUST be blocked
        msg_log = WhatsAppMessageService.send_template_message(
            practice=self.practice,
            recipient_phone=patient_phone,
            template_name='appointment_reminder_24h',
            context={"patient_name": "Ananya Roy"}
        )

        self.assertEqual(msg_log.status, WhatsAppMessageLog.STATUS_BLOCKED_OPT_OUT)
        self.assertEqual(msg_log.error_code, "RECIPIENT_OPTED_OUT")
        self.assertIn("Opt-Out Registry", msg_log.message_body)

    def test_re_opt_in_restores_messaging(self):
        """Testing keyword START / re-opt-in restores delivery capability."""
        patient_phone = "+919988776655"

        # Opt out first
        WhatsAppOptOutService.register_opt_out(self.practice, patient_phone)
        self.assertTrue(WhatsAppOptOutService.is_opted_out(self.practice, patient_phone))

        # Opt back in
        WhatsAppOptOutService.register_opt_in(self.practice, patient_phone, patient_name="Ananya Roy")
        self.assertFalse(WhatsAppOptOutService.is_opted_out(self.practice, patient_phone))

        # Outbound message should succeed now
        msg_log = WhatsAppMessageService.send_template_message(
            practice=self.practice,
            recipient_phone=patient_phone,
            template_name='appointment_reminder_24h',
            context={"patient_name": "Ananya Roy", "clinic_name": "Apollo Dental"}
        )
        self.assertEqual(msg_log.status, WhatsAppMessageLog.STATUS_SENT)

    def test_keyword_detection(self):
        """Tests inbound stop and start keyword categorization."""
        self.assertEqual(WhatsAppOptOutService.detect_keyword("STOP"), 'opt_out')
        self.assertEqual(WhatsAppOptOutService.detect_keyword("stop!"), 'opt_out')
        self.assertEqual(WhatsAppOptOutService.detect_keyword("unsubscribe"), 'opt_out')
        self.assertEqual(WhatsAppOptOutService.detect_keyword("cancel"), 'opt_out')
        self.assertEqual(WhatsAppOptOutService.detect_keyword("START"), 'opt_in')
        self.assertEqual(WhatsAppOptOutService.detect_keyword("unstop"), 'opt_in')
        self.assertIsNone(WhatsAppOptOutService.detect_keyword("What are the clinic timings?"))

    # =================================================================
    # 3. Booking Confirmation & Lifecycle Reminders Tests
    # =================================================================

    def test_booking_confirmation_triggers_whatsapp_and_reminders(self):
        """Confirming an appointment automatically sends WhatsApp message and schedules 24h & 2h reminders."""
        future_date = (timezone.now() + timedelta(days=2)).date()

        booking = BookingRequest.objects.create(
            practice=self.practice,
            doctor=self.doctor_profile,
            location=self.location,
            patient_name="Pooja Hegde",
            phone_number="+919123456789",
            preferred_date=future_date,
            booking_mode=BookingRequest.SCHEDULING_MODE_SLOT,
            start_time=time(14, 0),
            end_time=time(14, 30)
        )

        # Trigger confirmation
        from bookings.services.booking_service import BookingService
        BookingService.confirm_booking(booking=booking, user=self.owner)

        # Check Outbound Message Log
        confirmation_msg = WhatsAppMessageLog.objects.filter(
            practice=self.practice,
            booking=booking,
            template_name='appointment_confirmation_slot'
        ).first()

        self.assertIsNotNone(confirmation_msg)
        self.assertEqual(confirmation_msg.status, WhatsAppMessageLog.STATUS_SENT)
        self.assertIn("Pooja Hegde", confirmation_msg.message_body)
        self.assertIn(booking.booking_reference, confirmation_msg.message_body)

        # Check Reminders Scheduled
        reminders = WhatsAppReminder.objects.filter(booking=booking, status=WhatsAppReminder.STATUS_PENDING)
        self.assertEqual(reminders.count(), 2)

        rem_types = set(reminders.values_list('reminder_type', flat=True))
        self.assertIn(WhatsAppReminder.TYPE_APPT_24H, rem_types)
        self.assertIn(WhatsAppReminder.TYPE_APPT_2H, rem_types)

    def test_token_mode_booking_confirmation(self):
        """Session / Token mode booking issues token number and session name in WhatsApp template."""
        future_date = (timezone.now() + timedelta(days=3)).date()

        booking = BookingRequest.objects.create(
            practice=self.practice,
            doctor=self.doctor_profile,
            location=self.location,
            patient_name="Vikram Seth",
            phone_number="+919811223344",
            preferred_date=future_date,
            booking_mode=BookingRequest.SCHEDULING_MODE_TOKEN,
            session_name="Morning General OPD",
            token_number=18,
            estimated_arrival_time=time(10, 45)
        )

        from bookings.services.booking_service import BookingService
        BookingService.confirm_booking(
            booking=booking,
            user=self.owner,
            token_number=18,
            session_name="Morning General OPD"
        )

        token_msg = WhatsAppMessageLog.objects.filter(
            practice=self.practice,
            booking=booking,
            template_name='appointment_confirmation_token'
        ).first()

        self.assertIsNotNone(token_msg)
        self.assertIn("#18", token_msg.message_body)
        self.assertIn("Morning General OPD", token_msg.message_body)

    def test_reschedule_and_cancellation_whatsapp_notices(self):
        """Rescheduling and cancelling an appointment dispatches appropriate notices."""
        future_date = (timezone.now() + timedelta(days=2)).date()
        booking = BookingRequest.objects.create(
            practice=self.practice,
            doctor=self.doctor_profile,
            location=self.location,
            patient_name="Siddharth Rao",
            phone_number="+919776655443",
            preferred_date=future_date,
            booking_mode=BookingRequest.SCHEDULING_MODE_SLOT,
            start_time=time(11, 0),
            status=BookingRequest.STATUS_CONFIRMED,
            appointment_date=future_date
        )

        from bookings.services.booking_service import BookingService

        # 1. Reschedule
        new_date = (timezone.now() + timedelta(days=4)).date()
        BookingService.reschedule_booking(
            booking=booking,
            user=self.owner,
            new_date=new_date,
            new_start_time=time(16, 0)
        )

        resched_msg = WhatsAppMessageLog.objects.filter(
            booking=booking,
            template_name='appointment_rescheduled'
        ).first()
        self.assertIsNotNone(resched_msg)
        self.assertEqual(resched_msg.status, WhatsAppMessageLog.STATUS_SENT)

        # 2. Cancel
        BookingService.cancel_booking(booking=booking, user=self.owner, reason="Patient travelling out of town")
        cancel_msg = WhatsAppMessageLog.objects.filter(
            booking=booking,
            template_name='appointment_cancelled'
        ).first()
        self.assertIsNotNone(cancel_msg)
        self.assertIn("Patient travelling out of town", cancel_msg.message_body)

        # Reminders should be cancelled
        pending_rems = WhatsAppReminder.objects.filter(booking=booking, status=WhatsAppReminder.STATUS_PENDING)
        self.assertEqual(pending_rems.count(), 0)

    def test_completed_visit_schedules_google_review_request(self):
        """Marking a visit completed schedules a Google review reminder."""
        today = timezone.now().date()
        booking = BookingRequest.objects.create(
            practice=self.practice,
            doctor=self.doctor_profile,
            location=self.location,
            patient_name="Kavita Krishnan",
            phone_number="+919844332211",
            preferred_date=today,
            appointment_date=today,
            status=BookingRequest.STATUS_IN_CONSULTATION
        )

        from bookings.services.booking_service import BookingService
        BookingService.update_visit_status(booking=booking, new_status=BookingRequest.STATUS_COMPLETED, user=self.owner)

        review_rem = WhatsAppReminder.objects.filter(
            booking=booking,
            reminder_type=WhatsAppReminder.TYPE_POST_VISIT_REVIEW,
            status=WhatsAppReminder.STATUS_PENDING
        ).first()

        self.assertIsNotNone(review_rem)

    # =================================================================
    # 4. Lead Capture Welcome Message
    # =================================================================

    def test_new_lead_welcome_acknowledgement(self):
        """Fresh inquiry submissions with WhatsApp opt-in trigger immediate welcome acknowledgement."""
        from leads.services.lead_service import LeadService

        lead_data = {
            "patient_name": "Rohan Gupta",
            "phone_number": "+919911223344",
            "email": "rohan@gmail.com",
            "service_requested": "Teeth Whitening",
            "whatsapp_opt_in": True,
            "consent_given": True
        }

        lead = LeadService.create_lead(self.practice, lead_data)
        lead_msg = WhatsAppMessageLog.objects.filter(lead=lead, template_name='lead_welcome_acknowledgement').first()
        self.assertIsNotNone(lead_msg)
        self.assertEqual(lead_msg.status, WhatsAppMessageLog.STATUS_SENT)
        self.assertIn("Rohan Gupta", lead_msg.message_body)
        self.assertIn("Teeth Whitening", lead_msg.message_body)

    # =================================================================
    # 5. Reminder Batch Runner Tests
    # =================================================================

    def test_process_pending_reminders_runner(self):
        """Batch runner processes due reminders and skips opted-out patients."""
        past_time = timezone.now() - timedelta(minutes=10)

        # Booking 1: normal active patient
        b1 = BookingRequest.objects.create(
            practice=self.practice,
            patient_name="Normal Patient",
            phone_number="+919555112233",
            preferred_date=timezone.now().date(),
            appointment_date=timezone.now().date(),
            start_time=time(10, 0),
            status=BookingRequest.STATUS_CONFIRMED
        )
        rem1 = WhatsAppReminder.objects.create(
            practice=self.practice,
            booking=b1,
            reminder_type=WhatsAppReminder.TYPE_APPT_24H,
            scheduled_for=past_time,
            status=WhatsAppReminder.STATUS_PENDING
        )

        # Booking 2: opted out patient
        b2 = BookingRequest.objects.create(
            practice=self.practice,
            patient_name="Opted Out Patient",
            phone_number="+919555998877",
            preferred_date=timezone.now().date(),
            appointment_date=timezone.now().date(),
            start_time=time(11, 0),
            status=BookingRequest.STATUS_CONFIRMED
        )
        WhatsAppOptOutService.register_opt_out(self.practice, b2.phone_number)
        rem2 = WhatsAppReminder.objects.create(
            practice=self.practice,
            booking=b2,
            reminder_type=WhatsAppReminder.TYPE_APPT_24H,
            scheduled_for=past_time,
            status=WhatsAppReminder.STATUS_PENDING
        )

        stats = WhatsAppReminderService.process_pending_reminders(practice=self.practice)
        self.assertEqual(stats["sent"], 1)
        self.assertEqual(stats["skipped_opt_out"], 1)

        rem1.refresh_from_db()
        self.assertEqual(rem1.status, WhatsAppReminder.STATUS_SENT)

        rem2.refresh_from_db()
        self.assertEqual(rem2.status, WhatsAppReminder.STATUS_SKIPPED_OPT_OUT)

    # =================================================================
    # 6. Meta WhatsApp Webhook Tests
    # =================================================================

    def test_meta_webhook_challenge_verification(self):
        """Tests Meta hub.challenge verification GET handshake."""
        url = reverse('whatsapp:webhook_practice', kwargs={'practice_slug_or_id': self.practice.slug})
        challenge_token = "random_challenge_code_12345"

        response = self.client.get(url, {
            'hub.mode': 'subscribe',
            'hub.verify_token': self.config.webhook_verify_token,
            'hub.challenge': challenge_token
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), challenge_token)

    def test_meta_webhook_delivery_receipt(self):
        """Webhook delivery receipts update message status to delivered / read."""
        msg_log = WhatsAppMessageLog.objects.create(
            practice=self.practice,
            provider_message_id='wamid.test_12345',
            recipient_phone='+919876543210',
            message_body='Test',
            status=WhatsAppMessageLog.STATUS_SENT
        )

        url = reverse('whatsapp:webhook_practice', kwargs={'practice_slug_or_id': self.practice.slug})
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "WABA_123",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "statuses": [{
                            "id": "wamid.test_12345",
                            "status": "delivered",
                            "timestamp": "1729571200",
                            "recipient_id": "919876543210"
                        }]
                    },
                    "field": "messages"
                }]
            }]
        }

        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, 200)

        msg_log.refresh_from_db()
        self.assertEqual(msg_log.status, WhatsAppMessageLog.STATUS_DELIVERED)
        self.assertIsNotNone(msg_log.delivered_at)

    def test_meta_webhook_inbound_stop_keyword_registers_opt_out(self):
        """Patient texting STOP via WhatsApp automatically registers opt-out and sends compliance receipt."""
        sender_phone = "+919888777666"

        url = reverse('whatsapp:webhook_practice', kwargs={'practice_slug_or_id': self.practice.slug})
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "WABA_123",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "messages": [{
                            "from": "919888777666",
                            "id": "wamid.in_stop_123",
                            "timestamp": "1729571200",
                            "text": {"body": "STOP"},
                            "type": "text"
                        }]
                    },
                    "field": "messages"
                }]
            }]
        }

        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, 200)

        # Check opt-out is recorded
        self.assertTrue(WhatsAppOptOutService.is_opted_out(self.practice, sender_phone))

        # Check compliance acknowledgment was dispatched
        ack_msg = WhatsAppMessageLog.objects.filter(
            practice=self.practice,
            recipient_phone=sender_phone,
            message_body__icontains="successfully unsubscribed"
        ).first()
        self.assertIsNotNone(ack_msg)

    # =================================================================
    # 7. Management APIs & Analytics Tests
    # =================================================================

    def test_get_and_update_config_api(self):
        """GET /api/whatsapp/config/ and PATCH /api/whatsapp/config/."""
        url = reverse('whatsapp:config')

        get_res = self.client.get(url, **self.auth_headers)
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res.data['provider'], WhatsAppConfig.PROVIDER_MOCK)

        patch_res = self.client.patch(url, {
            'display_phone_number': '+919999888877',
            'daily_send_limit': 1500
        }, **self.auth_headers, format='json')

        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data['display_phone_number'], '+919999888877')
        self.assertEqual(patch_res.data['daily_send_limit'], 1500)

    def test_templates_api_list_and_preview(self):
        """GET /api/whatsapp/templates/ and POST /api/whatsapp/templates/<id>/preview/."""
        list_url = reverse('whatsapp:template_list_create')
        res = self.client.get(list_url, **self.auth_headers)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(res.data['count'], 8)

        tpl_id = res.data['results'][0]['id']
        preview_url = reverse('whatsapp:template_preview', kwargs={'pk': tpl_id})
        prev_res = self.client.post(preview_url, {}, **self.auth_headers, format='json')
        self.assertEqual(prev_res.status_code, status.HTTP_200_OK)
        self.assertIn('rendered_body', prev_res.data)

    def test_opt_out_apis(self):
        """Opt-out list, manual toggle, check, and opt-in endpoints."""
        list_url = reverse('whatsapp:opt_out_list_create')
        phone = "+919876123450"

        # 1. Post manual opt-out
        post_res = self.client.post(list_url, {
            'phone_number': phone,
            'reason': WhatsAppOptOut.REASON_STAFF_MANUAL,
            'patient_name': 'Manual Test Patient'
        }, **self.auth_headers, format='json')
        self.assertEqual(post_res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(post_res.data['is_opted_out'])

        # 2. Check status
        check_url = f"{reverse('whatsapp:opt_out_check')}?phone={phone}"
        check_res = self.client.get(check_url, **self.auth_headers)
        self.assertEqual(check_res.status_code, status.HTTP_200_OK)
        self.assertTrue(check_res.data['is_opted_out'])

        # 3. Opt back in
        optin_url = reverse('whatsapp:opt_in')
        optin_res = self.client.post(optin_url, {'phone_number': phone}, **self.auth_headers, format='json')
        self.assertEqual(optin_res.status_code, status.HTTP_200_OK)
        self.assertFalse(optin_res.data['record']['is_opted_out'])

    def test_analytics_api(self):
        """GET /api/whatsapp/analytics/ computes rates and metrics."""
        WhatsAppMessageLog.objects.create(
            practice=self.practice,
            recipient_phone='+919000000001',
            status=WhatsAppMessageLog.STATUS_DELIVERED,
            template_name='appointment_confirmation_slot'
        )
        WhatsAppMessageLog.objects.create(
            practice=self.practice,
            recipient_phone='+919000000002',
            status=WhatsAppMessageLog.STATUS_READ,
            template_name='appointment_confirmation_slot'
        )
        WhatsAppMessageLog.objects.create(
            practice=self.practice,
            recipient_phone='+919000000003',
            status=WhatsAppMessageLog.STATUS_FAILED,
            template_name='appointment_reminder_24h'
        )

        url = reverse('whatsapp:analytics')
        res = self.client.get(url, **self.auth_headers)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(res.data['total_outbound_messages'], 3)
        self.assertIn('delivery_rate_percent', res.data['metrics'])
        self.assertIn('read_rate_percent', res.data['metrics'])
        self.assertIn('opt_out_rate_percent', res.data['metrics'])

    def test_test_send_api(self):
        """POST /api/whatsapp/test-send/ sends sample template message."""
        url = reverse('whatsapp:test_send')
        payload = {
            "recipient_phone": "+919876543210",
            "template_name": "appointment_confirmation_slot",
            "custom_context": {"patient_name": "Dr. Tester"}
        }

        res = self.client.post(url, payload, **self.auth_headers, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['log']['status'], WhatsAppMessageLog.STATUS_SENT)

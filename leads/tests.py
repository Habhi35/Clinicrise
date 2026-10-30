import uuid
from datetime import date
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from authentication.models import User
from authentication.services.jwt_service import get_tokens_for_user
from practices.models import Practice, PracticeMembership
from websites.models import ClinicWebsite
from leads.models import ClickEvent, Lead, LeadActivity


class LeadsAndEnquiriesTests(APITestCase):

    def setUp(self):
        # 1. Create Clinic Owner
        self.owner = User.objects.create_user(
            email="dr.rajesh@sunriseclinic.com",
            phone_number="+919876500010",
            first_name="Dr. Rajesh",
            last_name="Sharma",
            password="StrongPassword123!"
        )
        self.owner_tokens = get_tokens_for_user(self.owner)

        # 2. Create Staff / Receptionist
        self.staff = User.objects.create_user(
            email="reception@sunriseclinic.com",
            phone_number="+919876500011",
            first_name="Pooja",
            last_name="Reddy",
            password="StrongPassword123!"
        )
        self.staff_tokens = get_tokens_for_user(self.staff)

        # 3. Create External User (other clinic)
        self.external_user = User.objects.create_user(
            email="external@otherclinic.com",
            phone_number="+919876500012",
            password="StrongPassword123!"
        )
        self.external_tokens = get_tokens_for_user(self.external_user)

        # 4. Create Practice Tenant: Sunrise Multispeciality Clinic
        self.practice = Practice.objects.create(
            name="Sunrise Multispeciality Clinic",
            slug="sunrise-clinic-hyd",
            owner=self.owner,
            phone_number="+919876543210",
            email="contact@sunriseclinic.com",
            city="Hyderabad",
            state="Telangana",
            is_active=True
        )
        self.owner_membership = PracticeMembership.objects.create(
            practice=self.practice,
            user=self.owner,
            role=PracticeMembership.ROLE_OWNER,
            is_active=True
        )
        self.staff_membership = PracticeMembership.objects.create(
            practice=self.practice,
            user=self.staff,
            role=PracticeMembership.ROLE_STAFF,
            is_active=True
        )

        # 5. Create Website for Practice
        self.website = ClinicWebsite.objects.create(
            practice=self.practice,
            title="Sunrise Multispeciality Clinic",
            subdomain="sunrise",
            contact_phone="+919876543210",
            whatsapp_number="+919876543210",
            is_published=True
        )

        # 6. Create Another Practice for Tenant Isolation Tests
        self.other_practice = Practice.objects.create(
            name="Apollo Dental",
            slug="apollo-dental-hyd",
            owner=self.external_user,
            phone_number="+919876599999",
            is_active=True
        )
        self.other_membership = PracticeMembership.objects.create(
            practice=self.other_practice,
            user=self.external_user,
            role=PracticeMembership.ROLE_OWNER,
            is_active=True
        )

    # -------------------------------------------------------------
    # 1. ENQUIRY FORMS & PUBLIC LEAD INGESTION
    # -------------------------------------------------------------
    def test_public_enquiry_form_submission_with_consent(self):
        """Prospective patient submits enquiry form with GDPR/DPDP consent logging."""
        url = reverse('leads:public_inquire', kwargs={'practice_slug_or_domain': self.practice.slug})
        payload = {
            "patient_name": "Kavita Rao",
            "phone_number": "+919876511111",
            "email": "kavita.rao@gmail.com",
            "preferred_date": "2026-10-25",
            "preferred_time_slot": "Morning (10:00 AM - 12:00 PM)",
            "service_requested": "Root Canal Consultation",
            "doctor_requested": "Dr. Rajesh Sharma",
            "message": "Experiencing tooth pain on right lower jaw for 3 days.",
            "consent_given": True,
            "consent_text": "I agree to receive communications regarding my enquiry via Phone, WhatsApp, SMS and Email.",
            "whatsapp_opt_in": True,
            "call_opt_in": True,
            "sms_opt_in": True,
            "email_opt_in": True,
            "utm_source": "google_ads",
            "utm_campaign": "dental_implants_hyd",
            "source_url": "https://sunrise.clinicrise.com/services/dental",
            "device_type": "mobile"
        }

        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
        self.assertIn('lead_id', response.data)

        # Verify Lead in database
        lead = Lead.objects.get(id=response.data['lead_id'])
        self.assertEqual(lead.practice, self.practice)
        self.assertEqual(lead.patient_name, "Kavita Rao")
        self.assertEqual(lead.phone_number, "+919876511111")
        self.assertEqual(lead.service_requested, "Root Canal Consultation")
        self.assertEqual(lead.status, Lead.STATUS_NEW)
        self.assertFalse(lead.is_read)
        self.assertEqual(lead.source, Lead.SOURCE_WEBSITE_FORM)
        self.assertEqual(lead.utm_source, "google_ads")

        # Verify Consent Tracking
        self.assertTrue(lead.consent_given)
        self.assertIsNotNone(lead.consent_timestamp)
        self.assertTrue(lead.whatsapp_opt_in)
        self.assertTrue(lead.call_opt_in)
        self.assertFalse(lead.consent_withdrawn)

        # Verify initial activity was recorded
        activities = lead.activities.all()
        self.assertEqual(activities.count(), 1)
        self.assertEqual(activities.first().new_status, Lead.STATUS_NEW)

    def test_enquiry_resolution_via_website_subdomain(self):
        """Enquiry submission resolves practice by clinic website subdomain."""
        url = reverse('leads:public_inquire', kwargs={'practice_slug_or_domain': 'sunrise'})
        payload = {
            "patient_name": "Rohan Mehta",
            "phone_number": "+919876522222",
            "message": "General checkup inquiry"
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        lead = Lead.objects.get(id=response.data['lead_id'])
        self.assertEqual(lead.practice, self.practice)
        self.assertEqual(lead.website, self.website)

    # -------------------------------------------------------------
    # 2. CALL & WHATSAPP CLICK EVENT TRACKING
    # -------------------------------------------------------------
    def test_whatsapp_click_event_tracking(self):
        """Track patient WhatsApp button click on clinic website."""
        url = reverse('leads:public_click_event', kwargs={'practice_slug_or_domain': self.practice.slug})
        payload = {
            "event_type": ClickEvent.TYPE_WHATSAPP_CLICK,
            "target_phone": "+919876543210",
            "doctor_name": "Dr. Rajesh Sharma",
            "service_name": "Dental Implants",
            "page_url": "https://sunrise.clinicrise.com/doctors/dr-rajesh",
            "utm_source": "instagram",
            "utm_medium": "story_link",
            "device_type": "mobile"
        }

        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['event_type'], ClickEvent.TYPE_WHATSAPP_CLICK)

        event = ClickEvent.objects.get(id=response.data['event_id'])
        self.assertEqual(event.practice, self.practice)
        self.assertEqual(event.event_type, ClickEvent.TYPE_WHATSAPP_CLICK)
        self.assertEqual(event.utm_source, "instagram")

    def test_call_click_with_quick_lead_capture(self):
        """Call click with phone provided automatically converts into high-priority lead."""
        url = reverse('leads:public_click_event', kwargs={'practice_slug_or_domain': self.practice.slug})
        payload = {
            "event_type": ClickEvent.TYPE_CALL_CLICK,
            "target_phone": "+919876543210",
            "patient_name": "Suresh Nair",
            "phone_number": "+919876533333",
            "service_name": "Emergency Consultation",
            "page_url": "https://sunrise.clinicrise.com/"
        }

        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNotNone(response.data['lead_id'])

        lead = Lead.objects.get(id=response.data['lead_id'])
        self.assertEqual(lead.patient_name, "Suresh Nair")
        self.assertEqual(lead.source, Lead.SOURCE_CALL_CLICK)
        self.assertEqual(lead.priority, Lead.PRIORITY_HIGH)

        # Check ClickEvent is linked to Lead
        event = ClickEvent.objects.get(id=response.data['event_id'])
        self.assertEqual(event.lead, lead)

    # -------------------------------------------------------------
    # 3. LEAD INBOX & MULTI-TENANCY ISOLATION
    # -------------------------------------------------------------
    def test_lead_inbox_tenant_isolation(self):
        """Practice members can only view their own practice's leads."""
        # Create Lead in Sunrise Clinic
        sunrise_lead = Lead.objects.create(
            practice=self.practice,
            patient_name="Sunrise Patient",
            phone_number="+919876510001",
            status=Lead.STATUS_NEW
        )
        # Create Lead in Apollo Dental
        apollo_lead = Lead.objects.create(
            practice=self.other_practice,
            patient_name="Apollo Patient",
            phone_number="+919876590001",
            status=Lead.STATUS_NEW
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.staff_tokens['access']}",
            HTTP_X_PRACTICE_ID=str(self.practice.id)
        )
        url = reverse('leads:lead_inbox')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        lead_ids = [item['id'] for item in response.data]
        self.assertIn(str(sunrise_lead.id), lead_ids)
        self.assertNotIn(str(apollo_lead.id), lead_ids)

    def test_lead_inbox_filtering_and_search(self):
        """Filter leads by status, source, priority and full-text search."""
        Lead.objects.create(
            practice=self.practice,
            patient_name="Amitabh Bachchan",
            phone_number="+919876544441",
            status=Lead.STATUS_CONTACTED,
            source=Lead.SOURCE_WEBSITE_FORM,
            priority=Lead.PRIORITY_HIGH
        )
        Lead.objects.create(
            practice=self.practice,
            patient_name="Shah Rukh Khan",
            phone_number="+919876544442",
            status=Lead.STATUS_NEW,
            source=Lead.SOURCE_WHATSAPP_CLICK,
            priority=Lead.PRIORITY_MEDIUM
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.owner_tokens['access']}",
            HTTP_X_PRACTICE_ID=str(self.practice.id)
        )
        url = reverse('leads:lead_inbox')

        # Filter by status=new
        res_status = self.client.get(f"{url}?status=new")
        self.assertEqual(res_status.status_code, status.HTTP_200_OK)
        for lead in res_status.data:
            self.assertEqual(lead['status'], Lead.STATUS_NEW)

        # Search by name query "Amitabh"
        res_search = self.client.get(f"{url}?search=Amitabh")
        self.assertEqual(len(res_search.data), 1)
        self.assertEqual(res_search.data[0]['patient_name'], "Amitabh Bachchan")

    # -------------------------------------------------------------
    # 4. LEAD DETAIL & MARK READ
    # -------------------------------------------------------------
    def test_lead_detail_view_marks_read(self):
        """Viewing lead detail marks is_read=True and returns full timeline."""
        lead = Lead.objects.create(
            practice=self.practice,
            patient_name="Deepika Padukone",
            phone_number="+919876555555",
            is_read=False
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.staff_tokens['access']}",
            HTTP_X_PRACTICE_ID=str(self.practice.id)
        )
        url = reverse('leads:lead_detail', kwargs={'pk': lead.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_read'])

        lead.refresh_from_db()
        self.assertTrue(lead.is_read)

    # -------------------------------------------------------------
    # 5. STATUS CHANGES & ACTIVITY AUDIT TRAIL
    # -------------------------------------------------------------
    def test_status_transition_pipeline_and_audit_log(self):
        """Transitioning lead status creates a LeadActivity audit entry."""
        lead = Lead.objects.create(
            practice=self.practice,
            patient_name="Virat Kohli",
            phone_number="+919876566666",
            status=Lead.STATUS_NEW
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.owner_tokens['access']}",
            HTTP_X_PRACTICE_ID=str(self.practice.id)
        )
        url = reverse('leads:lead_status_update', kwargs={'pk': lead.id})

        # Transition 1: New -> Contacted
        res1 = self.client.post(url, {
            "status": Lead.STATUS_CONTACTED,
            "note": "Called patient. Answered promptly, requested dental consultation."
        }, format='json')
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertEqual(res1.data['status'], Lead.STATUS_CONTACTED)

        lead.refresh_from_db()
        self.assertEqual(lead.status, Lead.STATUS_CONTACTED)
        self.assertIsNotNone(lead.last_contacted_at)

        # Transition 2: Contacted -> Appointment Scheduled
        res2 = self.client.post(url, {
            "status": Lead.STATUS_APPOINTMENT_SCHEDULED,
            "note": "Booked appointment for Saturday 11am with Dr. Rajesh.",
            "follow_up_date": "2026-10-24T11:00:00Z"
        }, format='json')
        self.assertEqual(res2.status_code, status.HTTP_200_OK)

        lead.refresh_from_db()
        self.assertEqual(lead.status, Lead.STATUS_APPOINTMENT_SCHEDULED)

        # Verify audit trail has 2 status change entries
        activities = lead.activities.filter(activity_type=LeadActivity.TYPE_STATUS_CHANGE)
        self.assertEqual(activities.count(), 2)

    # -------------------------------------------------------------
    # 6. MANUAL LEAD ENTRY BY CLINIC STAFF
    # -------------------------------------------------------------
    def test_manual_lead_creation_by_staff(self):
        """Staff manually logs walk-in patient from reception desk."""
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.staff_tokens['access']}",
            HTTP_X_PRACTICE_ID=str(self.practice.id)
        )
        url = reverse('leads:lead_list_create')
        payload = {
            "patient_name": "Manish Sharma",
            "phone_number": "+919876577777",
            "email": "manish@sharma.in",
            "service_requested": "Orthodontic Evaluation",
            "priority": Lead.PRIORITY_HIGH,
            "source": Lead.SOURCE_MANUAL,
            "message": "Walk-in patient at front desk inquiring about ceramic braces.",
            "consent_given": True,
            "whatsapp_opt_in": True,
            "call_opt_in": True
        }

        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['patient_name'], "Manish Sharma")
        self.assertEqual(response.data['source'], Lead.SOURCE_MANUAL)

    # -------------------------------------------------------------
    # 7. STAFF TIMELINE ACTIVITIES & CALL LOGS
    # -------------------------------------------------------------
    def test_add_activity_note_and_call_log(self):
        """Staff adds internal note and logs phone call to lead timeline."""
        lead = Lead.objects.create(
            practice=self.practice,
            patient_name="Ananya Panday",
            phone_number="+919876588888"
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.staff_tokens['access']}",
            HTTP_X_PRACTICE_ID=str(self.practice.id)
        )
        url = reverse('leads:lead_activities', kwargs={'lead_id': lead.id})

        # Log a phone call
        res_call = self.client.post(url, {
            "activity_type": LeadActivity.TYPE_CALL,
            "note": "Called patient, left voicemail regarding upcoming appointment slots.",
            "metadata": {"duration_seconds": 45}
        }, format='json')
        self.assertEqual(res_call.status_code, status.HTTP_201_CREATED)

        # Check that lead's last_contacted_at updated
        lead.refresh_from_db()
        self.assertIsNotNone(lead.last_contacted_at)

        # List activities
        res_list = self.client.get(url)
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(res_list.data), 1)

    # -------------------------------------------------------------
    # 8. CONSENT MANAGEMENT & PATIENT OPT-OUT
    # -------------------------------------------------------------
    def test_consent_withdrawal_and_opt_out(self):
        """Test patient opt-out via public endpoint and staff consent revocation."""
        lead = Lead.objects.create(
            practice=self.practice,
            patient_name="Opt-Out Patient",
            phone_number="+919876599991",
            whatsapp_opt_in=True,
            call_opt_in=True,
            consent_withdrawn=False
        )

        # 1. Public opt-out by phone
        opt_out_url = reverse('leads:public_opt_out', kwargs={'practice_slug_or_domain': self.practice.slug})
        opt_out_res = self.client.post(opt_out_url, {
            "phone_number": "+919876599991",
            "reason": "Unsubscribe request via web form"
        }, format='json')
        self.assertEqual(opt_out_res.status_code, status.HTTP_200_OK)
        self.assertTrue(opt_out_res.data['success'])

        lead.refresh_from_db()
        self.assertTrue(lead.consent_withdrawn)
        self.assertFalse(lead.whatsapp_opt_in)
        self.assertFalse(lead.call_opt_in)
        self.assertIsNotNone(lead.consent_withdrawn_at)

        # 2. Staff updates consent preferences
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.staff_tokens['access']}",
            HTTP_X_PRACTICE_ID=str(self.practice.id)
        )
        consent_url = reverse('leads:lead_consent_update', kwargs={'pk': lead.id})
        update_res = self.client.post(consent_url, {
            "whatsapp_opt_in": True,
            "call_opt_in": True,
            "consent_withdrawn": False
        }, format='json')
        self.assertEqual(update_res.status_code, status.HTTP_200_OK)

        lead.refresh_from_db()
        self.assertTrue(lead.whatsapp_opt_in)

    # -------------------------------------------------------------
    # 9. CRM INBOX STATS & CONVERSION METRICS
    # -------------------------------------------------------------
    def test_inbox_stats_and_metrics(self):
        """Dashboard statistics aggregate total, pipeline stages, and click events."""
        Lead.objects.create(practice=self.practice, patient_name="L1", phone_number="111", status=Lead.STATUS_NEW, is_read=False)
        Lead.objects.create(practice=self.practice, patient_name="L2", phone_number="222", status=Lead.STATUS_CONTACTED, is_read=True)
        Lead.objects.create(practice=self.practice, patient_name="L3", phone_number="333", status=Lead.STATUS_CONVERTED, is_read=True)

        ClickEvent.objects.create(practice=self.practice, event_type=ClickEvent.TYPE_WHATSAPP_CLICK)
        ClickEvent.objects.create(practice=self.practice, event_type=ClickEvent.TYPE_CALL_CLICK)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.owner_tokens['access']}",
            HTTP_X_PRACTICE_ID=str(self.practice.id)
        )
        url = reverse('leads:lead_stats')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(data['total_leads'], 3)
        self.assertEqual(data['unread_count'], 1)
        self.assertEqual(data['pipeline']['new'], 1)
        self.assertEqual(data['pipeline']['contacted'], 1)
        self.assertEqual(data['pipeline']['converted'], 1)
        self.assertAlmostEqual(data['conversion_rate_percentage'], 33.33, places=1)
        self.assertEqual(data['click_events']['total_whatsapp_clicks'], 1)
        self.assertEqual(data['click_events']['total_call_clicks'], 1)

    # -------------------------------------------------------------
    # 10. WEBSITE INQUIRY INTEGRATION
    # -------------------------------------------------------------
    def test_website_public_inquiry_syncs_to_lead_inbox(self):
        """Website inquiry endpoint creates unified Lead in CRM inbox."""
        url = reverse('websites:public_website_inquire', kwargs={'domain_or_subdomain': 'sunrise'})
        payload = {
            "patient_name": "Integration Patient",
            "phone_number": "+919876501234",
            "email": "integration@test.com",
            "message": "Testing automatic sync to lead inbox"
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Check Lead exists in Practice Lead inbox
        lead = Lead.objects.filter(practice=self.practice, phone_number="+919876501234").first()
        self.assertIsNotNone(lead)
        self.assertEqual(lead.patient_name, "Integration Patient")
        self.assertEqual(lead.source, Lead.SOURCE_WEBSITE_FORM)

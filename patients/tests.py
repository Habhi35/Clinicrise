import uuid
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from practices.models import DoctorProfile, Practice, PracticeMembership
from leads.models import Lead
from patients.models import (
    Patient,
    PatientFollowUp,
    PatientNote,
    PatientTimeline,
    PatientVitals,
)
from patients.services.patient_service import PatientService

User = get_user_model()


class PatientsAndCRMTestCase(TestCase):
    """
    Comprehensive test suite for Team Access (Receptionists & Assistants) and CRM
    (Patient directory, timelines, categorized & pinned notes, vitals, follow-up queues).
    """

    def setUp(self):
        self.client = APIClient()

        # 1. Create Practice Owner
        self.owner = User.objects.create_user(
            email="owner@cityhealth.com",
            password="StrongPassword123!",
            first_name="Dr. Rajesh",
            last_name="Sharma"
        )
        self.practice = Practice.objects.create(
            name="CityHealth Dental & Medical Centre",
            owner=self.owner,
            phone_number="+918049123456",
            city="Bengaluru",
            currency="INR"
        )
        self.owner_membership = PracticeMembership.objects.create(
            practice=self.practice,
            user=self.owner,
            role=PracticeMembership.ROLE_OWNER
        )

        # 2. Create Receptionist
        self.receptionist = User.objects.create_user(
            email="receptionist@cityhealth.com",
            password="StrongPassword123!",
            first_name="Priya",
            last_name="Nair"
        )
        self.receptionist_membership = PracticeMembership.objects.create(
            practice=self.practice,
            user=self.receptionist,
            role=PracticeMembership.ROLE_RECEPTIONIST
        )

        # 3. Create Clinical Assistant
        self.assistant = User.objects.create_user(
            email="assistant@cityhealth.com",
            password="StrongPassword123!",
            first_name="Sunita",
            last_name="Rao"
        )
        self.assistant_membership = PracticeMembership.objects.create(
            practice=self.practice,
            user=self.assistant,
            role=PracticeMembership.ROLE_ASSISTANT
        )

        # 4. Create Doctor
        self.doctor_user = User.objects.create_user(
            email="doctor@cityhealth.com",
            password="StrongPassword123!",
            first_name="Dr. Ananya",
            last_name="Deshmukh"
        )
        self.doctor_membership = PracticeMembership.objects.create(
            practice=self.practice,
            user=self.doctor_user,
            role=PracticeMembership.ROLE_DOCTOR
        )
        self.doctor_profile = DoctorProfile.objects.create(
            user=self.doctor_user,
            medical_license_number="KMC-987654",
            specialization="Dental Surgeon",
            qualifications="BDS, MDS"
        )

    def _auth(self, user):
        self.client.force_authenticate(user=user)
        self.client.credentials(HTTP_X_PRACTICE_ID=str(self.practice.id))

    def test_practice_role_matrix(self):
        """Verify role hierarchy and capabilities endpoint."""
        self._auth(self.receptionist)
        res = self.client.get('/api/practices/roles/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        roles = res.data['roles']
        role_codes = [r['code'] for r in roles]
        self.assertIn('owner', role_codes)
        self.assertIn('admin', role_codes)
        self.assertIn('doctor', role_codes)
        self.assertIn('receptionist', role_codes)
        self.assertIn('assistant', role_codes)
        self.assertIn('staff', role_codes)

    def test_filter_practice_members_by_role(self):
        """Verify filtering members by role in the practice."""
        self._auth(self.owner)
        res = self.client.get(f'/api/practices/{self.practice.id}/members/?role=receptionist')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['user_email'], 'receptionist@cityhealth.com')

        res_ast = self.client.get(f'/api/practices/{self.practice.id}/members/?role=assistant')
        self.assertEqual(res_ast.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_ast.data), 1)
        self.assertEqual(res_ast.data[0]['user_email'], 'assistant@cityhealth.com')

    def test_invite_receptionist_and_assistant(self):
        """Verify practice admin can invite receptionists and assistants."""
        self._auth(self.owner)
        # Invite new receptionist
        res = self.client.post(
            f'/api/practices/{self.practice.id}/invite/',
            {"identifier": "new.frontdesk@cityhealth.com", "role": "receptionist"}
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['invitation']['role'], 'receptionist')

        # Invite new clinical assistant
        res2 = self.client.post(
            f'/api/practices/{self.practice.id}/invite/',
            {"identifier": "new.nurse@cityhealth.com", "role": "assistant"}
        )
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res2.data['invitation']['role'], 'assistant')

    def test_register_patient(self):
        """Receptionist registers a new patient with medical alerts and contact info."""
        self._auth(self.receptionist)
        payload = {
            "first_name": "Arjun",
            "last_name": "Reddy",
            "phone_number": "9876543210",
            "email": "arjun.reddy@example.com",
            "gender": "male",
            "age": 32,
            "blood_group": "O+",
            "city": "Bengaluru",
            "emergency_contact_name": "Kavita Reddy",
            "emergency_contact_phone": "9876543211",
            "emergency_contact_relation": "Spouse",
            "allergies": "Penicillin, Sulfa drugs",
            "chronic_conditions": ["Mild Hypertension"],
            "medical_alerts": "Severe penicillin anaphylaxis",
            "tags": ["VIP", "Anxious"],
            "source": "walk_in"
        }
        res = self.client.post('/api/patients/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        data = res.data

        self.assertEqual(data['full_name'], "Arjun Reddy")
        self.assertEqual(data['phone_number'], "+919876543210")
        self.assertTrue(data['patient_id'].startswith("CR-P-"))
        self.assertEqual(data['blood_group'], "O+")

        # Check timeline entry was created
        timeline = PatientTimeline.objects.filter(patient_id=data['id'])
        self.assertTrue(timeline.filter(event_type=PatientTimeline.EVENT_PATIENT_CREATED).exists())

    def test_assistant_records_vitals_and_calculates_bmi(self):
        """Clinical assistant records patient vitals with auto-calculated BMI."""
        patient = Patient.objects.create(
            practice=self.practice,
            first_name="Deepak",
            last_name="Menon",
            phone_number="+919876543212",
            gender="male",
            age=45
        )

        self._auth(self.assistant)
        payload = {
            "blood_pressure_systolic": 125,
            "blood_pressure_diastolic": 82,
            "pulse_bpm": 74,
            "temperature_fahrenheit": 98.4,
            "oxygen_saturation_spo2": 99,
            "weight_kg": 72.0,
            "height_cm": 172.0,
            "notes": "Patient reports good energy, mild lower back stiffness."
        }
        res = self.client.post(f'/api/patients/{patient.id}/vitals/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        data = res.data

        self.assertEqual(data['blood_pressure_systolic'], 125)
        self.assertEqual(data['blood_pressure_diastolic'], 82)
        # BMI = 72 / (1.72^2) = 72 / 2.9584 = 24.3
        self.assertAlmostEqual(float(data['bmi']), 24.3, places=1)
        self.assertEqual(data['recorded_by_name'], "Sunita Rao")

        # Verify timeline entry
        timeline_entry = PatientTimeline.objects.filter(
            patient=patient,
            event_type=PatientTimeline.EVENT_VITALS_RECORDED
        ).first()
        self.assertIsNotNone(timeline_entry)
        self.assertIn("BP: 125/82 mmHg", timeline_entry.description)
        self.assertIn("Pulse: 74 bpm", timeline_entry.description)
        self.assertEqual(timeline_entry.performer_role, "assistant")

    def test_receptionist_logs_phone_call(self):
        """Receptionist logs an outgoing call with patient outcome."""
        patient = Patient.objects.create(
            practice=self.practice,
            first_name="Sneha",
            last_name="Iyer",
            phone_number="+919876543213"
        )

        self._auth(self.receptionist)
        payload = {
            "call_type": "outgoing",
            "outcome": "answered",
            "notes": "Confirmed patient arriving 15 minutes before 10am slot for dental x-ray."
        }
        res = self.client.post(f'/api/patients/{patient.id}/log-call/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # Check frontdesk note created
        note = PatientNote.objects.filter(patient=patient, category=PatientNote.CATEGORY_FRONTDESK).first()
        self.assertIsNotNone(note)
        self.assertIn("Phone Call Logged", note.note)

        # Check timeline entry
        timeline = PatientTimeline.objects.filter(patient=patient, event_type=PatientTimeline.EVENT_PHONE_CALL).first()
        self.assertIsNotNone(timeline)
        self.assertIn("Call Type: Outgoing", timeline.description)

    def test_doctor_adds_and_pins_critical_note(self):
        """Doctor adds clinical note and pins critical allergy warning."""
        patient = Patient.objects.create(
            practice=self.practice,
            first_name="Kavita",
            last_name="Krishnan",
            phone_number="+919876543214"
        )

        self._auth(self.doctor_user)
        # Add consultation note
        res = self.client.post(
            f'/api/patients/{patient.id}/notes/',
            {
                "note": "Root canal treatment completed on tooth #46. Prescribed paracetamol.",
                "category": "doctor_consultation",
                "is_pinned": False
            },
            format='json'
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # Add pinned allergy alert
        res_pinned = self.client.post(
            f'/api/patients/{patient.id}/notes/',
            {
                "note": "CRITICAL ALERT: Patient suffered severe angioedema with Amoxicillin in 2024. DO NOT PRESCRIBE BETA-LACTAMS.",
                "category": "general",
                "is_pinned": True
            },
            format='json'
        )
        self.assertEqual(res_pinned.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res_pinned.data['is_pinned'])

        # Check patient detail endpoint returns pinned notes prominently
        res_detail = self.client.get(f'/api/patients/{patient.id}/')
        self.assertEqual(res_detail.status_code, status.HTTP_200_OK)
        pinned = res_detail.data['pinned_notes']
        self.assertEqual(len(pinned), 1)
        self.assertIn("CRITICAL ALERT", pinned[0]['note'])

        # Test toggle pin endpoint
        pin_toggle_res = self.client.post(f'/api/patients/{patient.id}/notes/{res_pinned.data["id"]}/pin/')
        self.assertEqual(pin_toggle_res.status_code, status.HTTP_200_OK)
        self.assertFalse(pin_toggle_res.data['is_pinned'])

    def test_follow_up_scheduling_and_completion_queue(self):
        """Schedule a follow-up, list in global queue, and mark completed."""
        patient = Patient.objects.create(
            practice=self.practice,
            first_name="Rohan",
            last_name="Gupta",
            phone_number="+919876543215"
        )

        self._auth(self.doctor_user)
        due_tomorrow = timezone.now() + timedelta(days=1)
        follow_up_res = self.client.post(
            f'/api/patients/{patient.id}/follow-ups/',
            {
                "title": "Post-extraction recovery check",
                "follow_up_type": "post_consultation_check",
                "priority": "high",
                "due_date": due_tomorrow.isoformat(),
                "instructions": "Call patient to check bleeding and pain levels. Ensure ice pack applied.",
                "assigned_to_id": str(self.receptionist.id)
            },
            format='json'
        )
        self.assertEqual(follow_up_res.status_code, status.HTTP_201_CREATED)
        fu_id = follow_up_res.data['id']

        # Receptionist opens global queue
        self._auth(self.receptionist)
        queue_res = self.client.get('/api/patients/follow-ups/?filter=upcoming')
        self.assertEqual(queue_res.status_code, status.HTTP_200_OK)
        self.assertTrue(any(item['id'] == fu_id for item in queue_res.data))

        # Receptionist completes follow-up
        complete_res = self.client.post(
            f'/api/patients/follow-ups/{fu_id}/complete/',
            {"outcome_notes": "Spoke with Rohan. Bleeding completely stopped. Pain 2/10, managed with medication."}
        )
        self.assertEqual(complete_res.status_code, status.HTTP_200_OK)
        self.assertEqual(complete_res.data['status'], 'completed')
        self.assertEqual(complete_res.data['completed_by_name'], "Priya Nair")

        # Verify timeline recorded completion
        completed_timeline = PatientTimeline.objects.filter(
            patient=patient,
            event_type=PatientTimeline.EVENT_FOLLOW_UP_COMPLETED
        ).first()
        self.assertIsNotNone(completed_timeline)
        self.assertIn("Spoke with Rohan", completed_timeline.description)

    def test_convert_lead_to_patient(self):
        """1-Click conversion of a marketing lead enquiry into a full patient chart."""
        lead = Lead.objects.create(
            practice=self.practice,
            patient_name="Meera Sen",
            phone_number="+919876543216",
            email="meera.sen@example.com",
            message="Interested in clear aligners and smile makeover.",
            source="website_form"
        )

        self._auth(self.receptionist)
        res = self.client.post(f'/api/patients/convert-lead/{lead.id}/')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        patient_data = res.data['patient']

        self.assertEqual(patient_data['full_name'], "Meera Sen")
        self.assertEqual(patient_data['phone_number'], "+919876543216")

        # Verify lead state updated
        lead.refresh_from_db()
        self.assertEqual(lead.status, 'converted')

    def test_crm_overview_dashboard(self):
        """Test the practice CRM overview statistics."""
        # Seed active patient and follow-up
        p = Patient.objects.create(
            practice=self.practice,
            first_name="Test",
            last_name="Patient",
            phone_number="+919876543217"
        )
        PatientFollowUp.objects.create(
            practice=self.practice,
            patient=p,
            due_date=timezone.now() + timedelta(hours=2),
            title="Immediate Check",
            status="pending"
        )

        self._auth(self.owner)
        res = self.client.get('/api/patients/overview/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(res.data['total_active_patients'], 1)
        self.assertGreaterEqual(res.data['pending_followups_count'], 1)
        self.assertIn('followups_due_today', res.data)

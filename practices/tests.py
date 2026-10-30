from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from authentication.models import User
from authentication.services.jwt_service import get_tokens_for_user
from practices.models import (
    DoctorOnboarding,
    DoctorProfile,
    DoctorSchedule,
    Practice,
    PracticeImage,
    PracticeInvitation,
    PracticeMembership,
    PracticeService,
)


class PracticesAndPermissionsTests(APITestCase):

    def setUp(self):
        self.owner_user = User.objects.create_user(
            email="owner@cityclinic.com",
            phone_number="+919876500001",
            first_name="Dr. Rajesh",
            last_name="Sharma",
            password="StrongPassword123!"
        )
        self.owner_tokens = get_tokens_for_user(self.owner_user)

        self.doctor_user = User.objects.create_user(
            email="doctor@cityclinic.com",
            phone_number="+919876500002",
            first_name="Dr. Priya",
            last_name="Patel",
            password="StrongPassword123!"
        )
        self.doctor_tokens = get_tokens_for_user(self.doctor_user)

        self.staff_user = User.objects.create_user(
            email="staff@cityclinic.com",
            phone_number="+919876500003",
            first_name="Amit",
            last_name="Verma",
            password="StrongPassword123!"
        )
        self.staff_tokens = get_tokens_for_user(self.staff_user)

        self.external_user = User.objects.create_user(
            email="external@otherclinic.com",
            phone_number="+919876500004",
            password="StrongPassword123!"
        )
        self.external_tokens = get_tokens_for_user(self.external_user)

    def test_practice_creation_and_ownership(self):
        """Creating a practice assigns owner and automatically creates owner membership."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_tokens['access']}")
        url = reverse('practices:practice_list_create')

        payload = {
            "name": "City Health Clinic",
            "phone_number": "+919876500001",
            "email": "info@cityhealth.com",
            "city": "Hyderabad",
            "state": "Telangana",
            "currency": "INR"
        }

        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        practice_id = response.data['id']

        practice = Practice.objects.get(id=practice_id)
        self.assertEqual(practice.owner, self.owner_user)
        self.assertEqual(practice.name, "City Health Clinic")

        membership = PracticeMembership.objects.filter(practice=practice, user=self.owner_user).first()
        self.assertIsNotNone(membership)
        self.assertEqual(membership.role, PracticeMembership.ROLE_OWNER)
        self.assertTrue(membership.is_active)

    def test_tenant_isolation_via_x_practice_id(self):
        """Verifies that requests with X-Practice-ID are strictly scoped to the user's active membership."""
        practice_1 = Practice.objects.create(name="Clinic Alpha", owner=self.owner_user)
        PracticeMembership.objects.create(practice=practice_1, user=self.owner_user, role=PracticeMembership.ROLE_OWNER)

        practice_2 = Practice.objects.create(name="Clinic Beta", owner=self.external_user)
        PracticeMembership.objects.create(practice=practice_2, user=self.external_user, role=PracticeMembership.ROLE_OWNER)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.external_tokens['access']}",
            HTTP_X_PRACTICE_ID=str(practice_1.id)
        )

        detail_url = reverse('practices:practice_detail', kwargs={'pk': practice_1.id})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        detail_url_2 = reverse('practices:practice_detail', kwargs={'pk': practice_2.id})
        response_2 = self.client.get(detail_url_2)
        self.assertEqual(response_2.status_code, status.HTTP_200_OK)
        self.assertEqual(response_2.data['name'], "Clinic Beta")

    def test_team_invitation_and_acceptance_flow(self):
        """Owner invites a doctor, and the doctor accepts the invitation."""
        practice = Practice.objects.create(name="Apex Medical Center", owner=self.owner_user)
        PracticeMembership.objects.create(practice=practice, user=self.owner_user, role=PracticeMembership.ROLE_OWNER)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.owner_tokens['access']}",
            HTTP_X_PRACTICE_ID=str(practice.id)
        )
        invite_url = reverse('practices:practice_invite', kwargs={'practice_id': practice.id})
        invite_payload = {
            "identifier": self.doctor_user.email,
            "role": "doctor"
        }
        invite_res = self.client.post(invite_url, invite_payload, format='json')
        self.assertEqual(invite_res.status_code, status.HTTP_201_CREATED)
        invite_code = invite_res.data['invite_code']

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.doctor_tokens['access']}")
        accept_url = reverse('practices:invitation_accept')
        accept_res = self.client.post(accept_url, {"invite_code": invite_code}, format='json')
        self.assertEqual(accept_res.status_code, status.HTTP_200_OK)

        membership = PracticeMembership.objects.filter(practice=practice, user=self.doctor_user).first()
        self.assertIsNotNone(membership)
        self.assertEqual(membership.role, PracticeMembership.ROLE_DOCTOR)
        self.assertTrue(membership.is_active)

    def test_doctor_profile_management(self):
        """Test creating and retrieving doctor professional profile."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.doctor_tokens['access']}")
        profile_url = reverse('practices:doctor_profile')

        payload = {
            "medical_license_number": "MCI-2026-88912",
            "specialization": "Cardiologist",
            "qualifications": "MBBS, MD (Medicine), DM (Cardiology)",
            "experience_years": 12,
            "bio": "Senior Consultant Interventional Cardiologist",
            "default_consultation_fee": "800.00"
        }

        response = self.client.post(profile_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['specialization'], "Cardiologist")
        self.assertEqual(response.data['medical_license_number'], "MCI-2026-88912")

        get_res = self.client.get(profile_url)
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res.data['experience_years'], 12)

    def test_staff_cannot_invite_members(self):
        """Staff members do not have permission to invite new members to practice."""
        practice = Practice.objects.create(name="Sunrise Eye Clinic", owner=self.owner_user)
        PracticeMembership.objects.create(practice=practice, user=self.owner_user, role=PracticeMembership.ROLE_OWNER)
        PracticeMembership.objects.create(practice=practice, user=self.staff_user, role=PracticeMembership.ROLE_STAFF)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.staff_tokens['access']}",
            HTTP_X_PRACTICE_ID=str(practice.id)
        )
        invite_url = reverse('practices:practice_invite', kwargs={'practice_id': practice.id})
        response = self.client.post(invite_url, {"identifier": "newstaff@test.com", "role": "staff"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class DoctorOnboardingTests(APITestCase):
    """
    Test suite for complete Doctor Onboarding flow:
    - Step 1: Doctor profile & registration number
    - Step 2: Clinic & practice details
    - Step 3: Clinical services & fees
    - Step 4: Timings & schedule
    - Step 5: Clinic photos & documents
    - Saved progress (draft persistence & state resumption)
    - Review & completion validation
    """

    def setUp(self):
        self.doctor = User.objects.create_user(
            email="dr.ananya@clinicrise.com",
            phone_number="+919876599001",
            first_name="Dr. Ananya",
            last_name="Rao",
            password="SecurePassword123!"
        )
        self.tokens = get_tokens_for_user(self.doctor)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.tokens['access']}")

    def test_initial_onboarding_progress(self):
        """Initial onboarding progress starts at 0% with current_step set to doctor_profile."""
        url = reverse('practices:onboarding_progress')
        res = self.client.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['progress_percentage'], 0)
        self.assertEqual(res.data['current_step'], 'doctor_profile')
        self.assertFalse(res.data['is_completed'])
        self.assertEqual(len(res.data['steps']), 5)

    def test_save_draft_progress_arbitrary_data(self):
        """Doctors can save draft progress at any step without validation friction."""
        draft_url = reverse('practices:onboarding_save_draft')
        payload = {
            "step": "doctor_profile",
            "data": {
                "specialization": "Pediatrician",
                "notes": "Need to find MMC certificate number from locker tonight"
            }
        }
        res = self.client.post(draft_url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['success'])
        self.assertEqual(res.data['saved_draft']['specialization'], "Pediatrician")

        # Verify draft is preserved when querying progress
        progress_url = reverse('practices:onboarding_progress')
        get_res = self.client.get(progress_url)
        self.assertIn("doctor_profile", get_res.data['draft_data'])
        self.assertEqual(get_res.data['draft_data']['doctor_profile']['specialization'], "Pediatrician")

    def test_step_1_doctor_profile_and_registration(self):
        """Step 1 creates DoctorProfile with medical license number, council, and specialization."""
        step_url = reverse('practices:onboarding_step_profile')
        payload = {
            "title": "Dr.",
            "gender": "female",
            "medical_license_number": "MMC-2026-90412",
            "registration_council": "Maharashtra Medical Council",
            "registration_year": 2017,
            "specialization": "Pediatrician & Child Health Specialist",
            "qualifications": "MBBS, MD (Pediatrics), DNB",
            "experience_years": 9,
            "languages_spoken": "English, Hindi, Marathi",
            "bio": "Dedicated pediatrician with 9+ years experience in neonatal and child health.",
            "default_consultation_fee": "700.00",
            "profile_photo_url": "https://cdn.clinicrise.com/doctors/dr-ananya.jpg",
            "registration_certificate_url": "https://cdn.clinicrise.com/certs/mmc-90412.pdf"
        }

        res = self.client.post(step_url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['success'])
        self.assertEqual(res.data['doctor_profile']['medical_license_number'], "MMC-2026-90412")
        self.assertEqual(res.data['doctor_profile']['registration_council'], "Maharashtra Medical Council")
        self.assertEqual(res.data['progress_percentage'], 20)
        self.assertEqual(res.data['current_step'], 'clinic_details')

        # Verify DB model
        profile = DoctorProfile.objects.get(user=self.doctor)
        self.assertEqual(profile.specialization, "Pediatrician & Child Health Specialist")
        self.assertEqual(profile.registration_year, 2017)

    def test_step_1_duplicate_registration_number_rejected(self):
        """Duplicate medical license registration numbers are rejected with 400 Bad Request."""
        other_doctor = User.objects.create_user(
            email="other@clinicrise.com",
            password="Password123!"
        )
        DoctorProfile.objects.create(
            user=other_doctor,
            medical_license_number="DUPLICATE-REG-1234",
            specialization="General Medicine",
            qualifications="MBBS"
        )

        step_url = reverse('practices:onboarding_step_profile')
        payload = {
            "medical_license_number": "DUPLICATE-REG-1234",
            "specialization": "Dentist",
            "qualifications": "BDS"
        }
        res = self.client.post(step_url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already registered", res.data['error'])

    def test_step_2_clinic_details(self):
        """Step 2 creates Practice tenant and assigns Doctor as owner."""
        step_url = reverse('practices:onboarding_step_clinic')
        payload = {
            "name": "Little Stars Pediatric Clinic",
            "clinic_type": "solo_clinic",
            "tagline": "Compassionate Care for Growing Smiles",
            "phone_number": "+919876599001",
            "email": "contact@littlestars.com",
            "website": "https://littlestarsclinic.com",
            "address": "Shop 4, Sunrise Arcade, Bandra West",
            "landmark": "Near Linking Road",
            "city": "Mumbai",
            "state": "Maharashtra",
            "postal_code": "400050",
            "country": "India",
            "currency": "INR",
            "timezone": "Asia/Kolkata"
        }

        res = self.client.post(step_url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['practice']['name'], "Little Stars Pediatric Clinic")
        self.assertEqual(res.data['practice']['clinic_type'], "solo_clinic")
        self.assertEqual(res.data['current_step'], 'services')

        # Check DB
        practice = Practice.objects.get(owner=self.doctor)
        self.assertEqual(practice.city, "Mumbai")
        membership = PracticeMembership.objects.filter(practice=practice, user=self.doctor).first()
        self.assertIsNotNone(membership)
        self.assertEqual(membership.role, PracticeMembership.ROLE_OWNER)

    def test_full_onboarding_wizard_e2e(self):
        """Complete end-to-end multi-step onboarding journey."""
        # 1. Step 1: Doctor Profile
        step1_url = reverse('practices:onboarding_step_profile')
        res1 = self.client.post(step1_url, {
            "title": "Dr.",
            "medical_license_number": "MMC-2026-E2E-1",
            "registration_council": "Maharashtra Medical Council",
            "specialization": "Orthopedic Surgeon",
            "qualifications": "MBBS, MS (Ortho)",
            "experience_years": 11,
            "default_consultation_fee": "800.00"
        }, format='json')
        self.assertEqual(res1.status_code, status.HTTP_200_OK)

        # 2. Step 2: Clinic Details
        step2_url = reverse('practices:onboarding_step_clinic')
        res2 = self.client.post(step2_url, {
            "name": "OrthoCare Bone & Joint Clinic",
            "clinic_type": "polyclinic",
            "city": "Pune",
            "state": "Maharashtra",
            "phone_number": "+919876599001"
        }, format='json')
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        practice_id = res2.data['practice']['id']

        # 3. Step 3: Clinical Services
        step3_url = reverse('practices:onboarding_step_services')
        services_payload = {
            "services": [
                {
                    "name": "General Orthopedic Consultation",
                    "category": "consultation",
                    "duration_minutes": 20,
                    "price": "800.00"
                },
                {
                    "name": "Joint Injections / Pain Management",
                    "category": "procedure",
                    "duration_minutes": 30,
                    "price": "2500.00"
                },
                {
                    "name": "Follow-up Consultation",
                    "category": "follow_up",
                    "duration_minutes": 15,
                    "price": "500.00"
                }
            ]
        }
        res3 = self.client.post(step3_url, services_payload, format='json')
        self.assertEqual(res3.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res3.data['services']), 3)

        # 4. Step 4: Timings & Schedule
        step4_url = reverse('practices:onboarding_step_timings')
        timings_payload = {
            "timings": [
                {
                    "day_of_week": 0,  # Monday
                    "session_name": "Morning OPD",
                    "start_time": "09:00",
                    "end_time": "13:00",
                    "slot_duration_minutes": 20
                },
                {
                    "day_of_week": 0,  # Monday Evening
                    "session_name": "Evening OPD",
                    "start_time": "17:00",
                    "end_time": "20:00",
                    "slot_duration_minutes": 20
                },
                {
                    "day_of_week": 2,  # Wednesday
                    "session_name": "Morning OPD",
                    "start_time": "10:00",
                    "end_time": "14:00",
                    "slot_duration_minutes": 20
                }
            ]
        }
        res4 = self.client.post(step4_url, timings_payload, format='json')
        self.assertEqual(res4.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res4.data['timings']), 3)

        # 5. Step 5: Images & Media
        step5_url = reverse('practices:onboarding_step_images')
        images_payload = {
            "doctor_avatar_url": "https://cdn.clinicrise.com/dr-photo.jpg",
            "registration_certificate_url": "https://cdn.clinicrise.com/cert.pdf",
            "images": [
                {
                    "image_url": "https://cdn.clinicrise.com/clinic-facade.jpg",
                    "image_type": "clinic_facade",
                    "caption": "Clinic Exterior",
                    "is_primary": True
                },
                {
                    "image_url": "https://cdn.clinicrise.com/consultation-room.jpg",
                    "image_type": "consultation_room",
                    "caption": "Consultation Room"
                }
            ]
        }
        res5 = self.client.post(step5_url, images_payload, format='json')
        self.assertEqual(res5.status_code, status.HTTP_200_OK)

        # Check progress before completion
        progress_url = reverse('practices:onboarding_progress')
        progress_res = self.client.get(progress_url)
        self.assertEqual(progress_res.data['progress_percentage'], 100)
        self.assertEqual(len(progress_res.data['completed_steps']), 5)

        # 6. Step 6: Complete Onboarding
        complete_url = reverse('practices:onboarding_complete')
        complete_res = self.client.post(complete_url)
        self.assertEqual(complete_res.status_code, status.HTTP_200_OK)
        self.assertTrue(complete_res.data['success'])
        self.assertTrue(complete_res.data['onboarding']['is_completed'])
        self.assertEqual(complete_res.data['practice_id'], str(practice_id))

        # Check DB records
        self.assertEqual(PracticeService.objects.filter(practice_id=practice_id).count(), 3)
        self.assertEqual(DoctorSchedule.objects.filter(practice_id=practice_id).count(), 3)
        self.assertEqual(PracticeImage.objects.filter(practice_id=practice_id).count(), 2)

    def test_complete_onboarding_fails_without_clinic(self):
        """Trying to finalize onboarding without clinic details returns 400 Bad Request."""
        # Only complete Doctor Profile
        step1_url = reverse('practices:onboarding_step_profile')
        self.client.post(step1_url, {
            "medical_license_number": "INCOMPLETE-DOC-1",
            "specialization": "Dermatology",
            "qualifications": "MBBS, MD"
        }, format='json')

        complete_url = reverse('practices:onboarding_complete')
        res = self.client.post(complete_url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Clinic / Practice details are required", res.data['error'])

    def test_timing_validation_end_time_before_start_time(self):
        """Schedule shift with end_time before start_time returns validation error."""
        step2_url = reverse('practices:onboarding_step_clinic')
        self.client.post(step2_url, {"name": "Test Clinic"}, format='json')

        step1_url = reverse('practices:onboarding_step_profile')
        self.client.post(step1_url, {
            "medical_license_number": "TIMING-TEST-1",
            "specialization": "ENT",
            "qualifications": "MBBS"
        }, format='json')

        step4_url = reverse('practices:onboarding_step_timings')
        invalid_payload = {
            "timings": [
                {
                    "day_of_week": 1,
                    "start_time": "18:00",
                    "end_time": "09:00"  # Invalid! End before start
                }
            ]
        }
        res = self.client.post(step4_url, invalid_payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_file_upload_endpoint(self):
        """Doctors can upload photos and verification documents via onboarding/upload/."""
        upload_url = reverse('practices:onboarding_upload')

        test_file = SimpleUploadedFile(
            "medical_license.pdf",
            b"%PDF-1.4 test document content for license",
            content_type="application/pdf"
        )

        res = self.client.post(
            upload_url,
            {"file": test_file, "upload_type": "certificate"},
            format='multipart'
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data['success'])
        self.assertIn("certificate", res.data['file_path'])
        self.assertTrue(res.data['file_url'].endswith(".pdf"))

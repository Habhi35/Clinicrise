import datetime
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from authentication.models import User
from authentication.services.jwt_service import get_tokens_for_user
from practices.models import (
    DoctorProfile,
    DoctorSchedule,
    Practice,
    PracticeMembership,
    PracticeService,
)
from bookings.models import (
    BookingRequest,
    BookingTimeline,
    DoctorSessionCapacity,
    PracticeLocation,
)


class BookingRequestsTests(APITestCase):

    def setUp(self):
        # 1. Clinic Owner
        self.owner = User.objects.create_user(
            email="dr.rajesh@apollodental.com",
            phone_number="+919876500020",
            first_name="Dr. Rajesh",
            last_name="Sharma",
            password="StrongPassword123!"
        )
        self.owner_tokens = get_tokens_for_user(self.owner)

        # 2. Staff Member / Receptionist
        self.staff = User.objects.create_user(
            email="reception@apollodental.com",
            phone_number="+919876500021",
            first_name="Sunita",
            last_name="Rao",
            password="StrongPassword123!"
        )
        self.staff_tokens = get_tokens_for_user(self.staff)

        # 3. External User (another clinic)
        self.external_user = User.objects.create_user(
            email="external@otherclinic.com",
            phone_number="+919876500022",
            password="StrongPassword123!"
        )
        self.external_tokens = get_tokens_for_user(self.external_user)

        # 4. Practice: Apollo Dental Care
        self.practice = Practice.objects.create(
            name="Apollo Dental Care",
            slug="apollo-dental-care-hyd",
            owner=self.owner,
            phone_number="+919876543210",
            email="contact@apollodental.com",
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

        # 5. Doctor Profile & Schedule
        self.doctor_profile = DoctorProfile.objects.create(
            user=self.owner,
            title="Dr.",
            specialization="Endodontics & Dental Surgery",
            qualifications="BDS, MDS",
            medical_license_number="DCI-TEL-98234",
            is_verified=True
        )

        # Next upcoming Wednesday for deterministic schedule testing
        today = datetime.date.today()
        # Find next Wednesday (weekday=2)
        days_ahead = (2 - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        self.test_wednesday = today + datetime.timedelta(days=days_ahead)

        # Doctor Schedule for Wednesday (day_of_week=2): 09:00 - 13:00 Morning OPD
        self.schedule = DoctorSchedule.objects.create(
            practice=self.practice,
            doctor=self.doctor_profile,
            day_of_week=2,  # Wednesday
            session_name="Morning OPD",
            start_time=datetime.time(9, 0),
            end_time=datetime.time(13, 0),
            slot_duration_minutes=15,
            is_active=True
        )

        # 6. Practice Service
        self.service = PracticeService.objects.create(
            practice=self.practice,
            doctor=self.doctor_profile,
            name="Root Canal Consultation",
            duration_minutes=30,
            price=800.00,
            is_active=True
        )

        # 7. Practice Location / Branch
        self.main_location = PracticeLocation.objects.create(
            practice=self.practice,
            name="Jubilee Hills Main Clinic",
            code="JH-01",
            address="Road No 36, Jubilee Hills",
            city="Hyderabad",
            state="Telangana",
            postal_code="500033",
            phone_number="+919876543210",
            is_primary=True,
            is_active=True
        )

        # 8. Second Practice for Tenant Isolation
        self.other_practice = Practice.objects.create(
            name="City Healthcare",
            slug="city-healthcare",
            owner=self.external_user,
            is_active=True
        )
        self.other_membership = PracticeMembership.objects.create(
            practice=self.other_practice,
            user=self.external_user,
            role=PracticeMembership.ROLE_OWNER,
            is_active=True
        )

    # -------------------------------------------------------------
    # 1. PRACTICE LOCATIONS MANAGEMENT
    # -------------------------------------------------------------
    def test_practice_location_management_and_primary_switch(self):
        """Admin creates locations; primary flag cleanly switches."""
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.owner_tokens['access']}",
            HTTP_X_PRACTICE_ID=str(self.practice.id)
        )
        url = reverse('bookings:location_list_create')

        # Create secondary branch
        payload = {
            "name": "Gachibowli Branch Clinic",
            "code": "GB-02",
            "address": "Financial District",
            "city": "Hyderabad",
            "is_primary": True  # Should switch primary from Jubilee Hills to Gachibowli
        }
        res = self.client.post(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        new_loc_id = res.data['id']
        new_loc = PracticeLocation.objects.get(id=new_loc_id)
        self.assertTrue(new_loc.is_primary)

        # Main location should now have is_primary=False
        self.main_location.refresh_from_db()
        self.assertFalse(self.main_location.is_primary)

    def test_location_tenant_isolation(self):
        """Staff from another practice cannot see or edit locations."""
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.external_tokens['access']}",
            HTTP_X_PRACTICE_ID=str(self.other_practice.id)
        )
        url = reverse('bookings:location_detail', kwargs={'pk': self.main_location.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # -------------------------------------------------------------
    # 2. PUBLIC BOOKING REQUESTS & PREFERENCES
    # -------------------------------------------------------------
    def test_public_booking_request_creation_and_preferences(self):
        """Patient submits booking request with preferences (location, doctor, service, mode)."""
        url = reverse('bookings:public_request', kwargs={'practice_slug_or_domain': self.practice.slug})
        payload = {
            "patient_name": "Meera Nambiar",
            "phone_number": "+919876512345",
            "email": "meera@gmail.com",
            "gender": "female",
            "age": 29,
            "location_id": str(self.main_location.id),
            "doctor_id": str(self.doctor_profile.id),
            "service_id": str(self.service.id),
            "consultation_mode": BookingRequest.MODE_IN_PERSON,
            "preferred_date": str(self.test_wednesday),
            "preferred_time_window": BookingRequest.WINDOW_MORNING,
            "chief_complaint": "Severe wisdom tooth ache on upper left molar.",
            "patient_notes": "Please arrange ground floor consultation if possible.",
            "consent_given": True
        }

        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
        self.assertIn('booking_reference', response.data)
        self.assertEqual(response.data['status'], BookingRequest.STATUS_REQUESTED)

        # Verify database record
        booking = BookingRequest.objects.get(booking_reference=response.data['booking_reference'])
        self.assertEqual(booking.patient_name, "Meera Nambiar")
        self.assertEqual(booking.doctor, self.doctor_profile)
        self.assertEqual(booking.location, self.main_location)
        self.assertEqual(booking.service, self.service)
        self.assertEqual(booking.consultation_mode, BookingRequest.MODE_IN_PERSON)
        self.assertEqual(booking.preferred_time_window, BookingRequest.WINDOW_MORNING)
        self.assertEqual(booking.status, BookingRequest.STATUS_REQUESTED)

        # Check initial audit timeline
        self.assertEqual(booking.timeline.count(), 1)
        self.assertEqual(booking.timeline.first().action, 'requested')

        # Check Lead CRM sync
        self.assertIsNotNone(booking.lead)
        self.assertEqual(booking.lead.patient_name, "Meera Nambiar")

    # -------------------------------------------------------------
    # 3. SESSION / TOKEN MODE & SEQUENTIAL NUMBERING
    # -------------------------------------------------------------
    def test_session_token_mode_queue_and_sequential_numbering(self):
        """Bookings in Token Mode receive sequential token numbers within OPD session."""
        # Configure doctor capacity: Token Mode for "Morning OPD", max 20 tokens
        DoctorSessionCapacity.objects.create(
            practice=self.practice,
            doctor=self.doctor_profile,
            session_name="Morning OPD",
            booking_mode=DoctorSessionCapacity.MODE_TOKEN,
            max_tokens_per_session=20
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.staff_tokens['access']}",
            HTTP_X_PRACTICE_ID=str(self.practice.id)
        )

        # Book Token #1
        b1 = BookingRequest.objects.create(
            practice=self.practice,
            doctor=self.doctor_profile,
            location=self.main_location,
            patient_name="Patient One",
            phone_number="+919876500001",
            preferred_date=self.test_wednesday,
            appointment_date=self.test_wednesday,
            booking_mode=BookingRequest.SCHEDULING_MODE_TOKEN,
            session_name="Morning OPD",
            status=BookingRequest.STATUS_REQUESTED
        )
        url_confirm = reverse('bookings:booking_confirm', kwargs={'pk': b1.id})
        res1 = self.client.post(url_confirm, {"session_name": "Morning OPD"}, format='json')
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertEqual(res1.data['token_number'], 1)

        # Book Token #2
        b2 = BookingRequest.objects.create(
            practice=self.practice,
            doctor=self.doctor_profile,
            location=self.main_location,
            patient_name="Patient Two",
            phone_number="+919876500002",
            preferred_date=self.test_wednesday,
            appointment_date=self.test_wednesday,
            booking_mode=BookingRequest.SCHEDULING_MODE_TOKEN,
            session_name="Morning OPD",
            status=BookingRequest.STATUS_REQUESTED
        )
        url_confirm2 = reverse('bookings:booking_confirm', kwargs={'pk': b2.id})
        res2 = self.client.post(url_confirm2, {"session_name": "Morning OPD"}, format='json')
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.data['token_number'], 2)

    # -------------------------------------------------------------
    # 4. CAPACITY CHECKS (TOKEN MODE QUOTA & TIME-SLOT COLLISIONS)
    # -------------------------------------------------------------
    def test_token_capacity_check_prevents_overbooking(self):
        """Token mode enforces max_tokens_per_session cap and blocks excess bookings."""
        # Set max tokens cap = 2 for testing
        DoctorSessionCapacity.objects.create(
            practice=self.practice,
            doctor=self.doctor_profile,
            session_name="Morning OPD",
            booking_mode=DoctorSessionCapacity.MODE_TOKEN,
            max_tokens_per_session=2
        )

        # Fill quota with 2 confirmed tokens
        for i in range(1, 3):
            BookingRequest.objects.create(
                practice=self.practice,
                doctor=self.doctor_profile,
                patient_name=f"Patient {i}",
                phone_number=f"+91987650009{i}",
                preferred_date=self.test_wednesday,
                appointment_date=self.test_wednesday,
                booking_mode=BookingRequest.SCHEDULING_MODE_TOKEN,
                session_name="Morning OPD",
                token_number=i,
                status=BookingRequest.STATUS_CONFIRMED
            )

        # 3rd booking attempts confirmation -> should fail with capacity error
        b3 = BookingRequest.objects.create(
            practice=self.practice,
            doctor=self.doctor_profile,
            patient_name="Patient 3",
            phone_number="+919876500093",
            preferred_date=self.test_wednesday,
            appointment_date=self.test_wednesday,
            booking_mode=BookingRequest.SCHEDULING_MODE_TOKEN,
            session_name="Morning OPD",
            status=BookingRequest.STATUS_REQUESTED
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.staff_tokens['access']}",
            HTTP_X_PRACTICE_ID=str(self.practice.id)
        )
        url = reverse('bookings:booking_confirm', kwargs={'pk': b3.id})
        res = self.client.post(url, {"session_name": "Morning OPD"}, format='json')

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("maximum quota", res.data['error'])

    def test_time_slot_mode_prevents_slot_collision(self):
        """Time-slot mode prevents double booking on the same doctor and time."""
        # Confirm booking at 10:00 AM
        BookingRequest.objects.create(
            practice=self.practice,
            doctor=self.doctor_profile,
            patient_name="Original Booker",
            phone_number="+919876500111",
            preferred_date=self.test_wednesday,
            appointment_date=self.test_wednesday,
            booking_mode=BookingRequest.SCHEDULING_MODE_SLOT,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(10, 15),
            status=BookingRequest.STATUS_CONFIRMED
        )

        # Second booking requesting the exact same slot 10:00 AM
        b2 = BookingRequest.objects.create(
            practice=self.practice,
            doctor=self.doctor_profile,
            patient_name="Conflicting Booker",
            phone_number="+919876500222",
            preferred_date=self.test_wednesday,
            appointment_date=self.test_wednesday,
            booking_mode=BookingRequest.SCHEDULING_MODE_SLOT,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(10, 15),
            status=BookingRequest.STATUS_REQUESTED
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.staff_tokens['access']}",
            HTTP_X_PRACTICE_ID=str(self.practice.id)
        )
        url = reverse('bookings:booking_confirm', kwargs={'pk': b2.id})
        res = self.client.post(url, {
            "confirmed_date": str(self.test_wednesday),
            "start_time": "10:00:00",
            "end_time": "10:15:00"
        }, format='json')

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already booked", res.data['error'])

    # -------------------------------------------------------------
    # 5. CLINIC CONFIRMATION WORKFLOW
    # -------------------------------------------------------------
    def test_clinic_confirmation_workflow(self):
        """Clinic staff confirms pending booking and assigns confirmed slot."""
        booking = BookingRequest.objects.create(
            practice=self.practice,
            doctor=self.doctor_profile,
            location=self.main_location,
            service=self.service,
            patient_name="Rahul Dravid",
            phone_number="+919876500333",
            preferred_date=self.test_wednesday,
            booking_mode=BookingRequest.SCHEDULING_MODE_SLOT,
            status=BookingRequest.STATUS_REQUESTED
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.staff_tokens['access']}",
            HTTP_X_PRACTICE_ID=str(self.practice.id)
        )
        url = reverse('bookings:booking_confirm', kwargs={'pk': booking.id})
        payload = {
            "confirmed_date": str(self.test_wednesday),
            "start_time": "11:15:00",
            "end_time": "11:30:00",
            "clinic_notes": "Confirmed consultation with Dr. Rajesh Sharma."
        }

        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], BookingRequest.STATUS_CONFIRMED)
        self.assertEqual(response.data['start_time'], "11:15:00")

        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingRequest.STATUS_CONFIRMED)
        self.assertEqual(booking.confirmed_by, self.staff)
        self.assertIsNotNone(booking.confirmed_at)

        # Check timeline entry
        timeline_actions = [t.action for t in booking.timeline.all()]
        self.assertIn('confirmed', timeline_actions)

    # -------------------------------------------------------------
    # 6. RESCHEDULING & CANCELLATION
    # -------------------------------------------------------------
    def test_reschedule_and_cancellation_workflow(self):
        """Reschedule appointment to new date/time and test cancellation."""
        booking = BookingRequest.objects.create(
            practice=self.practice,
            doctor=self.doctor_profile,
            patient_name="Smriti Mandhana",
            phone_number="+919876500444",
            preferred_date=self.test_wednesday,
            appointment_date=self.test_wednesday,
            start_time=datetime.time(9, 30),
            end_time=datetime.time(9, 45),
            status=BookingRequest.STATUS_CONFIRMED
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.staff_tokens['access']}",
            HTTP_X_PRACTICE_ID=str(self.practice.id)
        )

        # 1. Reschedule
        reschedule_url = reverse('bookings:booking_reschedule', kwargs={'pk': booking.id})
        res_reschedule = self.client.post(reschedule_url, {
            "new_date": str(self.test_wednesday),
            "new_start_time": "11:45:00",
            "new_end_time": "12:00:00",
            "reason": "Patient requested later morning slot"
        }, format='json')
        self.assertEqual(res_reschedule.status_code, status.HTTP_200_OK)
        self.assertEqual(res_reschedule.data['status'], BookingRequest.STATUS_RESCHEDULED)

        # 2. Cancel
        cancel_url = reverse('bookings:booking_cancel', kwargs={'pk': booking.id})
        res_cancel = self.client.post(cancel_url, {
            "reason": "Patient called to cancel due to travel"
        }, format='json')
        self.assertEqual(res_cancel.status_code, status.HTTP_200_OK)
        self.assertEqual(res_cancel.data['status'], BookingRequest.STATUS_CANCELLED)

        booking.refresh_from_db()
        self.assertEqual(booking.status, BookingRequest.STATUS_CANCELLED)
        self.assertIsNotNone(booking.cancelled_at)

    # -------------------------------------------------------------
    # 7. VISIT STATUS LIFECYCLE (CHECKED IN -> COMPLETED)
    # -------------------------------------------------------------
    def test_visit_status_lifecycle(self):
        """Update appointment visit status from confirmed to checked-in and completed."""
        booking = BookingRequest.objects.create(
            practice=self.practice,
            doctor=self.doctor_profile,
            patient_name="Neeraj Chopra",
            phone_number="+919876500555",
            preferred_date=self.test_wednesday,
            appointment_date=self.test_wednesday,
            status=BookingRequest.STATUS_CONFIRMED
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.staff_tokens['access']}",
            HTTP_X_PRACTICE_ID=str(self.practice.id)
        )
        url = reverse('bookings:booking_visit_status', kwargs={'pk': booking.id})

        # Check-in
        res1 = self.client.post(url, {"status": BookingRequest.STATUS_CHECKED_IN, "notes": "Patient waiting in room 3"}, format='json')
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertEqual(res1.data['status'], BookingRequest.STATUS_CHECKED_IN)

        # Complete
        res2 = self.client.post(url, {"status": BookingRequest.STATUS_COMPLETED, "notes": "Consultation done. Prescribed antibiotics."}, format='json')
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.data['status'], BookingRequest.STATUS_COMPLETED)

    # -------------------------------------------------------------
    # 8. PUBLIC AVAILABILITY & TRACKING
    # -------------------------------------------------------------
    def test_public_availability_overview_and_tracking(self):
        """Public endpoint returns available sessions/slots and tracks booking by ref."""
        avail_url = reverse('bookings:public_availability', kwargs={'practice_slug_or_domain': self.practice.slug})
        res_avail = self.client.get(f"{avail_url}?doctor_id={self.doctor_profile.id}&date={self.test_wednesday}")
        self.assertEqual(res_avail.status_code, status.HTTP_200_OK)
        self.assertTrue(res_avail.data['is_available'])
        self.assertIn('sessions', res_avail.data)
        self.assertIn('time_slots', res_avail.data)

        # Create booking to track
        booking = BookingRequest.objects.create(
            practice=self.practice,
            patient_name="Tracking Tester",
            phone_number="+919876500666",
            preferred_date=self.test_wednesday
        )
        track_url = reverse('bookings:public_track', kwargs={
            'practice_slug_or_domain': self.practice.slug,
            'booking_reference': booking.booking_reference
        })
        res_track = self.client.get(track_url)
        self.assertEqual(res_track.status_code, status.HTTP_200_OK)
        self.assertEqual(res_track.data['booking_reference'], booking.booking_reference)

    # -------------------------------------------------------------
    # 9. BOOKING STATS & QUEUE COUNTERS
    # -------------------------------------------------------------
    def test_booking_stats_dashboard(self):
        """Stats endpoint calculates today's queues, pending requests, and confirmation counts."""
        BookingRequest.objects.create(practice=self.practice, patient_name="B1", phone_number="1", preferred_date=self.test_wednesday, status=BookingRequest.STATUS_REQUESTED)
        BookingRequest.objects.create(practice=self.practice, patient_name="B2", phone_number="2", preferred_date=self.test_wednesday, status=BookingRequest.STATUS_CONFIRMED)
        BookingRequest.objects.create(practice=self.practice, patient_name="B3", phone_number="3", preferred_date=self.test_wednesday, status=BookingRequest.STATUS_COMPLETED)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {self.owner_tokens['access']}",
            HTTP_X_PRACTICE_ID=str(self.practice.id)
        )
        url = reverse('bookings:booking_stats')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_bookings'], 3)
        self.assertEqual(response.data['pending_confirmation_count'], 1)
        self.assertEqual(response.data['confirmed_count'], 1)
        self.assertEqual(response.data['completed_count'], 1)

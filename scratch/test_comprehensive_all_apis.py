import os
import sys
import json
import uuid
import random
from decimal import Decimal

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ClinicRise.settings')
django.setup()

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from authentication.models import User
from authentication.services.jwt_service import get_tokens_for_user
from practices.models import Practice, PracticeMembership, DoctorProfile
from gbp.models import GoogleReview, LocalRankKeyword
from billing.models import SubscriptionPlan
from websites.models import ClinicWebsite, WebsitePage, CustomDomain
from websites.services.approval_service import ContentApprovalService

def test_all_apis():
    print("=" * 90)
    print("STARTING CLINICRISE COMPREHENSIVE END-TO-END API TEST SUITE ACROSS ALL 10 PHASES")
    print("=" * 90)

    client = APIClient()
    public_client = APIClient()
    test_log = []

    def log_call(phase, step_name, method, url, request_body, response, expected_statuses, notes=""):
        status_code = response.status_code
        passed = status_code in expected_statuses

        try:
            resp_data = response.json()
        except Exception:
            if 'application/pdf' in response.get('Content-Type', ''):
                resp_data = f"<Binary PDF Stream: {len(response.content)} bytes>"
            elif 'text/html' in response.get('Content-Type', ''):
                resp_data = f"<HTML Document: {len(response.content)} bytes, Preview: {response.content.decode('utf-8', errors='ignore')[:150]}...>"
            else:
                resp_data = response.content.decode('utf-8', errors='ignore')[:300]

        entry = {
            "phase": phase,
            "step": step_name,
            "method": method,
            "url": url,
            "request_body": request_body,
            "status_code": status_code,
            "expected_statuses": expected_statuses,
            "passed": passed,
            "response": resp_data,
            "notes": notes
        }
        test_log.append(entry)

        status_str = "PASSED [OK]" if passed else "FAILED [X]"
        print(f"[{status_str}] Phase {phase} - {step_name}: {method} {url} -> Status {status_code} (Expected {expected_statuses})")
        return resp_data, passed

    unique_num = random.randint(100000, 999999)
    test_phone = f"+9198{random.randint(10000000, 99999999)}"
    patient_phone = f"+9198{random.randint(10000000, 99999999)}"
    staff_phone = f"+9198{random.randint(10000000, 99999999)}"
    test_email = f"dr.aditi_{unique_num}@arogyaclinic.com"
    staff_email = f"reception_{unique_num}@arogyaclinic.com"
    clinic_subdomain = f"arogya{unique_num}"

    # =========================================================================
    # PHASE 1: DOCTOR ONBOARDING & SETUP
    # =========================================================================
    print("\n--- PHASE 1: DOCTOR ONBOARDING & SETUP ---")

    # 1.1 Request OTP
    req_body_1_1 = {"phone_number": test_phone, "purpose": "login"}
    res = public_client.post("/api/auth/otp/send/", req_body_1_1, format="json")
    resp_1_1, _ = log_call(1, "1.1 Mobile OTP - Request Code", "POST", "/api/auth/otp/send/", req_body_1_1, res, [200])
    otp_code = resp_1_1.get("dev_otp", "123456") if isinstance(resp_1_1, dict) else "123456"

    # 1.2 Verify OTP & Issue Tokens
    req_body_1_2 = {"phone_number": test_phone, "otp_code": otp_code, "purpose": "login"}
    res = public_client.post("/api/auth/otp/verify/", req_body_1_2, format="json")
    resp_1_2, _ = log_call(1, "1.2 Mobile OTP - Verify & Issue JWT Session", "POST", "/api/auth/otp/verify/", req_body_1_2, res, [200])
    tokens = resp_1_2.get("tokens", {}) if isinstance(resp_1_2, dict) else {}
    access_token = tokens.get("access")
    doctor_user = User.objects.get(id=resp_1_2.get("user", {}).get("id"))

    # Authenticate main client
    if access_token:
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

    # 1.3 Google Sign-In Alternative
    req_body_1_3 = {"id_token": f"mock-google:{test_email}"}
    res_google = public_client.post("/api/auth/google/", req_body_1_3, format="json")
    log_call(1, "1.3 Alternative Auth: Google Sign-In", "POST", "/api/auth/google/", req_body_1_3, res_google, [200])

    # 1.4 Wizard Progress
    res = client.get("/api/practices/onboarding/progress/")
    log_call(1, "1.4 Wizard - Track Progress Initial", "GET", "/api/practices/onboarding/progress/", None, res, [200])

    # 1.5 Step 1: Doctor Profile
    req_body_1_5 = {
        "first_name": "Aditi",
        "last_name": "Sharma",
        "title": "Dr.",
        "gender": "female",
        "medical_license_number": f"MCI-2015-{unique_num}",
        "registration_council": "Maharashtra Medical Council",
        "registration_year": 2015,
        "specialization": "Dermatology & Cosmetology",
        "qualifications": "MBBS, MD (Dermatology)",
        "experience_years": 11,
        "languages_spoken": "English, Hindi, Marathi",
        "bio": "Dr. Aditi Sharma is a board-certified Dermatologist specializing in clinical dermatology and laser skin treatments.",
        "default_consultation_fee": 800.00
    }
    res = client.post("/api/practices/onboarding/step/doctor-profile/", req_body_1_5, format="json")
    log_call(1, "1.5 Step 1: Doctor Profile & License", "POST", "/api/practices/onboarding/step/doctor-profile/", req_body_1_5, res, [200])
    doctor_profile = DoctorProfile.objects.filter(user=doctor_user).first()

    # 1.6 Step 2: Clinic Details
    req_body_1_6 = {
        "name": f"Arogya Skin Clinic {unique_num}",
        "clinic_type": "solo_clinic",
        "tagline": "Advanced Dermatological Care & Aesthetic Wellness",
        "about": "Arogya Clinic provides evidence-based clinical dermatology and cutting-edge aesthetic care in Mumbai.",
        "phone_number": test_phone,
        "email": test_email,
        "website": "https://arogyaclinic.com",
        "address": "Shop 4, Sunrise Heights, Linking Road, Bandra West",
        "landmark": "Opposite National College",
        "city": "Mumbai",
        "state": "Maharashtra",
        "postal_code": "400050",
        "country": "India",
        "established_year": 2018,
        "currency": "INR",
        "timezone": "Asia/Kolkata"
    }
    res = client.post("/api/practices/onboarding/step/clinic-details/", req_body_1_6, format="json")
    resp_1_6, _ = log_call(1, "1.6 Step 2: Clinic & Practice Details", "POST", "/api/practices/onboarding/step/clinic-details/", req_body_1_6, res, [200])
    practice_data = resp_1_6.get("practice", {}) if isinstance(resp_1_6, dict) else {}
    practice_id = practice_data.get("id")
    practice_slug = practice_data.get("slug")

    # Set tenant header for subsequent requests
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        HTTP_X_PRACTICE_ID=str(practice_id)
    )

    # 1.7 Step 3: Services
    req_body_1_7 = {
        "services": [
            {
                "name": "General Dermatology Consultation",
                "category": "consultation",
                "description": "Comprehensive evaluation of skin conditions.",
                "duration_minutes": 20,
                "price": 800.00,
                "is_teleconsultation": True
            },
            {
                "name": "Acne & Scar Laser Treatment",
                "category": "procedure",
                "description": "Fractional CO2 laser therapy.",
                "duration_minutes": 45,
                "price": 3500.00,
                "is_teleconsultation": False
            }
        ]
    }
    res = client.post("/api/practices/onboarding/step/services/", req_body_1_7, format="json")
    log_call(1, "1.7 Step 3: Clinical Services Catalog", "POST", "/api/practices/onboarding/step/services/", req_body_1_7, res, [200])

    # 1.8 Step 4: Timings
    req_body_1_8 = {
        "timings": [
            {"day_of_week": 0, "session_name": "Morning OPD", "start_time": "10:00:00", "end_time": "13:30:00", "slot_duration_minutes": 20},
            {"day_of_week": 0, "session_name": "Evening Clinic", "start_time": "17:00:00", "end_time": "20:30:00", "slot_duration_minutes": 20},
            {"day_of_week": 5, "session_name": "Weekend Special OPD", "start_time": "10:00:00", "end_time": "15:00:00", "slot_duration_minutes": 20}
        ]
    }
    res = client.post("/api/practices/onboarding/step/timings/", req_body_1_8, format="json")
    log_call(1, "1.8 Step 4: OPD Consultation Timings", "POST", "/api/practices/onboarding/step/timings/", req_body_1_8, res, [200])

    # 1.9 Step 5: Images
    req_body_1_9 = {
        "doctor_avatar_url": "https://clinicrise-media.s3.amazonaws.com/doctors/dr-aditi.jpg",
        "registration_certificate_url": "https://clinicrise-media.s3.amazonaws.com/certs/mci-cert.pdf",
        "images": [
            {
                "image_url": "https://clinicrise-media.s3.amazonaws.com/clinic/reception.jpg",
                "image_type": "reception",
                "caption": "Executive Patient Waiting Lounge & Reception",
                "is_primary": True,
                "order": 1
            }
        ]
    }
    res = client.post("/api/practices/onboarding/step/images/", req_body_1_9, format="json")
    log_call(1, "1.9 Step 5: Clinic Photos & Verification Documents", "POST", "/api/practices/onboarding/step/images/", req_body_1_9, res, [200])

    # 1.10 Finalize Onboarding
    res = client.post("/api/practices/onboarding/complete/", {}, format="json")
    log_call(1, "1.10 Finalize Doctor Onboarding", "POST", "/api/practices/onboarding/complete/", {}, res, [200])

    # 1.11 Staff Invitation
    req_body_1_11 = {
        "identifier": staff_email,
        "role": "staff"
    }
    res = client.post(f"/api/practices/{practice_id}/invite/", req_body_1_11, format="json")
    resp_1_11, _ = log_call(1, "1.11 Practice Staff Invitation", "POST", f"/api/practices/{practice_id}/invite/", req_body_1_11, res, [201])
    invite_code = resp_1_11.get("invite_code") if isinstance(resp_1_11, dict) else None

    # 1.12 Accept Invitation
    if invite_code:
        staff_user = User.objects.create_user(
            email=staff_email,
            phone_number=staff_phone,
            password="StaffPassword123!"
        )
        staff_client = APIClient()
        staff_tokens = get_tokens_for_user(staff_user)
        staff_client.credentials(HTTP_AUTHORIZATION=f"Bearer {staff_tokens['access']}")
        req_body_1_12 = {"invite_code": invite_code}
        res = staff_client.post("/api/practices/invitations/accept/", req_body_1_12, format="json")
        log_call(1, "1.12 Accept Staff Invitation", "POST", "/api/practices/invitations/accept/", req_body_1_12, res, [200])

    # =========================================================================
    # PHASE 2: AUTOMATED WEBSITE ENGINE & CONTENT APPROVALS
    # =========================================================================
    print("\n--- PHASE 2: AUTOMATED WEBSITE ENGINE & CONTENT APPROVALS ---")

    # 2.1 1-Click Clinic Website Auto-Generation
    req_body_2_1 = {
        "practice_id": str(practice_id),
        "subdomain": clinic_subdomain,
        "template_style": "modern_minimal",
        "auto_publish": True
    }
    res = client.post("/api/websites/generate/", req_body_2_1, format="json")
    resp_2_1, _ = log_call(2, "2.1 1-Click Clinic Website Generation", "POST", "/api/websites/generate/", req_body_2_1, res, [201])
    website_id = resp_2_1.get("website", {}).get("id") if isinstance(resp_2_1, dict) else None

    # 2.2 Live Website Public Rendering
    res = public_client.get(f"/api/websites/public/{clinic_subdomain}/")
    log_call(2, "2.2 Live Website Public Rendering", "GET", f"/api/websites/public/{clinic_subdomain}/", None, res, [200])

    # 2.3 Custom Domain Connection
    custom_domain_name = f"drsharma{unique_num}.com"
    req_body_2_3 = {"domain": custom_domain_name}
    res = client.post(f"/api/websites/{website_id}/domains/", req_body_2_3, format="json")
    resp_2_3, _ = log_call(2, "2.3 Custom Domain Connection", "POST", f"/api/websites/{website_id}/domains/", req_body_2_3, res, [201])
    domain_id = resp_2_3.get("domain", {}).get("id") if isinstance(resp_2_3, dict) else None

    # 2.4 Custom Domain Verification
    if domain_id:
        res = client.post(f"/api/websites/{website_id}/domains/{domain_id}/verify/", {"simulate": True}, format="json")
        log_call(2, "2.4 DNS Domain Verification", "POST", f"/api/websites/{website_id}/domains/{domain_id}/verify/", {"simulate": True}, res, [200])

    # Create a custom page and submit it for review
    test_page = WebsitePage.objects.create(
        website_id=website_id,
        title="Laser Hair Removal Treatments",
        slug=f"laser-hair-removal-{unique_num}",
        page_type=WebsitePage.PAGE_TYPE_SERVICES,
        draft_content={"sections": [{"heading": "Advanced Laser Hair Reduction"}]},
        is_published=False
    )
    ContentApprovalService.submit_for_review(test_page, doctor_user, submission_notes="Added clinical laser description")

    # 2.5 Approval Queue
    res = client.get(f"/api/websites/{website_id}/approvals/")
    log_call(2, "2.5 Unified Content Approval Queue", "GET", f"/api/websites/{website_id}/approvals/", None, res, [200])

    # 2.6 Doctor Review & Approve Page
    req_body_2_6 = {
        "action": "approve",
        "review_notes": "Medically verified by Dr. Aditi Sharma. Approved for public publishing."
    }
    res = client.post(f"/api/websites/{website_id}/pages/{test_page.id}/review/", req_body_2_6, format="json")
    log_call(2, "2.6 Doctor Review & Approve Page", "POST", f"/api/websites/{website_id}/pages/{test_page.id}/review/", req_body_2_6, res, [200])

    # 2.7 Publish Page
    res = client.post(f"/api/websites/{website_id}/pages/{test_page.id}/publish/", {}, format="json")
    log_call(2, "2.7 Publish Approved Page", "POST", f"/api/websites/{website_id}/pages/{test_page.id}/publish/", {}, res, [200])

    # =========================================================================
    # PHASE 3: DIGITAL PRESENCE, GOOGLE BUSINESS PROFILE & SEO
    # =========================================================================
    print("\n--- PHASE 3: DIGITAL PRESENCE, GBP & SEO ---")

    # 3.1 10-Step Google Business Profile Checklist
    res = client.get("/api/gbp/checklist/")
    log_call(3, "3.1 10-Step GBP Setup Checklist", "GET", "/api/gbp/checklist/", None, res, [200])

    # Seed mock review & keywords for practice
    mock_review = GoogleReview.objects.create(
        practice_id=practice_id,
        review_id=f"g_rev_{unique_num}",
        reviewer_name="Rohan Deshmukh",
        star_rating=5,
        comment="Dr. Aditi Sharma is wonderful! My acne cleared up completely within 6 weeks. Very polite staff.",
        review_timestamp=timezone.now()
    )
    LocalRankKeyword.objects.create(
        practice_id=practice_id,
        keyword="dermatologist in bandra",
        target_city="Mumbai",
        is_active=True
    )

    # 3.2 List Patient Reviews
    res = client.get("/api/gbp/reviews/")
    log_call(3, "3.2 List Google Patient Reviews", "GET", "/api/gbp/reviews/", None, res, [200])

    # 3.3 AI Empathetic Clinical Reply Generation
    res = client.post(f"/api/gbp/reviews/{mock_review.id}/generate-reply/", {}, format="json")
    resp_3_3, _ = log_call(3, "3.3 AI Empathetic Reply Generation", "POST", f"/api/gbp/reviews/{mock_review.id}/generate-reply/", {}, res, [200])
    ai_reply_text = resp_3_3.get("ai_suggested_reply", "Thank you for visiting Arogya Clinic!") if isinstance(resp_3_3, dict) else "Thank you!"

    # 3.4 Post Review Reply
    req_body_3_4 = {"reply_text": ai_reply_text}
    res = client.post(f"/api/gbp/reviews/{mock_review.id}/reply/", req_body_3_4, format="json")
    log_call(3, "3.4 Publish Review Reply to Google", "POST", f"/api/gbp/reviews/{mock_review.id}/reply/", req_body_3_4, res, [200])

    # 3.5 Local SEO 3-Pack Rank Tracking Check
    res = client.post("/api/gbp/rank-tracking/check/", {}, format="json")
    log_call(3, "3.5 Local SEO 3-Pack Rank Audit Check", "POST", "/api/gbp/rank-tracking/check/", {}, res, [200])

    # =========================================================================
    # PHASE 4: PATIENT LEAD INGESTION & PIPELINE
    # =========================================================================
    print("\n--- PHASE 4: PATIENT LEAD INGESTION & PIPELINE ---")

    # 4.1 Public Website Visit Tracking
    req_body_4_1 = {
        "page_url": f"https://{clinic_subdomain}.clinicrise.com/services/acne-treatment",
        "referrer": "https://www.google.com/",
        "utm_source": "google",
        "utm_medium": "cpc",
        "utm_campaign": "skin_acne_promo",
        "device_type": "mobile",
        "visitor_id": f"v_{unique_num}"
    }
    res = public_client.post(f"/api/analytics/public/{practice_slug}/visit/", req_body_4_1, format="json")
    log_call(4, "4.1 Public Website Visit Tracking", "POST", f"/api/analytics/public/{practice_slug}/visit/", req_body_4_1, res, [201])

    # 4.2 Track Public WhatsApp Button Click
    req_body_4_2 = {
        "event_type": "whatsapp_click",
        "page_url": f"https://{clinic_subdomain}.clinicrise.com/",
        "device_type": "mobile",
        "visitor_id": f"v_{unique_num}"
    }
    res = public_client.post(f"/api/leads/public/{practice_slug}/click-event/", req_body_4_2, format="json")
    log_call(4, "4.2 Track Public WhatsApp Click Event", "POST", f"/api/leads/public/{practice_slug}/click-event/", req_body_4_2, res, [201])

    # 4.3 Public Patient Inquiry Form Submission
    req_body_4_3 = {
        "patient_name": "Pooja Verma",
        "phone_number": patient_phone,
        "email": f"pooja_{unique_num}@example.com",
        "service_requested": "Acne & Scar Laser Treatment",
        "preferred_date": str(timezone.now().date()),
        "preferred_time_slot": "Evening (5 PM - 8 PM)",
        "message": "Suffering from hormonal acne breakouts for 6 months. Would like consultation with Dr. Aditi.",
        "consent_given": True,
        "whatsapp_opt_in": True,
        "utm_source": "google",
        "utm_campaign": "skin_acne_promo"
    }
    res = public_client.post(f"/api/leads/public/{practice_slug}/inquire/", req_body_4_3, format="json")
    resp_4_3, _ = log_call(4, "4.3 Public Patient Inquiry Form", "POST", f"/api/leads/public/{practice_slug}/inquire/", req_body_4_3, res, [201])
    lead_id = resp_4_3.get("lead_id") if isinstance(resp_4_3, dict) else None

    # 4.4 Staff CRM Lead Inbox
    res = client.get("/api/leads/inbox/?status=new")
    log_call(4, "4.4 Clinic Staff CRM Lead Inbox", "GET", "/api/leads/inbox/?status=new", None, res, [200])

    # 4.5 Lead Pipeline Status Update (POST endpoint)
    if lead_id:
        req_body_4_5 = {
            "status": "contacted",
            "note": "Spoke with Pooja. Confirmed appointment preference for Saturday with Dr. Aditi."
        }
        res = client.post(f"/api/leads/{lead_id}/status/", req_body_4_5, format="json")
        log_call(4, "4.5 Lead Pipeline Status Transition", "POST", f"/api/leads/{lead_id}/status/", req_body_4_5, res, [200])

    # =========================================================================
    # PHASE 5: BOOKING REQUESTS & APPOINTMENT LIFECYCLE
    # =========================================================================
    print("\n--- PHASE 5: BOOKING REQUESTS & APPOINTMENT LIFECYCLE ---")

    today_str = str(timezone.now().date())
    # 5.1 Realtime Availability Check (with doctor_id)
    doc_query = f"?doctor_id={doctor_profile.id}&date={today_str}" if doctor_profile else f"?date={today_str}"
    res = public_client.get(f"/api/bookings/public/{practice_slug}/availability/{doc_query}")
    log_call(5, "5.1 Realtime Doctor Availability Check", "GET", f"/api/bookings/public/{practice_slug}/availability/{doc_query}", None, res, [200])

    # 5.2 Public Booking Request Submission
    req_body_5_2 = {
        "patient_name": "Pooja Verma",
        "phone_number": patient_phone,
        "email": f"pooja_{unique_num}@example.com",
        "gender": "female",
        "age": 28,
        "consultation_mode": "in_person",
        "preferred_date": today_str,
        "preferred_time_window": "evening",
        "booking_mode": "slot",
        "session_name": "Evening Clinic",
        "start_time": "17:20:00",
        "chief_complaint": "Severe facial acne breakouts and post-inflammatory pigmentation.",
        "consent_given": True
    }
    res = public_client.post(f"/api/bookings/public/{practice_slug}/request/", req_body_5_2, format="json")
    resp_5_2, _ = log_call(5, "5.2 Public Booking Request Submission", "POST", f"/api/bookings/public/{practice_slug}/request/", req_body_5_2, res, [201])
    booking_ref = resp_5_2.get("booking_reference") if isinstance(resp_5_2, dict) else None

    from bookings.models import BookingRequest
    b_obj = BookingRequest.objects.filter(booking_reference=booking_ref).first()
    booking_id = str(b_obj.id) if b_obj else None

    # 5.3 Public Booking Tracking
    if booking_ref:
        res = public_client.get(f"/api/bookings/public/{practice_slug}/track/{booking_ref}/")
        log_call(5, "5.3 Public Booking Tracking by Reference", "GET", f"/api/bookings/public/{practice_slug}/track/{booking_ref}/", None, res, [200])

    # 5.4 Clinic Confirmation Workflow
    if booking_id:
        req_body_5_4 = {
            "confirmed_date": today_str,
            "start_time": "17:20:00",
            "end_time": "17:40:00",
            "session_name": "Evening Clinic",
            "token_number": 4,
            "clinic_notes": "Confirmed over phone. Advised to bring previous dermatological prescriptions."
        }
        res = client.post(f"/api/bookings/{booking_id}/confirm/", req_body_5_4, format="json")
        log_call(5, "5.4 Clinic Confirmation Workflow", "POST", f"/api/bookings/{booking_id}/confirm/", req_body_5_4, res, [200])

        # 5.5 Appointment Day: Patient Arrival & Visit Status
        req_body_5_5 = {
            "status": "in_consultation",
            "notes": "Patient checked in. Vitals recorded. Entering Doctor chamber."
        }
        res = client.post(f"/api/bookings/{booking_id}/visit-status/", req_body_5_5, format="json")
        log_call(5, "5.5 Patient Visit Status Lifecycle", "POST", f"/api/bookings/{booking_id}/visit-status/", req_body_5_5, res, [200])

    # =========================================================================
    # PHASE 6: PATIENT CRM & CLINICAL CHARTING
    # =========================================================================
    print("\n--- PHASE 6: PATIENT CRM & CLINICAL CHARTING ---")

    # 6.1 Convert Lead to Permanent Patient Record
    res = client.post(f"/api/patients/convert-lead/{lead_id}/", {}, format="json")
    resp_6_1, _ = log_call(6, "6.1 Convert Lead to Permanent Patient Chart", "POST", f"/api/patients/convert-lead/{lead_id}/", {}, res, [200, 201])
    patient_id = resp_6_1.get("patient", {}).get("id") if isinstance(resp_6_1, dict) else None

    if patient_id:
        # 6.2 Record Patient Vitals
        req_body_6_2 = {
            "blood_pressure_systolic": 118,
            "blood_pressure_diastolic": 76,
            "pulse_bpm": 74,
            "temperature_fahrenheit": 98.4,
            "oxygen_saturation_spo2": 99,
            "weight_kg": 56.5,
            "height_cm": 164.0,
            "notes": "Normal baseline vitals before laser procedure."
        }
        res = client.post(f"/api/patients/{patient_id}/vitals/", req_body_6_2, format="json")
        log_call(6, "6.2 Record Patient Vitals", "POST", f"/api/patients/{patient_id}/vitals/", req_body_6_2, res, [201])

        # 6.3 Clinical Notes & Pinned Alerts
        req_body_6_3 = {
            "category": "clinical",
            "note": "Diagnosis: Grade 3 Inflammatory Acne Vulgaris. Plan: Start Clindamycin gel morning, Adapalene 0.1% bedtime. CAUTION: Patient allergic to Benzoyl Peroxide.",
            "is_pinned": True
        }
        res = client.post(f"/api/patients/{patient_id}/notes/", req_body_6_3, format="json")
        log_call(6, "6.3 Clinical Doctor Notes & Pinned Alerts", "POST", f"/api/patients/{patient_id}/notes/", req_body_6_3, res, [201])

        # 6.4 Schedule Follow-up / Recall Task
        req_body_6_4 = {
            "follow_up_type": "clinical_review",
            "priority": "medium",
            "due_date": str((timezone.now() + timezone.timedelta(days=14)).date()),
            "title": "2-Week Acne Therapy Progress Review",
            "instructions": "Call patient to assess tolerance of topical Adapalene."
        }
        res = client.post(f"/api/patients/{patient_id}/follow-ups/", req_body_6_4, format="json")
        resp_6_4, _ = log_call(6, "6.4 Schedule Follow-up / Recall Task", "POST", f"/api/patients/{patient_id}/follow-ups/", req_body_6_4, res, [201])
        follow_up_id = resp_6_4.get("id") if isinstance(resp_6_4, dict) else None

        # 6.5 Complete Follow-up Task
        if follow_up_id:
            req_body_6_5 = {
                "outcome_notes": "Spoke with Pooja. Skin adapting well with no redness. Booked peel for Saturday."
            }
            res = client.post(f"/api/patients/follow-ups/{follow_up_id}/complete/", req_body_6_5, format="json")
            log_call(6, "6.5 Complete Follow-up Task", "POST", f"/api/patients/follow-ups/{follow_up_id}/complete/", req_body_6_5, res, [200])

    # =========================================================================
    # PHASE 7: WHATSAPP AUTOMATION & PATIENT REMINDERS
    # =========================================================================
    print("\n--- PHASE 7: WHATSAPP AUTOMATION & PATIENT REMINDERS ---")

    # 7.1 WhatsApp Gateway Configuration (PUT / PATCH)
    req_body_7_1 = {
        "phone_number_id": f"10098{unique_num}",
        "waba_id": f"99881{unique_num}",
        "access_token": "EAAQ3ZCZB_mock_token_12345",
        "display_phone_number": test_phone,
        "business_name": "Arogya Skin Clinic",
        "is_enabled": True,
        "auto_confirmation_enabled": True,
        "auto_reminders_enabled": True,
        "post_visit_review_enabled": True
    }
    res = client.put("/api/whatsapp/config/", req_body_7_1, format="json")
    log_call(7, "7.1 WhatsApp Gateway Configuration", "PUT", "/api/whatsapp/config/", req_body_7_1, res, [200, 201])

    # 7.2 Seed Default Clinical Templates
    res = client.post("/api/whatsapp/templates/seed-defaults/", {}, format="json")
    log_call(7, "7.2 Seed Default Clinical Templates", "POST", "/api/whatsapp/templates/seed-defaults/", {}, res, [200, 201])

    # 7.3 Instant Test Send WhatsApp Message
    req_body_7_3 = {
        "recipient_phone": patient_phone,
        "template_name": "booking_confirmation"
    }
    res = client.post("/api/whatsapp/test-send/", req_body_7_3, format="json")
    log_call(7, "7.3 Instant Test Send WhatsApp Message", "POST", "/api/whatsapp/test-send/", req_body_7_3, res, [200])

    # 7.4 Process Queued Automated Reminders
    res = client.post("/api/whatsapp/reminders/process-now/", {}, format="json")
    log_call(7, "7.4 Process Queued Automated Reminders", "POST", "/api/whatsapp/reminders/process-now/", {}, res, [200])

    # 7.5 Consent Opt-Out Verification Check (?phone=...)
    res = client.get(f"/api/whatsapp/opt-outs/check/?phone={patient_phone}")
    log_call(7, "7.5 Patient Consent Opt-Out Check", "GET", f"/api/whatsapp/opt-outs/check/?phone={patient_phone}", None, res, [200])

    # =========================================================================
    # PHASE 8: SUBSCRIPTIONS, INVOICING & BILLING
    # =========================================================================
    print("\n--- PHASE 8: SUBSCRIPTIONS, INVOICING & BILLING ---")

    plan = SubscriptionPlan.objects.filter(tier=SubscriptionPlan.TIER_GROWTH).first()
    if not plan:
        plan = SubscriptionPlan.objects.filter(is_active=True).exclude(tier=SubscriptionPlan.TIER_TRIAL).first()
    if not plan:
        plan = SubscriptionPlan.objects.create(
            name="Growth Polyclinic",
            slug=f"growth-polyclinic-{unique_num}",
            tier=SubscriptionPlan.TIER_GROWTH,
            monthly_price=Decimal("2999.00"),
            yearly_price=Decimal("29990.00"),
            currency="INR",
            max_doctors=5,
            max_staff=10,
            is_active=True
        )

    # 8.1 Subscription Plans Catalog
    res = client.get("/api/billing/plans/")
    log_call(8, "8.1 Subscription Plans Catalog", "GET", "/api/billing/plans/", None, res, [200])

    # 8.2 Current Usage Summary
    res = client.get("/api/billing/usage/")
    log_call(8, "8.2 Current Usage Summary", "GET", "/api/billing/usage/", None, res, [200])

    # 8.3 Initiate Checkout Session
    req_body_8_3 = {
        "plan_id": str(plan.id),
        "interval": "yearly"
    }
    res = client.post("/api/billing/checkout/", req_body_8_3, format="json")
    resp_8_3, _ = log_call(8, "8.3 Initiate Checkout Session", "POST", "/api/billing/checkout/", req_body_8_3, res, [200])
    invoice_id = resp_8_3.get("invoice_id") if isinstance(resp_8_3, dict) else None
    order_id = resp_8_3.get("order_id") if isinstance(resp_8_3, dict) else f"order_mock_{unique_num}"

    # 8.4 Verify Payment Signature & Activate Plan
    if invoice_id:
        req_body_8_4 = {
            "invoice_id": str(invoice_id),
            "razorpay_order_id": order_id,
            "razorpay_payment_id": f"pay_mock_{unique_num}",
            "razorpay_signature": f"mock_sig_{unique_num}"
        }
        res = client.post("/api/billing/verify-payment/", req_body_8_4, format="json")
        log_call(8, "8.4 Verify Payment & Activate Plan", "POST", "/api/billing/verify-payment/", req_body_8_4, res, [200])

        # 8.5 Printable GST Tax Invoice / Receipt
        res = client.get(f"/api/billing/invoices/{invoice_id}/receipt/")
        log_call(8, "8.5 Printable GST Tax Invoice HTML Receipt", "GET", f"/api/billing/invoices/{invoice_id}/receipt/", None, res, [200])

    # =========================================================================
    # PHASE 9: GROWTH ANALYTICS & EXECUTIVE REPORTS
    # =========================================================================
    print("\n--- PHASE 9: GROWTH ANALYTICS & EXECUTIVE REPORTS ---")

    # 9.1 Practice Analytics Dashboard
    res = client.get("/api/analytics/dashboard/?period=30d")
    log_call(9, "9.1 Practice Analytics Dashboard", "GET", "/api/analytics/dashboard/?period=30d", None, res, [200])

    # 9.2 Patient Acquisition Funnel
    res = client.get("/api/analytics/funnel/")
    log_call(9, "9.2 Patient Acquisition Funnel", "GET", "/api/analytics/funnel/", None, res, [200])

    # 9.3 Trigger Automated Monthly Growth Report
    now = timezone.now()
    req_body_9_3 = {"year": now.year, "month": now.month}
    res = client.post("/api/reports/monthly/generate/", req_body_9_3, format="json")
    resp_9_3, _ = log_call(9, "9.3 Generate Monthly Growth Report", "POST", "/api/reports/monthly/generate/", req_body_9_3, res, [200, 201])
    report_id = resp_9_3.get("id") if isinstance(resp_9_3, dict) else None

    # 9.4 Download Executive PDF Report
    if report_id:
        res = client.get(f"/api/reports/monthly/{report_id}/pdf/")
        log_call(9, "9.4 Download Executive PDF Growth Report", "GET", f"/api/reports/monthly/{report_id}/pdf/", None, res, [200])

    # =========================================================================
    # PHASE 10: SECURITY, PRIVACY & COMPLIANCE
    # =========================================================================
    print("\n--- PHASE 10: SECURITY, PRIVACY & COMPLIANCE ---")

    # 10.1 Active Role & Granular RBAC Permissions
    res = client.get("/api/security/roles/my-permissions/")
    log_call(10, "10.1 Active Role & Granular RBAC Permissions", "GET", "/api/security/roles/my-permissions/", None, res, [200])

    # 10.2 Security Audit Trail
    res = client.get("/api/security/audit-logs/")
    log_call(10, "10.2 Immutable Security Audit Trail", "GET", "/api/security/audit-logs/", None, res, [200])

    # 10.3 Patient Consent Management
    req_body_10_3 = {
        "patient_identifier": patient_phone,
        "patient_name": "Pooja Verma",
        "consent_type": "whatsapp_notifications",
        "consent_text": "Patient agreed to receive WhatsApp appointment reminders and lab reports."
    }
    res = client.post("/api/security/consents/", req_body_10_3, format="json")
    resp_10_3, _ = log_call(10, "10.3 Patient Consent Intake (DPDP/HIPAA)", "POST", "/api/security/consents/", req_body_10_3, res, [201])

    # 10.4 Withdraw Consent
    req_body_10_4 = {
        "patient_identifier": patient_phone,
        "consent_type": "whatsapp_notifications",
        "reason": "Patient requested stop on marketing messages"
    }
    res = client.post("/api/security/consents/withdraw/", req_body_10_4, format="json")
    log_call(10, "10.4 Withdraw Patient Consent", "POST", "/api/security/consents/withdraw/", req_body_10_4, res, [200])

    # 10.5 Encrypted Practice Data Backup
    req_body_10_5 = {
        "backup_name": f"Snapshot_{unique_num}",
        "backup_type": "manual"
    }
    res = client.post("/api/security/backups/", req_body_10_5, format="json")
    resp_10_5, _ = log_call(10, "10.5 Encrypted Practice Data Backup", "POST", "/api/security/backups/", req_body_10_5, res, [201])
    backup_id = resp_10_5.get("id") if isinstance(resp_10_5, dict) else None

    # 10.6 Verify Backup Integrity
    if backup_id:
        res = client.post(f"/api/security/backups/{backup_id}/verify/", {}, format="json")
        log_call(10, "10.6 Verify Cryptographic Backup Integrity", "POST", f"/api/security/backups/{backup_id}/verify/", {}, res, [200])

    # =========================================================================
    # SUMMARY & EXPORT
    # =========================================================================
    total_calls = len(test_log)
    passed_calls = sum(1 for e in test_log if e["passed"])
    failed_calls = total_calls - passed_calls

    print("\n" + "=" * 90)
    print(f"TEST EXECUTION COMPLETE: Total Endpoints Tested: {total_calls} | Passed: {passed_calls} | Failed: {failed_calls}")
    print("=" * 90)

    results_path = os.path.join(BASE_DIR, "scratch", "comprehensive_test_results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(test_log, f, indent=2, default=str)
    print(f"Results successfully saved to {results_path}")

    return test_log

if __name__ == "__main__":
    test_all_apis()

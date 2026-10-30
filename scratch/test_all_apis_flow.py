import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ClinicRise.settings')
django.setup()

import io
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()

def run_all_api_flow_tests():
    print("=" * 80)
    print("CLINICRISE COMPLETE END-TO-END FLOW-WISE API VERIFICATION")
    print("=" * 80)
    
    client = APIClient()
    results = []

    def record(stage_name, endpoint_name, method, url, status_code, expected_status, passed, notes=""):
        status_label = "PASS [OK]" if passed else "FAIL [X]"
        print(f"[{status_label}] {stage_name} -> {method} {url} (Got: {status_code}, Expected: {expected_status}) {notes}")
        results.append({
            "stage": stage_name,
            "endpoint": endpoint_name,
            "method": method,
            "url": url,
            "got": status_code,
            "expected": expected_status,
            "passed": passed
        })

    # -------------------------------------------------------------
    # STAGE 0: AUTHENTICATION & LOGIN
    # -------------------------------------------------------------
    phone = "+919988776655"
    res = client.post("/api/auth/register/", {
        "phone_number": phone,
        "email": "dr.e2e@clinicrise.com",
        "full_name": "Dr. End-to-End Test",
        "password": "Password123!"
    }, format="json")
    if res.status_code == status.HTTP_201_CREATED:
        record("Stage 0: Auth", "Register User", "POST", "/api/auth/register/", res.status_code, 201, True)
    elif res.status_code == status.HTTP_400_BAD_REQUEST and "already" in str(res.data).lower():
        record("Stage 0: Auth", "Register User (Already Exists)", "POST", "/api/auth/register/", res.status_code, 400, True)
    else:
        record("Stage 0: Auth", "Register User", "POST", "/api/auth/register/", res.status_code, 201, False)

    # Login
    res = client.post("/api/auth/login/", {
        "email": "dr.e2e@clinicrise.com",
        "password": "Password123!"
    }, format="json")
    record("Stage 0: Auth", "Login", "POST", "/api/auth/login/", res.status_code, 200, res.status_code == 200)
    tokens = res.data.get('tokens', {})
    access_token = tokens.get('access')

    # Authenticate client for subsequent requests
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

    # -------------------------------------------------------------
    # STAGE 1: PRACTICE SETUP & ONBOARDING
    # -------------------------------------------------------------
    # List practices
    res = client.get("/api/practices/")
    record("Stage 1: Practice", "List Practices", "GET", "/api/practices/", res.status_code, 200, res.status_code == 200)

    # Create new practice
    res = client.post("/api/practices/", {
        "name": "E2E Care Dental",
        "state": "Telangana",
        "city": "Hyderabad",
        "country": "India",
        "currency": "INR",
        "phone": "+919988776655",
        "email": "clinic@e2ecare.com",
        "tagline": "Modern Dental Excellence"
    }, format="json")
    practice_created = res.status_code == 201
    record("Stage 1: Practice", "Create Practice", "POST", "/api/practices/", res.status_code, 201, practice_created or res.status_code in [200, 201])
    
    if practice_created:
        practice_id = res.data.get('id')
    else:
        practice_res = client.get("/api/practices/")
        practice_id = practice_res.data[0]['id']

    # Set X-Practice-ID header
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        HTTP_X_PRACTICE_ID=str(practice_id)
    )

    # Get Practice Detail
    res = client.get(f"/api/practices/{practice_id}/")
    record("Stage 1: Practice", "Practice Detail", "GET", f"/api/practices/{practice_id}/", res.status_code, 200, res.status_code == 200)

    # Current Practice
    res = client.get("/api/practices/current/")
    record("Stage 1: Practice", "Current Practice Context", "GET", "/api/practices/current/", res.status_code, 200, res.status_code == 200)

    # Onboarding Progress
    res = client.get("/api/practices/onboarding/progress/")
    record("Stage 1: Practice", "Onboarding Progress", "GET", "/api/practices/onboarding/progress/", res.status_code, 200, res.status_code == 200)

    # -------------------------------------------------------------
    # STAGE 2: TEAM MEMBERS & ROLES
    # -------------------------------------------------------------
    res = client.get(f"/api/practices/{practice_id}/members/")
    record("Stage 2: Team Access", "List Members", "GET", f"/api/practices/{practice_id}/members/", res.status_code, 200, res.status_code == 200)

    # Role Matrix
    res = client.get("/api/practices/roles/")
    record("Stage 2: Team Access", "Role Matrix", "GET", "/api/practices/roles/", res.status_code, 200, res.status_code == 200)

    # -------------------------------------------------------------
    # STAGE 3: SUBSCRIPTION BILLING & PLANS
    # -------------------------------------------------------------
    res = client.get("/api/billing/plans/")
    record("Stage 3: Billing", "List Subscription Plans", "GET", "/api/billing/plans/", res.status_code, 200, res.status_code == 200)

    res = client.get("/api/billing/subscription/")
    record("Stage 3: Billing", "Current Subscription", "GET", "/api/billing/subscription/", res.status_code, 200, res.status_code == 200)

    # -------------------------------------------------------------
    # STAGE 4: PATIENTS CRM & TIMELINE
    # -------------------------------------------------------------
    import uuid
    random_suffix = uuid.uuid4().hex[:6]
    res = client.post("/api/patients/", {
        "first_name": "Ramesh",
        "last_name": "Kumar",
        "phone_number": f"+9198765{random_suffix[:5]}",
        "email": f"ramesh_{random_suffix}@example.com",
        "gender": "male",
        "city": "Hyderabad"
    }, format="json")
    patient_created = res.status_code == 201
    record("Stage 4: Patients CRM", "Create Patient", "POST", "/api/patients/", res.status_code, 201, patient_created)
    patient_id = res.data.get('id') if patient_created else None

    # Patient List
    res = client.get("/api/patients/")
    record("Stage 4: Patients CRM", "List Patients", "GET", "/api/patients/", res.status_code, 200, res.status_code == 200)

    # CRM Overview
    res = client.get("/api/patients/overview/")
    record("Stage 4: Patients CRM", "CRM Overview", "GET", "/api/patients/overview/", res.status_code, 200, res.status_code == 200)

    if patient_id:
        # Patient Detail
        res = client.get(f"/api/patients/{patient_id}/")
        record("Stage 4: Patients CRM", "Patient Detail", "GET", f"/api/patients/{patient_id}/", res.status_code, 200, res.status_code == 200)

        # Timeline
        res = client.get(f"/api/patients/{patient_id}/timeline/")
        record("Stage 4: Patients CRM", "Patient Timeline", "GET", f"/api/patients/{patient_id}/timeline/", res.status_code, 200, res.status_code == 200)

        # Add Note
        res = client.post(f"/api/patients/{patient_id}/notes/", {
            "category": "clinical",
            "note": "Patient reported mild sensitivity on lower right molar."
        }, format="json")
        record("Stage 4: Patients CRM", "Add Patient Note", "POST", f"/api/patients/{patient_id}/notes/", res.status_code, 201, res.status_code == 201)

        # Add Follow-up
        res = client.post(f"/api/patients/{patient_id}/follow-ups/", {
            "title": "Post-op checkup call",
            "due_date": str((timezone.now() + timezone.timedelta(days=2)).date()),
            "priority": "normal"
        }, format="json")
        record("Stage 4: Patients CRM", "Schedule Follow-up", "POST", f"/api/patients/{patient_id}/follow-ups/", res.status_code, 201, res.status_code == 201)

    # -------------------------------------------------------------
    # STAGE 5: LEADS & WHATSAPP AUTOMATION
    # -------------------------------------------------------------
    res = client.post("/api/leads/", {
        "patient_name": "Sunita Verma",
        "phone_number": f"+9198766{random_suffix[:5]}",
        "email": f"sunita_{random_suffix}@example.com",
        "source": "google_search",
        "service_requested": "Root Canal Treatment"
    }, format="json")
    lead_created = res.status_code == 201
    record("Stage 5: Leads & WhatsApp", "Create Lead", "POST", "/api/leads/", res.status_code, 201, lead_created)

    res = client.get("/api/leads/")
    record("Stage 5: Leads & WhatsApp", "List Leads", "GET", "/api/leads/", res.status_code, 200, res.status_code == 200)

    # WhatsApp Templates
    res = client.get("/api/whatsapp/templates/")
    record("Stage 5: Leads & WhatsApp", "List WhatsApp Templates", "GET", "/api/whatsapp/templates/", res.status_code, 200, res.status_code == 200)

    # WhatsApp Message Logs
    res = client.get("/api/whatsapp/logs/")
    record("Stage 5: Leads & WhatsApp", "List WhatsApp Message Logs", "GET", "/api/whatsapp/logs/", res.status_code, 200, res.status_code == 200)

    # WhatsApp Reminders Queue
    res = client.get("/api/whatsapp/reminders/")
    record("Stage 5: Leads & WhatsApp", "WhatsApp Reminders Queue", "GET", "/api/whatsapp/reminders/", res.status_code, 200, res.status_code == 200)

    # WhatsApp Opt-outs
    res = client.get("/api/whatsapp/opt-outs/")
    record("Stage 5: Leads & WhatsApp", "WhatsApp Opt-Out Registry", "GET", "/api/whatsapp/opt-outs/", res.status_code, 200, res.status_code == 200)

    # -------------------------------------------------------------
    # STAGE 6: GOOGLE BUSINESS PROFILE (GBP) INTEGRATIONS
    # -------------------------------------------------------------
    res = client.get("/api/gbp/checklist/")
    record("Stage 6: GBP", "GBP Launch Checklist", "GET", "/api/gbp/checklist/", res.status_code, 200, res.status_code == 200)

    res = client.get("/api/gbp/connection/")
    record("Stage 6: GBP", "GBP Connection Info", "GET", "/api/gbp/connection/", res.status_code, 200, res.status_code == 200)

    res = client.get("/api/gbp/reviews/")
    record("Stage 6: GBP", "List Google Reviews", "GET", "/api/gbp/reviews/", res.status_code, 200, res.status_code == 200)

    res = client.get("/api/gbp/posts/")
    record("Stage 6: GBP", "List GBP Posts", "GET", "/api/gbp/posts/", res.status_code, 200, res.status_code == 200)

    res = client.get("/api/gbp/rank-tracking/overview/")
    record("Stage 6: GBP", "Local Rank Tracking Overview", "GET", "/api/gbp/rank-tracking/overview/", res.status_code, 200, res.status_code == 200)

    res = client.get("/api/gbp/search-console/overview/")
    record("Stage 6: GBP", "Search Console Overview", "GET", "/api/gbp/search-console/overview/", res.status_code, 200, res.status_code == 200)

    # -------------------------------------------------------------
    # STAGE 7: MONTHLY GROWTH REPORTS & PDF GENERATION
    # -------------------------------------------------------------
    # Trigger Monthly Growth Report
    res = client.post("/api/reports/monthly/generate/", {
        "period_month": timezone.now().strftime("%Y-%m"),
        "force_refresh": True
    }, format="json")
    report_created = res.status_code in [200, 201]
    record("Stage 7: Reports", "Generate Monthly Growth Report", "POST", "/api/reports/monthly/generate/", res.status_code, "200/201", report_created)
    report_id = res.data.get('id') if report_created else None

    # List Reports
    res = client.get("/api/reports/monthly/")
    record("Stage 7: Reports", "List Reports", "GET", "/api/reports/monthly/", res.status_code, 200, res.status_code == 200)

    if report_id:
        # Report Detail
        res = client.get(f"/api/reports/monthly/{report_id}/")
        record("Stage 7: Reports", "Report Detail", "GET", f"/api/reports/monthly/{report_id}/", res.status_code, 200, res.status_code == 200)

        # Download ReportLab PDF
        res = client.get(f"/api/reports/monthly/{report_id}/pdf/")
        pdf_valid = res.status_code == 200 and res.get('Content-Type') == 'application/pdf'
        record("Stage 7: Reports", "Download Growth PDF", "GET", f"/api/reports/monthly/{report_id}/pdf/", res.status_code, 200, pdf_valid, f"PDF bytes: {len(res.content)}")

    # -------------------------------------------------------------
    # STAGE 8: ANALYTICS DASHBOARD
    # -------------------------------------------------------------
    res = client.get("/api/analytics/dashboard/")
    record("Stage 8: Analytics", "Analytics Dashboard", "GET", "/api/analytics/dashboard/", res.status_code, 200, res.status_code == 200)

    res = client.get("/api/analytics/traffic-sources/")
    record("Stage 8: Analytics", "Traffic Sources", "GET", "/api/analytics/traffic-sources/", res.status_code, 200, res.status_code == 200)

    res = client.get("/api/analytics/funnel/")
    record("Stage 8: Analytics", "Conversion Funnel", "GET", "/api/analytics/funnel/", res.status_code, 200, res.status_code == 200)

    # -------------------------------------------------------------
    # SUMMARY
    # -------------------------------------------------------------
    total = len(results)
    passed = sum(1 for r in results if r['passed'])
    failed = total - passed
    print("\n" + "=" * 80)
    print(f"VERIFICATION SUMMARY: Total Tested: {total} | Passed: {passed} | Failed: {failed}")
    print("=" * 80)
    if failed == 0:
        print(">>> ALL FLOW-WISE APIS ARE OPERATIONAL AND PASSING 100%! <<<")
    else:
        print(">>> SOME APIS ENCOUNTERED FAILURES! <<<")

if __name__ == '__main__':
    run_all_api_flow_tests()

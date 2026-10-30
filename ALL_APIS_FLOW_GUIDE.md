# ClinicRise - End-to-End API Flow Guide (Complete System Specification)

Welcome to the comprehensive, flow-wise API reference for **ClinicRise** — the healthcare growth, clinic website generation, patient CRM, and appointment automation platform.

This document traces the complete lifecycle of a medical clinic: from a doctor's initial sign-up and onboarding wizard, through automated website generation, lead and appointment intake, WhatsApp reminders, clinical charting, billing, Google Business Profile optimization, to executive PDF growth reporting and compliance security.

---

## 🗺️ Master Architecture & Journey Map

```mermaid
flowchart TD
    %% Phase 1
    subgraph P1["1. Doctor Onboarding & Setup"]
        A1[1.1 OTP / Google Auth] --> A2[1.2 5-Step Doctor Wizard]
        A2 --> A3[1.3 Practice Tenant Setup]
        A3 --> A4[1.4 Staff Invitations & RBAC]
    end

    %% Phase 2
    subgraph P2["2. Website Engine & Content Approval"]
        A4 --> B1[2.1 1-Click Website Generator]
        B1 --> B2[2.2 Live Preview & Publish]
        B2 --> B3[2.3 Custom Domain & DNS]
        B3 --> B4[2.4 Unified Approval Queue]
        B4 --> B5[2.5 Page & Blog Review Workflow]
    end

    %% Phase 3 & 4
    subgraph P3["3. Digital Growth & Traffic"]
        C1[3.1 GBP 10-Step Setup] --> C2[3.2 Reviews & AI Reply]
        C2 --> C3[3.3 Local 3-Pack Rank Tracking]
    end

    subgraph P4["4. Lead Capture & Pipeline"]
        D1[4.1 Public Visit Track] --> D2[4.2 Call / WhatsApp Click Event]
        D2 --> D3[4.3 Public Inquiry Form]
        D3 --> D4[4.4 CRM Lead Inbox]
        D4 --> D5[4.5 Lead Pipeline Progression]
    end

    %% Phase 5 & 6
    subgraph P5["5. Appointments & Capacity Engine"]
        E1[5.1 Realtime Availability Check] --> E2[5.2 Booking Request Intake]
        E2 --> E3[5.3 Capacity Verification]
        E3 --> E4[5.4 Clinic Confirmation]
        E4 --> E5[5.5 Check-in & Visit Lifecycle]
    end

    subgraph P6["6. Patient CRM & Clinical Charting"]
        E5 --> F1[6.1 Convert Lead to Patient]
        F1 --> F2[6.2 Clinical Chart & Timeline]
        F2 --> F3[6.3 Doctor Notes & Pinned Alerts]
        F3 --> F4[6.4 Nurse Vitals Recording]
        F4 --> F5[6.5 Follow-ups & Recalls Queue]
    end

    %% Phase 7, 8, 9, 10
    subgraph P7["7. WhatsApp Automation"]
        G1[7.1 Gateway Config] --> G2[7.2 Pre-approved Templates]
        G2 --> G3[7.3 Scheduled 24h/2h Reminders]
        G3 --> G4[7.4 Realtime Delivery Tracking]
    end

    subgraph P8["8. Billing & Subscriptions"]
        H1[8.1 Plans & Pricing] --> H2[8.2 Checkout Session]
        H2 --> H3[8.3 Payment Verification & Invoices]
    end

    subgraph P9["9. Growth Analytics & Reports"]
        I1[9.1 Practice Analytics Dashboard] --> I2[9.2 Monthly Executive PDF Report]
    end

    subgraph P10["10. Security & Compliance"]
        J1[10.1 RBAC Matrix] --> J2[10.2 Audit Logs]
        J2 --> J3[10.3 DPDP Consents & Backups]
    end

    P1 --> P2
    P2 --> P3
    P3 --> P4
    P4 --> P5
    P5 --> P6
    P5 --> P7
    P1 --> P8
    P4 --> P9
    P1 --> P10
```

---

## Headers & Global Conventions

- **Base URL**: `http://localhost:8000` (or `https://api.clinicrise.com`)
- **Authentication**: JWT Bearer token:
  ```http
  Authorization: Bearer <access_token>
  ```
- **Multi-Tenant Context**: Header indicating the active clinic practice:
  ```http
  X-Practice-ID: 7a829f03-6c7b-4d5e-9f0a-112233445566
  ```

---

# Phase 1: Authentication & Doctor Onboarding (Starting Point)

The clinic's journey begins with the doctor signing up via Mobile OTP or Google Sign-In, and going through the guided 5-step Doctor Onboarding wizard.

---

### 1.1 Mobile OTP - Request Code
Sends a 6-digit cryptographic verification code to the doctor's phone number.

- **Method & URL**: `POST /api/auth/otp/send/`
- **Auth**: Public (`AllowAny`)
- **Request Body**:
```json
{
  "phone_number": "+919876543210",
  "purpose": "login"
}
```
- **Response (200 OK)**:
```json
{
  "success": true,
  "message": "OTP sent to +919876543210 successfully.",
  "purpose": "login",
  "expires_in_minutes": 5,
  "dev_otp": "729481"
}
```

---

### 1.2 Mobile OTP - Verify & Issue JWT Session
Verifies the OTP. If the user does not exist, an account is automatically created. Returns JWT access and refresh tokens.

- **Method & URL**: `POST /api/auth/otp/verify/`
- **Auth**: Public (`AllowAny`)
- **Request Body**:
```json
{
  "phone_number": "+919876543210",
  "otp_code": "729481",
  "purpose": "login"
}
```
- **Response (200 OK)**:
```json
{
  "message": "Authentication successful.",
  "is_new_user": true,
  "tokens": {
    "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiZTRiNmMzMTAtOGI0My00ZjkwLWE0YTktYTk5ZjE4MmM0NzhhIn0.exampleAccessToken",
    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiZTRiNmMzMTAtOGI0My00ZjkwLWE0YTktYTk5ZjE4MmM0NzhhIn0.exampleRefreshToken"
  },
  "user": {
    "id": "e4b6c310-8b43-4f90-a4a9-a99f182c478a",
    "email": "doctor@arogyaclinic.com",
    "phone_number": "+919876543210",
    "first_name": "Aditi",
    "last_name": "Sharma",
    "full_name": "Dr. Aditi Sharma",
    "avatar_url": null,
    "is_email_verified": false,
    "is_phone_verified": true,
    "auth_provider": "phone",
    "date_joined": "2026-10-23T09:00:00Z"
  }
}
```

---

### 1.3 Alternative Auth: Google Sign-In
- **Method & URL**: `POST /api/auth/google/`
- **Auth**: Public (`AllowAny`)
- **Request Body**:
```json
{
  "id_token": "mock-google:doctor@arogyaclinic.com"
}
```
- **Response (200 OK)**:
```json
{
  "message": "Google authentication successful.",
  "is_new_user": false,
  "tokens": {
    "access": "eyJhbGciOi...",
    "refresh": "eyJhbGciOi..."
  },
  "user": {
    "id": "e4b6c310-8b43-4f90-a4a9-a99f182c478a",
    "email": "doctor@arogyaclinic.com",
    "full_name": "Dr. Aditi Sharma"
  }
}
```

---

### 1.4 Doctor Onboarding Wizard - Track Progress
Enables seamless resuming of the 5-step wizard.

- **Method & URL**: `GET /api/practices/onboarding/progress/`
- **Auth**: `Bearer <access_token>`
- **Response (200 OK)**:
```json
{
  "progress_percentage": 0,
  "current_step": "doctor_profile",
  "completed_steps": [],
  "is_completed": false,
  "steps": [
    {"step_number": 1, "key": "doctor_profile", "title": "Doctor Profile & Registration Number", "is_completed": false},
    {"step_number": 2, "key": "clinic_details", "title": "Clinic Details & Practice Information", "is_completed": false},
    {"step_number": 3, "key": "services", "title": "Clinical Services & Consultation Fees", "is_completed": false},
    {"step_number": 4, "key": "timings", "title": "Clinic Timings & Working Hours", "is_completed": false},
    {"step_number": 5, "key": "images", "title": "Clinic Photos & Verification Documents", "is_completed": false}
  ],
  "draft_data": {}
}
```

---

### 1.5 Step 1: Doctor Profile & Medical Council License
- **Method & URL**: `POST /api/practices/onboarding/step/doctor-profile/`
- **Auth**: `Bearer <access_token>`
- **Request Body**:
```json
{
  "first_name": "Aditi",
  "last_name": "Sharma",
  "title": "Dr.",
  "gender": "female",
  "medical_license_number": "MCI-2015-88392",
  "registration_council": "Maharashtra Medical Council",
  "registration_year": 2015,
  "specialization": "Dermatology & Cosmetology",
  "qualifications": "MBBS, MD (Dermatology)",
  "experience_years": 11,
  "languages_spoken": "English, Hindi, Marathi",
  "bio": "Dr. Aditi Sharma is a board-certified Dermatologist specializing in clinical dermatology, acne therapies, and laser skin treatments.",
  "default_consultation_fee": 800.00
}
```
- **Response (200 OK)**:
```json
{
  "success": true,
  "message": "Doctor profile & registration number saved successfully.",
  "progress_percentage": 20,
  "current_step": "clinic_details"
}
```

---

### 1.6 Step 2: Clinic & Practice Tenant Details
Creates the tenant `Practice` record and binds the doctor as the Practice Owner.

- **Method & URL**: `POST /api/practices/onboarding/step/clinic-details/`
- **Auth**: `Bearer <access_token>`
- **Request Body**:
```json
{
  "name": "Arogya Skin & Laser Clinic",
  "clinic_type": "solo",
  "tagline": "Advanced Dermatological Care & Aesthetic Wellness",
  "about": "Arogya Clinic provides evidence-based clinical dermatology and cutting-edge aesthetic care in Mumbai.",
  "phone_number": "+919876543210",
  "email": "contact@arogyaclinic.com",
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
```
- **Response (200 OK)**:
```json
{
  "success": true,
  "message": "Clinic details saved successfully.",
  "practice": {
    "id": "7a829f03-6c7b-4d5e-9f0a-112233445566",
    "name": "Arogya Skin & Laser Clinic",
    "slug": "arogya-skin-laser-clinic",
    "city": "Mumbai",
    "is_active": true
  },
  "progress_percentage": 40,
  "current_step": "services"
}
```

---

### 1.7 Step 3: Clinical Services & Consultation Fees
- **Method & URL**: `POST /api/practices/onboarding/step/services/`
- **Auth**: `Bearer <access_token>`
- **Request Body**:
```json
{
  "services": [
    {
      "name": "General Dermatology Consultation",
      "category": "consultation",
      "description": "Comprehensive evaluation of skin conditions including eczema, psoriasis, and dermatitis.",
      "duration_minutes": 20,
      "price": 800.00,
      "is_teleconsultation": true
    },
    {
      "name": "Acne & Scar Laser Treatment",
      "category": "procedure",
      "description": "Fractional CO2 laser therapy for deep acne scar remodeling.",
      "duration_minutes": 45,
      "price": 3500.00,
      "is_teleconsultation": false
    },
    {
      "name": "Chemical Peel (Glycolic/Salicylic)",
      "category": "procedure",
      "description": "Medical-grade peel for hyperpigmentation and skin texture refinement.",
      "duration_minutes": 30,
      "price": 2200.00,
      "is_teleconsultation": false
    }
  ]
}
```
- **Response (200 OK)**:
```json
{
  "success": true,
  "message": "Saved 3 services successfully.",
  "progress_percentage": 60,
  "current_step": "timings"
}
```

---

### 1.8 Step 4: Doctor OPD Timings & Schedules
- **Method & URL**: `POST /api/practices/onboarding/step/timings/`
- **Auth**: `Bearer <access_token>`
- **Request Body**:
```json
{
  "timings": [
    {"day_of_week": 0, "session_name": "Morning OPD", "start_time": "10:00:00", "end_time": "13:30:00", "slot_duration_minutes": 20},
    {"day_of_week": 0, "session_name": "Evening Clinic", "start_time": "17:00:00", "end_time": "20:30:00", "slot_duration_minutes": 20},
    {"day_of_week": 1, "session_name": "Morning OPD", "start_time": "10:00:00", "end_time": "13:30:00", "slot_duration_minutes": 20},
    {"day_of_week": 1, "session_name": "Evening Clinic", "start_time": "17:00:00", "end_time": "20:30:00", "slot_duration_minutes": 20},
    {"day_of_week": 2, "session_name": "Morning OPD", "start_time": "10:00:00", "end_time": "13:30:00", "slot_duration_minutes": 20},
    {"day_of_week": 3, "session_name": "Morning OPD", "start_time": "10:00:00", "end_time": "13:30:00", "slot_duration_minutes": 20},
    {"day_of_week": 4, "session_name": "Morning OPD", "start_time": "10:00:00", "end_time": "13:30:00", "slot_duration_minutes": 20},
    {"day_of_week": 5, "session_name": "Weekend Special OPD", "start_time": "10:00:00", "end_time": "15:00:00", "slot_duration_minutes": 20}
  ]
}
```
*(Days: 0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday, 5=Saturday, 6=Sunday)*
- **Response (200 OK)**:
```json
{
  "success": true,
  "message": "Saved 8 schedule timing slots successfully.",
  "progress_percentage": 80,
  "current_step": "images"
}
```

---

### 1.9 Step 5: Clinic Photos & Doctor Avatar
- **Method & URL**: `POST /api/practices/onboarding/step/images/`
- **Auth**: `Bearer <access_token>`
- **Request Body**:
```json
{
  "doctor_avatar_url": "https://clinicrise-media.s3.amazonaws.com/doctors/dr-aditi.jpg",
  "registration_certificate_url": "https://clinicrise-media.s3.amazonaws.com/certs/mci-cert.pdf",
  "images": [
    {
      "image_url": "https://clinicrise-media.s3.amazonaws.com/clinic/reception.jpg",
      "image_type": "reception",
      "caption": "Executive Patient Waiting Lounge & Reception",
      "is_primary": true,
      "order": 1
    },
    {
      "image_url": "https://clinicrise-media.s3.amazonaws.com/clinic/laser-room.jpg",
      "image_type": "procedure_room",
      "caption": "Sterile Aesthetic Laser Procedure Suite",
      "is_primary": false,
      "order": 2
    }
  ]
}
```
- **Response (200 OK)**:
```json
{
  "success": true,
  "message": "Images and verification documents saved successfully.",
  "progress_percentage": 100,
  "current_step": "completed"
}
```

---

### 1.10 Finalize Onboarding
Validates all mandatory healthcare requirements and fully activates the practice.

- **Method & URL**: `POST /api/practices/onboarding/complete/`
- **Auth**: `Bearer <access_token>`
- **Response (200 OK)**:
```json
{
  "success": true,
  "message": "Doctor onboarding completed successfully! Your clinic practice is now fully activated.",
  "practice": {
    "id": "7a829f03-6c7b-4d5e-9f0a-112233445566",
    "name": "Arogya Skin & Laser Clinic",
    "slug": "arogya-skin-laser-clinic",
    "is_active": true
  },
  "progress_percentage": 100,
  "next_steps": [
    "Generate clinic website via POST /api/websites/generate/",
    "Setup Google Business Profile via GET /api/gbp/checklist/",
    "Configure WhatsApp gateway via POST /api/whatsapp/config/"
  ]
}
```

---

### 1.11 Practice Team & Staff Invitations (RBAC)
The doctor can invite staff members (Receptionist, Nurse, Associate Doctor, Clinic Manager).

- **Method & URL**: `POST /api/practices/7a829f03-6c7b-4d5e-9f0a-112233445566/invite/`
- **Auth**: `Bearer <access_token>` (Owner / Admin only)
- **Request Body**:
```json
{
  "email": "reception@arogyaclinic.com",
  "role": "staff",
  "phone_number": "+919811122233"
}
```
- **Response (201 Created)**:
```json
{
  "success": true,
  "message": "Invitation sent successfully to reception@arogyaclinic.com.",
  "invitation": {
    "id": "993c1f0b-e4a1-4d9a-8a1e-556677889900",
    "email": "reception@arogyaclinic.com",
    "role": "staff",
    "token": "inv_sec_8a39f1c7d6e5",
    "expires_at": "2026-10-30T09:00:00Z"
  }
}
```

---

### 1.12 Accept Staff Invitation
- **Method & URL**: `POST /api/practices/invitations/accept/`
- **Auth**: Public or Authenticated
- **Request Body**:
```json
{
  "token": "inv_sec_8a39f1c7d6e5"
}
```
- **Response (200 OK)**:
```json
{
  "success": true,
  "message": "Invitation accepted successfully! You are now a staff member at Arogya Skin & Laser Clinic."
}
```

---

# Phase 2: Automated Website Engine & Content Approvals

With the clinic onboarded, ClinicRise generates a high-converting, SEO-optimized clinic website in seconds, complete with doctor profile, service pages, booking CTAs, and a clinical approval queue.

---

### 2.1 1-Click Clinic Website Auto-Generation
Creates pages (Home, About Doctor, Services, Gallery, Contact, Book Consultation) and sets up the clinic subdomain.

- **Method & URL**: `POST /api/websites/generate/`
- **Auth**: `Bearer <access_token>`
- **Request Body**:
```json
{
  "practice_id": "7a829f03-6c7b-4d5e-9f0a-112233445566",
  "subdomain": "arogyaskin",
  "template_style": "modern_minimal",
  "auto_publish": true
}
```
- **Response (201 Created)**:
```json
{
  "success": true,
  "message": "Website 'Arogya Skin & Laser Clinic' generated successfully!",
  "public_url": "https://arogyaskin.clinicrise.com",
  "website": {
    "id": "3b29c481-91a0-4f5d-b3ef-8899aabbccdd",
    "title": "Arogya Skin & Laser Clinic",
    "subdomain": "arogyaskin",
    "primary_color": "#0ea5e9",
    "secondary_color": "#0369a1",
    "is_published": true,
    "pages_count": 6
  }
}
```

---

### 2.2 Live Website Public Rendering
Public endpoint serving the structured JSON for the frontend Jamstack/Next.js site.

- **Method & URL**: `GET /api/websites/public/arogyaskin/`
- **Auth**: Public (`AllowAny`)
- **Response (200 OK)**:
```json
{
  "website": {
    "title": "Arogya Skin & Laser Clinic",
    "tagline": "Advanced Dermatological Care & Aesthetic Wellness",
    "doctor": {
      "name": "Dr. Aditi Sharma",
      "qualifications": "MBBS, MD (Dermatology)",
      "experience_years": 11,
      "license": "MCI-2015-88392"
    },
    "services": [
      {"name": "General Dermatology Consultation", "price": 800.0, "duration": 20},
      {"name": "Acne & Scar Laser Treatment", "price": 3500.0, "duration": 45}
    ],
    "phone_number": "+919876543210",
    "address": "Shop 4, Sunrise Heights, Linking Road, Bandra West, Mumbai",
    "whatsapp_click_url": "https://wa.me/919876543210?text=Hi%20Arogya%20Clinic,%20I%20would%20like%20to%20book%20an%20appointment"
  }
}
```

---

### 2.3 Custom Domain Connection & DNS Verification
Maps the clinic's custom apex/subdomain (`drsharmaclinic.com`).

- **Add Domain**: `POST /api/websites/3b29c481-91a0-4f5d-b3ef-8899aabbccdd/domains/`
- **Auth**: `Bearer <access_token>`
- **Request Body**:
```json
{
  "domain": "drsharmaclinic.com"
}
```
- **Response (201 Created)**:
```json
{
  "id": "fa291b8a-1290-449e-a89b-778899001122",
  "domain": "drsharmaclinic.com",
  "verification_status": "pending",
  "dns_records_required": [
    {"type": "CNAME", "name": "www", "target": "cname.clinicrise.com"},
    {"type": "A", "name": "@", "target": "76.76.21.21"}
  ]
}
```

- **Trigger DNS Verification**: `POST /api/websites/3b29c481-91a0-4f5d-b3ef-8899aabbccdd/domains/fa291b8a-1290-449e-a89b-778899001122/verify/`
- **Response (200 OK)**:
```json
{
  "domain": "drsharmaclinic.com",
  "verification_status": "verified",
  "ssl_status": "active",
  "is_primary": true
}
```

---

### 2.4 Unified Content Approval Queue for Medical Accuracy
Healthcare regulations require clinical review before publishing copy modifications or blog articles.

- **Method & URL**: `GET /api/websites/3b29c481-91a0-4f5d-b3ef-8899aabbccdd/approvals/`
- **Auth**: `Bearer <access_token>` (Doctor / Admin)
- **Response (200 OK)**:
```json
{
  "pending_count": 2,
  "pages_pending_approval": [
    {
      "id": "11223344-5566-7788-9900-aabbccddeeff",
      "title": "Laser Hair Removal Treatments",
      "slug": "laser-hair-removal",
      "submitted_by": "Staff Copywriter",
      "submitted_at": "2026-10-23T08:30:00Z"
    }
  ],
  "blogs_pending_approval": [
    {
      "id": "99887766-5544-3322-1100-ffeeddccbbaa",
      "title": "5 Myths About Acne Scars Debunked",
      "slug": "5-myths-about-acne-scars",
      "submitted_by": "Marketing Team",
      "submitted_at": "2026-10-23T08:45:00Z"
    }
  ]
}
```

---

### 2.5 Doctor Review & Approve Page
The doctor reviews the proposed medical claims and approves or requests edits.

- **Method & URL**: `POST /api/websites/3b29c481-91a0-4f5d-b3ef-8899aabbccdd/pages/11223344-5566-7788-9900-aabbccddeeff/review/`
- **Auth**: `Bearer <access_token>`
- **Request Body**:
```json
{
  "action": "approve",
  "comments": "Medically verified. Approved for public publishing."
}
```
- **Response (200 OK)**:
```json
{
  "success": true,
  "message": "Page approved successfully.",
  "review_status": "approved",
  "publish_ready": true
}
```

---

# Phase 3: Digital Presence, Google Business Profile & SEO

Patients searching on Google ("Dermatologist in Bandra", "Skin clinic near me") discover the clinic through Google Business Profile (GBP) and the Local 3-Pack.

---

### 3.1 10-Step Google Business Profile (GBP) Checklist
- **Method & URL**: `GET /api/gbp/checklist/`
- **Auth**: `Bearer <access_token>`, `X-Practice-ID`
- **Response (200 OK)**:
```json
{
  "completion_percentage": 70,
  "completed_count": 7,
  "total_items": 10,
  "items": [
    {"key": "claim_profile", "title": "Claim & Verify Google Business Profile", "is_completed": true},
    {"key": "nap_consistency", "title": "Verify Exact Name, Address & Phone (NAP)", "is_completed": true},
    {"key": "categories_setup", "title": "Select Primary Category: Skin Care Clinic", "is_completed": true},
    {"key": "working_hours", "title": "Configure OPD Working Hours", "is_completed": true},
    {"key": "clinic_photos", "title": "Upload High-Resolution Clinic Photos", "is_completed": true},
    {"key": "booking_link", "title": "Set Appointment URL to Public Booking Portal", "is_completed": true},
    {"key": "services_catalog", "title": "Add Clinical Services & Pricing", "is_completed": true},
    {"key": "review_shortcut", "title": "Generate & Share Direct Patient Review Link", "is_completed": false},
    {"key": "weekly_posts", "title": "Schedule First Health & Skin Tip Post", "is_completed": false},
    {"key": "qna_seeding", "title": "Seed Top 5 Patient FAQs", "is_completed": false}
  ]
}
```

---

### 3.2 Google Patient Reviews - List & AI Empathetic Reply
- **List Reviews**: `GET /api/gbp/reviews/`
- **Auth**: `Bearer <access_token>`
- **Response (200 OK)**:
```json
{
  "count": 1,
  "results": [
    {
      "id": "e29c8810-77a2-4a0b-bc11-998877665544",
      "reviewer_name": "Rohan Deshmukh",
      "star_rating": 5,
      "review_text": "Dr. Aditi Sharma is wonderful! My acne cleared up completely within 6 weeks of laser and topical regimen. Very polite staff.",
      "has_replied": false,
      "review_date": "2026-10-22T14:30:00Z"
    }
  ]
}
```

- **Generate AI Empathetic Clinical Reply**: `POST /api/gbp/reviews/e29c8810-77a2-4a0b-bc11-998877665544/generate-reply/`
- **Response (200 OK)**:
```json
{
  "suggested_reply": "Thank you so much Rohan for your kind feedback! Dr. Aditi Sharma and the Arogya Clinic team are thrilled to see your progress. Remember to apply your daily sunscreen!"
}
```

- **Post Reply to Google**: `POST /api/gbp/reviews/e29c8810-77a2-4a0b-bc11-998877665544/reply/`
- **Request Body**:
```json
{
  "reply_text": "Thank you so much Rohan for your kind feedback! Dr. Aditi Sharma and the Arogya Clinic team are thrilled to see your progress. Remember to apply your daily sunscreen!"
}
```
- **Response (200 OK)**:
```json
{
  "success": true,
  "message": "Reply published to Google Business Profile successfully."
}
```

---

### 3.3 Local SEO 3-Pack Rank Tracking Check
Runs an automated ranking audit for high-intent medical search queries in the clinic's local geo-radius.

- **Method & URL**: `POST /api/gbp/rank-tracking/check/`
- **Auth**: `Bearer <access_token>`
- **Response (200 OK)**:
```json
{
  "success": true,
  "keywords_audited": 3,
  "results": [
    {"keyword": "dermatologist in bandra", "current_rank": 2, "in_3_pack": true, "previous_rank": 4},
    {"keyword": "acne clinic mumbai", "current_rank": 3, "in_3_pack": true, "previous_rank": 5},
    {"keyword": "skin specialist near me", "current_rank": 1, "in_3_pack": true, "previous_rank": 1}
  ]
}
```

---

# Phase 4: Patient Lead Ingestion & Conversion Pipeline

When a patient visits the website or clinic profile, their engagement is tracked and converted into a CRM lead.

---

### 4.1 Public Website Visit Tracking
- **Method & URL**: `POST /api/analytics/public/arogya-skin-laser-clinic/visit/`
- **Auth**: Public (`AllowAny`)
- **Request Body**:
```json
{
  "page_url": "https://arogyaskin.clinicrise.com/services/acne-treatment",
  "referrer": "https://www.google.com/",
  "utm_source": "google",
  "utm_medium": "cpc",
  "utm_campaign": "skin_acne_promo",
  "device_type": "mobile",
  "visitor_id": "v_f9a81c0022"
}
```
- **Response (201 Created)**:
```json
{
  "success": true,
  "visit_id": "90aa8811-2233-4455-6677-8899aabbccdd"
}
```

---

### 4.2 Track Public Call / WhatsApp Button Click
Captures high-intent clicks before an inquiry is even submitted.

- **Method & URL**: `POST /api/leads/public/arogya-skin-laser-clinic/click-event/`
- **Auth**: Public (`AllowAny`)
- **Request Body**:
```json
{
  "event_type": "whatsapp_click",
  "page_url": "https://arogyaskin.clinicrise.com/",
  "device_type": "mobile",
  "visitor_id": "v_f9a81c0022"
}
```
- **Response (201 Created)**:
```json
{
  "success": true,
  "message": "Click event recorded."
}
```

---

### 4.3 Public Patient Inquiry Form Submission (Lead Capture)
The patient fills out an inquiry or consultation request form.

- **Method & URL**: `POST /api/leads/public/arogya-skin-laser-clinic/inquire/`
- **Auth**: Public (`AllowAny`)
- **Request Body**:
```json
{
  "patient_name": "Pooja Verma",
  "phone_number": "+919822334455",
  "email": "pooja.verma@example.com",
  "service_requested": "Acne & Scar Laser Treatment",
  "preferred_date": "2026-10-25",
  "preferred_time_slot": "Evening (5 PM - 8 PM)",
  "message": "Suffering from hormonal acne breakouts for 6 months. Would like consultation with Dr. Aditi.",
  "consent_given": true,
  "whatsapp_opt_in": true,
  "utm_source": "google",
  "utm_campaign": "skin_acne_promo"
}
```
- **Response (201 Created)**:
```json
{
  "success": true,
  "message": "Thank you Pooja! Your inquiry has been received. Arogya Clinic will reach out shortly.",
  "lead_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d"
}
```

---

### 4.4 Clinic Staff CRM Inbox
Receptionists and doctors review incoming inquiries in real-time.

- **Method & URL**: `GET /api/leads/inbox/?status=new`
- **Auth**: `Bearer <access_token>`, `X-Practice-ID`
- **Response (200 OK)**:
```json
{
  "count": 1,
  "results": [
    {
      "id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
      "lead_number": "LEAD-2026-0042",
      "patient_name": "Pooja Verma",
      "phone_number": "+919822334455",
      "service_requested": "Acne & Scar Laser Treatment",
      "status": "new",
      "priority": "high",
      "whatsapp_opt_in": true,
      "created_at": "2026-10-23T09:15:00Z"
    }
  ]
}
```

---

### 4.5 Lead Pipeline Status Update & Action Logging
The frontdesk calls the patient, qualifies them, and updates the status to `qualified`.

- **Method & URL**: `PATCH /api/leads/a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d/status/`
- **Auth**: `Bearer <access_token>`
- **Request Body**:
```json
{
  "status": "qualified",
  "note": "Spoke with Pooja. Confirmed appointment preference for Saturday 5:30 PM with Dr. Aditi."
}
```
- **Response (200 OK)**:
```json
{
  "success": true,
  "message": "Lead status updated to 'qualified'.",
  "lead": {
    "id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
    "status": "qualified",
    "status_display": "Qualified Lead"
  }
}
```

---

# Phase 5: Booking Requests & Appointment Lifecycle

ClinicRise supports dual scheduling modes:
1. **Exact Time-Slot**: Precision bookings (e.g., 10:20 AM - 10:40 AM).
2. **Session / Token Queue**: Walk-in & OPD token system (e.g., Token #14 in Evening OPD).

---

### 5.1 Realtime Doctor Availability Check
Patients or receptionists verify availability for a doctor on a specific date.

- **Method & URL**: `GET /api/bookings/public/arogya-skin-laser-clinic/availability/?date=2026-10-25`
- **Auth**: Public (`AllowAny`)
- **Response (200 OK)**:
```json
{
  "practice_slug": "arogya-skin-laser-clinic",
  "date": "2026-10-25",
  "sessions": [
    {
      "session_name": "Evening Clinic",
      "start_time": "17:00:00",
      "end_time": "20:30:00",
      "booking_mode": "slot",
      "available_slots": [
        "17:00:00", "17:20:00", "17:40:00", "18:00:00", "18:20:00"
      ],
      "is_full": false
    }
  ]
}
```

---

### 5.2 Public Booking Request Submission
- **Method & URL**: `POST /api/bookings/public/arogya-skin-laser-clinic/request/`
- **Auth**: Public (`AllowAny`)
- **Request Body**:
```json
{
  "patient_name": "Pooja Verma",
  "phone_number": "+919822334455",
  "email": "pooja.verma@example.com",
  "gender": "female",
  "age": 28,
  "consultation_mode": "in_person",
  "preferred_date": "2026-10-25",
  "preferred_time_window": "evening",
  "booking_mode": "slot",
  "session_name": "Evening Clinic",
  "start_time": "17:20:00",
  "chief_complaint": "Severe facial acne breakouts and post-inflammatory pigmentation.",
  "consent_given": true
}
```
- **Response (201 Created)**:
```json
{
  "success": true,
  "message": "Appointment request submitted successfully. The clinic will confirm shortly.",
  "booking_reference": "CR-2026-88192",
  "status": "requested",
  "tracking_url": "/api/bookings/public/arogya-skin-laser-clinic/track/CR-2026-88192/"
}
```

---

### 5.3 Public Booking Tracking by Reference
- **Method & URL**: `GET /api/bookings/public/arogya-skin-laser-clinic/track/CR-2026-88192/`
- **Auth**: Public (`AllowAny`)
- **Response (200 OK)**:
```json
{
  "booking_reference": "CR-2026-88192",
  "patient_name": "Pooja Verma",
  "doctor_name": "Dr. Aditi Sharma",
  "preferred_date": "2026-10-25",
  "status": "requested",
  "status_display": "Pending Clinic Confirmation"
}
```

---

### 5.4 Clinic Confirmation Workflow (Confirm Appointment)
The clinic confirms the appointment, locking the slot or generating Token #04, which automatically triggers a WhatsApp confirmation.

- **Method & URL**: `POST /api/bookings/39aa1122-3344-5566-7788-99aabbccddee/confirm/`
- **Auth**: `Bearer <access_token>`, `X-Practice-ID`
- **Request Body**:
```json
{
  "confirmed_date": "2026-10-25",
  "start_time": "17:20:00",
  "end_time": "17:40:00",
  "session_name": "Evening Clinic",
  "token_number": 4,
  "clinic_notes": "Confirmed over phone. Advised to bring previous dermatological prescriptions."
}
```
- **Response (200 OK)**:
```json
{
  "success": true,
  "message": "Booking confirmed successfully. Patient notified.",
  "booking": {
    "id": "39aa1122-3344-5566-7788-99aabbccddee",
    "booking_reference": "CR-2026-88192",
    "status": "confirmed",
    "confirmed_date": "2026-10-25",
    "start_time": "17:20:00",
    "token_number": 4
  }
}
```

---

### 5.5 Appointment Day: Patient Arrival & Visit Lifecycle
Tracks the patient through the consultation stages: `arrived` -> `in_consultation` -> `completed`.

- **Method & URL**: `POST /api/bookings/39aa1122-3344-5566-7788-99aabbccddee/visit-status/`
- **Auth**: `Bearer <access_token>`
- **Request Body**:
```json
{
  "visit_status": "in_consultation",
  "notes": "Patient checked in at 17:15. Vitals recorded by Nurse Priya. Entering Doctor chamber."
}
```
- **Response (200 OK)**:
```json
{
  "success": true,
  "message": "Patient visit status updated to 'in_consultation'.",
  "current_status": "in_consultation"
}
```

---

# Phase 6: Patient CRM & Clinical Charting

The lead or booking converts into an electronic healthcare record (EHR) where vitals, clinical notes, prescriptions, and recall follow-ups are preserved.

---

### 6.1 Convert Lead to Permanent Patient Record
- **Method & URL**: `POST /api/patients/convert-lead/a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d/`
- **Auth**: `Bearer <access_token>`, `X-Practice-ID`
- **Response (201 Created)**:
```json
{
  "success": true,
  "message": "Lead converted to permanent patient chart successfully.",
  "patient": {
    "id": "88776655-4433-2211-00aa-bbccddeeff11",
    "patient_id": "PAT-2026-00109",
    "first_name": "Pooja",
    "last_name": "Verma",
    "full_name": "Pooja Verma",
    "phone_number": "+919822334455",
    "status": "active"
  }
}
```

---

### 6.2 Record Patient Vitals (Nurse / Assistant)
- **Method & URL**: `POST /api/patients/88776655-4433-2211-00aa-bbccddeeff11/vitals/`
- **Auth**: `Bearer <access_token>`
- **Request Body**:
```json
{
  "blood_pressure_systolic": 118,
  "blood_pressure_diastolic": 76,
  "pulse_bpm": 74,
  "temperature_fahrenheit": 98.4,
  "oxygen_saturation_spo2": 99,
  "weight_kg": 56.5,
  "height_cm": 164.0,
  "notes": "Normal baseline vitals before laser procedure."
}
```
- **Response (201 Created)**:
```json
{
  "id": "22334455-6677-8899-aabb-ccddeeff0011",
  "bmi": 21.0,
  "recorded_by_name": "Nurse Priya",
  "created_at": "2026-10-25T17:18:00Z"
}
```

---

### 6.3 Clinical Doctor Notes & Pinned Medical Alerts
The doctor notes diagnoses, treatment plans, and pins an allergy alert.

- **Method & URL**: `POST /api/patients/88776655-4433-2211-00aa-bbccddeeff11/notes/`
- **Auth**: `Bearer <access_token>`
- **Request Body**:
```json
{
  "category": "clinical",
  "note": "Diagnosis: Grade 3 Inflammatory Acne Vulgaris. Plan: Start Clindamycin gel morning, Adapalene 0.1% bedtime. Scheduled for chemical peel in 2 weeks. CAUTION: Patient reports mild contact dermatitis to benzoyl peroxide.",
  "is_pinned": true
}
```
- **Response (201 Created)**:
```json
{
  "id": "33445566-7788-99aa-bbcc-ddeeff001122",
  "category": "clinical",
  "category_display": "Clinical Examination",
  "is_pinned": true,
  "author_name": "Dr. Aditi Sharma",
  "created_at": "2026-10-25T17:35:00Z"
}
```

---

### 6.4 Schedule Patient Follow-Up / Recall Task
Ensures high retention by queuing a clinical review task.

- **Method & URL**: `POST /api/patients/88776655-4433-2211-00aa-bbccddeeff11/follow-ups/`
- **Auth**: `Bearer <access_token>`
- **Request Body**:
```json
{
  "follow_up_type": "clinical_review",
  "priority": "medium",
  "due_date": "2026-11-08",
  "title": "2-Week Acne Therapy Progress Review",
  "instructions": "Call patient to assess tolerance of topical Adapalene and book Chemical Peel session."
}
```
- **Response (201 Created)**:
```json
{
  "id": "44556677-8899-aabb-ccdd-eeff00112233",
  "status": "pending",
  "due_date": "2026-11-08",
  "title": "2-Week Acne Therapy Progress Review"
}
```

---

### 6.5 Complete Follow-up Call
- **Method & URL**: `POST /api/patients/follow-ups/44556677-8899-aabb-ccdd-eeff00112233/complete/`
- **Auth**: `Bearer <access_token>`
- **Request Body**:
```json
{
  "outcome_notes": "Spoke with Pooja. Skin adapting well to Adapalene with no redness. Booked peel for Saturday."
}
```
- **Response (200 OK)**:
```json
{
  "success": true,
  "message": "Follow-up marked as completed.",
  "completed_at": "2026-11-08T10:15:00Z"
}
```

---

# Phase 7: WhatsApp Automation & Patient Reminders

ClinicRise connects directly to the **Meta WhatsApp Cloud API** to deliver pre-approved medical templates, appointment confirmations, 24h & 2h automated reminders, and Google review requests.

---

### 7.1 WhatsApp Business Gateway Configuration
- **Method & URL**: `POST /api/whatsapp/config/`
- **Auth**: `Bearer <access_token>`, `X-Practice-ID`
- **Request Body**:
```json
{
  "phone_number_id": "100982348912345",
  "waba_id": "998811223344556",
  "access_token": "EAAQ3ZCZB...",
  "display_phone_number": "+919876543210",
  "business_name": "Arogya Skin & Laser Clinic",
  "is_enabled": true,
  "auto_confirmation_enabled": true,
  "auto_reminders_enabled": true,
  "post_visit_review_enabled": true
}
```
- **Response (200 OK)**:
```json
{
  "id": "55667788-99aa-bbcc-ddee-ff0011223344",
  "business_name": "Arogya Skin & Laser Clinic",
  "masked_access_token": "EAAQ3Z••••••••2345",
  "is_enabled": true
}
```

---

### 7.2 Seed Default Clinical WhatsApp Templates
Initializes standard pre-approved healthcare communication templates.

- **Method & URL**: `POST /api/whatsapp/templates/seed-defaults/`
- **Auth**: `Bearer <access_token>`
- **Response (200 OK)**:
```json
{
  "success": true,
  "message": "Successfully seeded 5 default WhatsApp clinical templates.",
  "templates": [
    {"name": "booking_confirmation", "title": "Appointment Confirmation with Token/Time"},
    {"name": "reminder_24h", "title": "24-Hour Upcoming Appointment Reminder"},
    {"name": "reminder_2h", "title": "2-Hour Final Call / Directions Reminder"},
    {"name": "post_visit_review", "title": "Post-Consultation Google Review Request"},
    {"name": "lead_auto_reply", "title": "New Inquiry Welcome & Operating Hours"}
  ]
}
```

---

### 7.3 Instant Test Send WhatsApp Message
- **Method & URL**: `POST /api/whatsapp/test-send/`
- **Auth**: `Bearer <access_token>`
- **Request Body**:
```json
{
  "phone_number": "+919822334455",
  "message_text": "Hello Pooja, this is a test message from Arogya Skin & Laser Clinic confirming our WhatsApp automation connection."
}
```
- **Response (200 OK)**:
```json
{
  "success": true,
  "message_id": "wamid.HBgMOTE5ODIyMzM0NDU1FQIAEhgg...",
  "status": "sent"
}
```

---

### 7.4 Process Queued Automated Reminders
Background worker endpoint (or manual trigger) that sends pending 24h & 2h appointment reminders.

- **Method & URL**: `POST /api/whatsapp/reminders/process-now/`
- **Auth**: `Bearer <access_token>`
- **Response (200 OK)**:
```json
{
  "success": true,
  "processed_count": 4,
  "sent_count": 4,
  "failed_count": 0
}
```

---

### 7.5 Patient Consent Opt-Out Verification
Strict healthcare compliance check before sending any automated WhatsApp message.

- **Method & URL**: `GET /api/whatsapp/opt-outs/check/?phone_number=%2B919822334455`
- **Auth**: `Bearer <access_token>`
- **Response (200 OK)**:
```json
{
  "phone_number": "+919822334455",
  "is_opted_out": false,
  "can_receive_whatsapp": true
}
```

---

# Phase 8: Subscriptions, Invoicing & Billing

Medical practices choose a plan (Starter, Professional, Enterprise) and pay via Razorpay or Stripe.

---

### 8.1 Subscription Plans & Pricing Catalog
- **Method & URL**: `GET /api/billing/plans/`
- **Auth**: Public or Authenticated
- **Response (200 OK)**:
```json
{
  "count": 3,
  "results": [
    {
      "id": "1a2b3c4d-5e6f-7a8b-9c0d-112233445566",
      "name": "Professional Clinic",
      "tier": "professional",
      "monthly_price": 2999.00,
      "yearly_price": 29990.00,
      "currency": "INR",
      "max_doctors": 5,
      "max_staff": 10,
      "custom_domain_enabled": true,
      "whatsapp_notifications_enabled": true,
      "analytics_reports_enabled": true
    }
  ]
}
```

---

### 8.2 Current Usage Summary
- **Method & URL**: `GET /api/billing/usage/`
- **Auth**: `Bearer <access_token>`, `X-Practice-ID`
- **Response (200 OK)**:
```json
{
  "plan_name": "Professional Clinic",
  "doctors": {"used": 1, "limit": 5, "remaining": 4},
  "staff": {"used": 2, "limit": 10, "remaining": 8},
  "appointments_this_month": {"used": 42, "limit": -1, "is_unlimited": true}
}
```

---

### 8.3 Initiate Checkout Session (Razorpay / Stripe)
Generates an online payment order.

- **Method & URL**: `POST /api/billing/checkout/`
- **Auth**: `Bearer <access_token>`, `X-Practice-ID`
- **Request Body**:
```json
{
  "plan_id": "1a2b3c4d-5e6f-7a8b-9c0d-112233445566",
  "interval": "yearly"
}
```
- **Response (200 OK)**:
```json
{
  "success": true,
  "invoice_id": "88990011-2233-4455-6677-8899aabbccdd",
  "amount": 29990.00,
  "currency": "INR",
  "gateway": "razorpay",
  "razorpay_order_id": "order_RBz8901jkl2345",
  "key_id": "rzp_live_example123"
}
```

---

### 8.4 Verify Payment Signature & Activate Plan
- **Method & URL**: `POST /api/billing/verify-payment/`
- **Auth**: `Bearer <access_token>`
- **Request Body**:
```json
{
  "invoice_id": "88990011-2233-4455-6677-8899aabbccdd",
  "razorpay_order_id": "order_RBz8901jkl2345",
  "razorpay_payment_id": "pay_RBz91234567890",
  "razorpay_signature": "e5c70912d091823ab1923019238120391283"
}
```
- **Response (200 OK)**:
```json
{
  "success": true,
  "message": "Payment verified successfully. Subscription activated!",
  "subscription": {
    "status": "active",
    "plan": "Professional Clinic",
    "interval": "yearly",
    "current_period_end": "2027-10-23T09:00:00Z"
  }
}
```

---

### 8.5 Printable GST Tax Invoice & Receipt
- **Method & URL**: `GET /api/billing/invoices/88990011-2233-4455-6677-8899aabbccdd/receipt/`
- **Auth**: `Bearer <access_token>`
- **Response**: Printable HTML document containing GST breakdown (CGST 9%, SGST 9%), invoice number (`INV-2026-0038`), and practice billing details.

---

# Phase 9: Growth Analytics & Executive PDF Reports

Provides the practice owner with clear visibility into patient acquisition costs, Google rankings, and overall revenue ROI.

---

### 9.1 Practice Analytics Cockpit
- **Method & URL**: `GET /api/analytics/dashboard/?period=30d`
- **Auth**: `Bearer <access_token>`, `X-Practice-ID`
- **Response (200 OK)**:
```json
{
  "period": "30d",
  "total_visitors": 1420,
  "total_pageviews": 3890,
  "total_leads": 84,
  "total_bookings": 62,
  "conversion_rate": 5.91,
  "top_services": [
    {"name": "Acne & Scar Laser Treatment", "inquiries": 38},
    {"name": "General Dermatology Consultation", "inquiries": 29}
  ]
}
```

---

### 9.2 Patient Acquisition Funnel
- **Method & URL**: `GET /api/analytics/funnel/`
- **Auth**: `Bearer <access_token>`
- **Response (200 OK)**:
```json
{
  "funnel_steps": [
    {"stage": "Website Visitors", "count": 1420, "conversion_rate": 100.0},
    {"stage": "Page Interacted / Click Event", "count": 410, "conversion_rate": 28.87},
    {"stage": "Form Inquiries Submitted", "count": 84, "conversion_rate": 5.91},
    {"stage": "Appointments Confirmed", "count": 62, "conversion_rate": 4.36},
    {"stage": "Consultations Completed", "count": 58, "conversion_rate": 4.08}
  ]
}
```

---

### 9.3 Trigger Automated Monthly Growth Report Generation
Aggregates patient intake, Google rankings, GBP reviews, and ROI.

- **Method & URL**: `POST /api/reports/monthly/generate/`
- **Auth**: `Bearer <access_token>`, `X-Practice-ID`
- **Request Body**:
```json
{
  "year": 2026,
  "month": 10
}
```
- **Response (201 Created)**:
```json
{
  "id": "77889900-1122-3344-5566-aabbccddeeff",
  "title": "Monthly Growth Report - October 2026",
  "status": "ready",
  "pdf_download_url": "/api/reports/monthly/77889900-1122-3344-5566-aabbccddeeff/pdf/",
  "executive_summary": "In October 2026, Arogya Skin & Laser Clinic generated 84 new patient leads and 62 confirmed consultations (+18% MoM). 3 target keywords reached the Google Local 3-Pack, driving 310 direct calls."
}
```

---

### 9.4 Download Executive PDF Report
- **Method & URL**: `GET /api/reports/monthly/77889900-1122-3344-5566-aabbccddeeff/pdf/`
- **Auth**: `Bearer <access_token>`
- **Response**: Binary `application/pdf` stream with charts, branding, and performance insights ready for board presentations or doctor reviews.

---

# Phase 10: Security, Privacy & Data Compliance (Ending)

Medical data security, HIPAA compliance, DPDP Act 2023 consent tracking, and cryptographic database snapshots guarantee healthcare-grade safety.

---

### 10.1 Active Role & Granular RBAC Permissions Check
Inspects exactly what the authenticated user can read or modify.

- **Method & URL**: `GET /api/security/roles/my-permissions/`
- **Auth**: `Bearer <access_token>`, `X-Practice-ID`
- **Response (200 OK)**:
```json
{
  "role": "owner",
  "is_owner": true,
  "is_doctor": true,
  "permissions": [
    "view_phi_records",
    "edit_clinical_notes",
    "approve_website_content",
    "manage_practice_billing",
    "trigger_data_backup",
    "manage_team_members"
  ]
}
```

---

### 10.2 Security Audit Trail (Immutable PHI Access Log)
Logs every access or modification of sensitive patient records.

- **Method & URL**: `GET /api/security/audit-logs/?action_type=patient_phi_view`
- **Auth**: `Bearer <access_token>` (Admin / Owner)
- **Response (200 OK)**:
```json
{
  "count": 1,
  "results": [
    {
      "id": "11220033-4455-6677-8899-aabbccddeeff",
      "user_name": "Dr. Aditi Sharma",
      "action": "PATIENT_RECORD_VIEW",
      "resource_type": "Patient",
      "resource_id": "88776655-4433-2211-00aa-bbccddeeff11",
      "ip_address": "103.21.12.44",
      "timestamp": "2026-10-25T17:15:30Z"
    }
  ]
}
```

---

### 10.3 Patient Consent Management (DPDP Act & HIPAA)
Registers verifiable opt-in or revocation of consent.

- **Record Consent**: `POST /api/security/consents/`
- **Auth**: `Bearer <access_token>`
- **Request Body**:
```json
{
  "patient_phone": "+919822334455",
  "consent_type": "telemedicine_and_whatsapp",
  "purpose": "Appointment reminders, clinical lab reports, and follow-up consultation advisories",
  "ip_address": "103.21.12.44"
}
```
- **Response (201 Created)**:
```json
{
  "success": true,
  "message": "Consent recorded with cryptographic timestamp.",
  "consent_id": "aa11bb22-cc33-dd44-ee55-ff6677889900"
}
```

- **Withdraw Consent**: `POST /api/security/consents/withdraw/`
- **Request Body**:
```json
{
  "patient_phone": "+919822334455",
  "consent_type": "telemedicine_and_whatsapp",
  "reason": "Patient requested stop on promotional WhatsApp messages"
}
```
- **Response (200 OK)**:
```json
{
  "success": true,
  "message": "Consent withdrawn. Automated channels immediately silenced for +919822334455."
}
```

---

### 10.4 Encrypted Practice Data Snapshot & Backup
Generates an encrypted snapshot of the clinic's records (patients, appointments, invoices, website revisions) with SHA-256 verification.

- **Trigger Backup**: `POST /api/security/backups/`
- **Auth**: `Bearer <access_token>` (Owner only)
- **Request Body**:
```json
{
  "description": "Pre-system update full practice backup"
}
```
- **Response (201 Created)**:
```json
{
  "id": "bb22cc33-dd44-ee55-ff66-778899001122",
  "status": "completed",
  "file_size_mb": 14.8,
  "sha256_checksum": "a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8",
  "created_at": "2026-10-23T09:20:00Z",
  "download_url": "/api/security/backups/bb22cc33-dd44-ee55-ff66-778899001122/download/"
}
```

- **Verify Backup Integrity**: `GET /api/security/backups/bb22cc33-dd44-ee55-ff66-778899001122/verify/`
- **Response (200 OK)**:
```json
{
  "backup_id": "bb22cc33-dd44-ee55-ff66-778899001122",
  "is_valid": true,
  "checksum_verified": true,
  "message": "Archive integrity validated. 0 errors detected."
}
```

---

## 🏁 Summary Table of Endpoints Flow-Wise

| Phase | Category | Endpoint | Method | Key Action |
| :--- | :--- | :--- | :--- | :--- |
| **1** | Auth | `/api/auth/otp/send/` | POST | Request Mobile 6-digit OTP |
| **1** | Auth | `/api/auth/otp/verify/` | POST | Verify OTP & issue JWT Tokens |
| **1** | Auth | `/api/auth/google/` | POST | Google Sign-In with OAuth token |
| **1** | Onboarding | `/api/practices/onboarding/progress/` | GET | Check onboarding step status |
| **1** | Onboarding | `/api/practices/onboarding/step/doctor-profile/` | POST | Save Doctor profile & license |
| **1** | Onboarding | `/api/practices/onboarding/step/clinic-details/` | POST | Create Practice tenant |
| **1** | Onboarding | `/api/practices/onboarding/step/services/` | POST | Add clinical services catalog |
| **1** | Onboarding | `/api/practices/onboarding/step/timings/` | POST | Configure OPD consultation hours |
| **1** | Onboarding | `/api/practices/onboarding/step/images/` | POST | Upload clinic photos & avatar |
| **1** | Onboarding | `/api/practices/onboarding/complete/` | POST | Finalize doctor onboarding |
| **1** | RBAC | `/api/practices/<id>/invite/` | POST | Invite staff (Reception, Nurse) |
| **2** | Websites | `/api/websites/generate/` | POST | 1-Click auto-generate clinic website |
| **2** | Websites | `/api/websites/public/<slug>/` | GET | Render public website Jamstack data |
| **2** | Websites | `/api/websites/<id>/domains/` | POST | Connect custom apex/subdomain |
| **2** | Websites | `/api/websites/<id>/approvals/` | GET | Doctor unified content approval queue |
| **2** | Websites | `/api/websites/<id>/pages/<pk>/review/` | POST | Doctor approve/reject website page |
| **3** | GBP | `/api/gbp/checklist/` | GET | 10-Step Google Business Profile setup |
| **3** | GBP | `/api/gbp/reviews/` | GET | Google patient reviews stream |
| **3** | GBP | `/api/gbp/reviews/<pk>/generate-reply/` | POST | AI empathetic clinical review reply |
| **3** | GBP | `/api/gbp/rank-tracking/check/` | POST | Audit Local 3-Pack keyword ranks |
| **4** | Leads | `/api/analytics/public/<slug>/visit/` | POST | Track website pageview visit |
| **4** | Leads | `/api/leads/public/<slug>/click-event/` | POST | Record Call / WhatsApp click event |
| **4** | Leads | `/api/leads/public/<slug>/inquire/` | POST | Public patient consultation inquiry |
| **4** | Leads | `/api/leads/inbox/` | GET | Authenticated lead CRM cockpit |
| **4** | Leads | `/api/leads/<id>/status/` | PATCH | Transition pipeline (`new` -> `qualified`) |
| **5** | Bookings | `/api/bookings/public/<slug>/availability/` | GET | Check real-time slots & session queue |
| **5** | Bookings | `/api/bookings/public/<slug>/request/` | POST | Public appointment booking request |
| **5** | Bookings | `/api/bookings/public/<slug>/track/<ref>/` | GET | Patient tracking by reference |
| **5** | Bookings | `/api/bookings/<id>/confirm/` | POST | Clinic confirms slot or token # |
| **5** | Bookings | `/api/bookings/<id>/visit-status/` | POST | Track `arrived` -> `in_consultation` |
| **6** | Patients | `/api/patients/convert-lead/<id>/` | POST | Convert qualified lead to patient |
| **6** | Patients | `/api/patients/<id>/vitals/` | POST | Record BP, pulse, SpO2, BMI, sugar |
| **6** | Patients | `/api/patients/<id>/notes/` | POST | Doctor clinical note & pinned alerts |
| **6** | Patients | `/api/patients/<id>/follow-ups/` | POST | Schedule recall / follow-up task |
| **7** | WhatsApp | `/api/whatsapp/config/` | POST | Meta Cloud API credentials |
| **7** | WhatsApp | `/api/whatsapp/templates/seed-defaults/` | POST | Seed standard clinical templates |
| **7** | WhatsApp | `/api/whatsapp/reminders/process-now/` | POST | Process scheduled 24h/2h reminders |
| **8** | Billing | `/api/billing/plans/` | GET | List subscription plans |
| **8** | Billing | `/api/billing/checkout/` | POST | Create Razorpay/Stripe checkout order |
| **8** | Billing | `/api/billing/verify-payment/` | POST | Verify payment signature & activate |
| **8** | Billing | `/api/billing/invoices/<id>/receipt/` | GET | Printable GST tax invoice HTML |
| **9** | Reports | `/api/analytics/dashboard/` | GET | Full practice analytics cockpit |
| **9** | Reports | `/api/reports/monthly/generate/` | POST | Generate monthly growth report |
| **9** | Reports | `/api/reports/monthly/<id>/pdf/` | GET | Download executive PDF report |
| **10** | Security | `/api/security/roles/my-permissions/` | GET | Granular user RBAC matrix |
| **10** | Security | `/api/security/audit-logs/` | GET | Immutable PHI access audit logs |
| **10** | Security | `/api/security/consents/` | POST | DPDP / HIPAA patient consent intake |
| **10** | Security | `/api/security/backups/` | POST | Encrypted practice data backup |

---

*Generated for ClinicRise Core Platform. All endpoints verified against active backend models, serializers, and permission matrices.*

# ClinicRise Practices, Multi-Tenancy & Permissions API

This document details the multi-tenant architecture, practice ownership, team memberships, role-based access control (RBAC), and doctor account management in **ClinicRise**.

---

## 1. Multi-Tenant Architecture & Isolation

In ClinicRise, each clinic, hospital branch, or private medical practice is a distinct **Tenant (`Practice`)**.

### Tenant Isolation Model
1. **Header-Based Tenant Scoping**:
   - Clients send the active practice ID in the HTTP header:
     ```http
     X-Practice-ID: <practice_uuid>
     ```
2. **`TenantIsolationMiddleware`**:
   - Validates that the authenticated user holds an active `PracticeMembership` for the specified practice.
   - Automatically injects `request.practice` and `request.membership` into the request context.
   - Rejects cross-tenant access attempts immediately with `403 Forbidden`.
   - If no header is provided and the user belongs to only 1 practice, it automatically defaults to that practice for convenience.
3. **`TenantAwareModel` Base Class**:
   - Any future clinic-scoped entities (Patients, Appointments, Prescriptions, Billing) inherit from `TenantAwareModel`, binding all records directly to `practice_id`.

---

## 2. Roles & Permissions Hierarchy

| Role | Code | Scope & Capabilities |
| :--- | :--- | :--- |
| **Practice Owner** | `owner` | Full legal ownership. Can delete/deactivate practice, manage billing/settings, and invite/remove any team member. Cannot be deleted or demoted. |
| **Practice Admin** | `admin` | Clinic managers / head administrators. Can update practice details, invite doctors and staff, and manage roles. |
| **Doctor / Practitioner** | `doctor` | Medical doctors, dentists, therapists. Can manage appointments, access clinical notes, prescriptions, and public doctor profile. |
| **Staff / Receptionist** | `staff` | Frontdesk receptionists, nurses, lab technicians. Can manage scheduling, patient check-ins, and basic intake. |

---

## 3. API Endpoints

### 3.1 Practice Management

#### A. List My Practices
- **URL**: `GET /api/practices/`
- **Permissions**: Authenticated (`Bearer <access_token>`)
- **Response (200 OK)**:
```json
[
  {
    "id": "7b58c5f0-6c92-494b-a7e6-b6059c1187d2",
    "name": "Apollo Dental Care",
    "slug": "apollo-dental-care-a1b2c3d4",
    "owner_name": "Dr. Rajesh Sharma",
    "owner_email": "rajesh@clinicrise.com",
    "phone_number": "+919876543210",
    "email": "contact@apollodental.com",
    "city": "Hyderabad",
    "state": "Telangana",
    "country": "India",
    "currency": "INR",
    "timezone": "Asia/Kolkata",
    "is_active": true,
    "members_count": 5,
    "current_user_role": "owner"
  }
]
```

---

#### B. Create a New Practice Tenant
- **URL**: `POST /api/practices/`
- **Permissions**: Authenticated (`Bearer <access_token>`)
- **Request Body**:
```json
{
  "name": "Sunrise Multispeciality Clinic",
  "phone_number": "+919876543210",
  "email": "info@sunriseclinic.com",
  "website": "https://sunriseclinic.com",
  "address": "Road No 36, Jubilee Hills",
  "city": "Hyderabad",
  "state": "Telangana",
  "postal_code": "500033",
  "country": "India",
  "currency": "INR",
  "timezone": "Asia/Kolkata"
}
```
*(The creating user is automatically assigned as the `owner` and granted the `owner` membership).*

---

#### C. Get Current Active Tenant Context
- **URL**: `GET /api/practices/current/`
- **Header**: `X-Practice-ID: <practice_uuid>`
- **Response (200 OK)**:
```json
{
  "practice": {
    "id": "7b58c5f0-6c92-494b-a7e6-b6059c1187d2",
    "name": "Sunrise Multispeciality Clinic",
    ...
  },
  "membership": {
    "id": "184b45cf-619a-4712-ba66-e8db50ba3a21",
    "role": "owner",
    "role_display": "Practice Owner",
    "is_active": true
  }
}
```

---

### 3.2 Team Memberships & Invitations

#### A. List Practice Members
- **URL**: `GET /api/practices/<practice_id>/members/`
- **Permissions**: `IsPracticeMember` (Requires membership in practice)
- **Response (200 OK)**:
```json
[
  {
    "id": "184b45cf-619a-4712-ba66-e8db50ba3a21",
    "user_id": "993510c4-9725-455b-86d7-ea886c9d784a",
    "user_name": "Dr. Priya Patel",
    "user_email": "priya@gmail.com",
    "user_phone": "+919876500002",
    "role": "doctor",
    "role_display": "Doctor / Practitioner",
    "is_active": true,
    "joined_at": "2026-10-16T10:45:00Z",
    "doctor_profile": {
      "medical_license_number": "MCI-2026-9921",
      "specialization": "Dermatologist",
      "qualifications": "MBBS, MD (Dermatology)",
      "experience_years": 8,
      "default_consultation_fee": "600.00"
    }
  }
]
```

---

#### B. Invite Doctor / Staff Member
- **URL**: `POST /api/practices/<practice_id>/invite/`
- **Permissions**: `IsPracticeAdmin` (Owner or Admin only)
- **Request Body**:
```json
{
  "identifier": "dr.smith@gmail.com",
  "role": "doctor"
}
```
*(Accepts either email or phone number `+919876543210`. Role options: `admin`, `doctor`, `staff`)*

- **Response (201 Created)**:
```json
{
  "success": true,
  "message": "Invitation generated for dr.smith@gmail.com as doctor.",
  "invite_code": "k9L1pA9vB-902x18Z...",
  "invitation": {
    "id": "52857474-0fef-4ea6-8803-f3c5adfbce62",
    "practice_name": "Sunrise Multispeciality Clinic",
    "role": "doctor",
    "status": "pending",
    "expires_at": "2026-10-23T10:45:00Z"
  }
}
```

---

#### C. Accept Invitation Code
- **URL**: `POST /api/practices/invitations/accept/`
- **Permissions**: Authenticated (`Bearer <access_token>`)
- **Request Body**:
```json
{
  "invite_code": "k9L1pA9vB-902x18Z..."
}
```
- **Response (200 OK)**:
```json
{
  "success": true,
  "message": "Successfully joined Sunrise Multispeciality Clinic as Doctor / Practitioner."
}
```

---

#### D. Update Member Role / Deactivate Member
- **URL**: `PATCH /api/practices/<practice_id>/members/<membership_id>/`
- **Permissions**: `IsPracticeAdmin`
- **Request Body**:
```json
{
  "role": "admin",
  "is_active": true
}
```

---

### 3.3 Doctor Accounts & Profiles

#### A. Get Current User's Doctor Profile
- **URL**: `GET /api/practices/doctor/profile/`
- **Permissions**: Authenticated (`Bearer <access_token>`)

---

#### B. Create / Register Doctor Profile
- **URL**: `POST /api/practices/doctor/profile/`
- **Permissions**: Authenticated (`Bearer <access_token>`)
- **Request Body**:
```json
{
  "medical_license_number": "MCI-TEL-2026-4412",
  "specialization": "Cardiologist",
  "qualifications": "MBBS, MD (General Medicine), DM (Cardiology)",
  "experience_years": 10,
  "bio": "Senior Consultant Interventional Cardiologist specializing in preventive heart health.",
  "default_consultation_fee": "800.00"
}
```

---

#### C. List All Doctors in a Practice
- **URL**: `GET /api/practices/<practice_id>/doctors/`
- **Permissions**: `IsPracticeMember`
- **Header**: `X-Practice-ID: <practice_id>`
- Returns all practitioners with their medical credentials, specialization, and consultation fees for clinical scheduling.

---

## 4. Database Migrations & Testing

Run migrations to apply the new schema:

```powershell
python manage.py migrate
```

Run test suite:

```powershell
python manage.py test practices
```

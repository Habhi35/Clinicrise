# ClinicRise Authentication & Session Management API

This document details the backend authentication architecture and API contracts for **ClinicRise**.

---

## 1. Overview & Architecture

- **Framework**: Django REST Framework (DRF)
- **Session Management**: JSON Web Tokens (JWT) via `djangorestframework-simplejwt` with automatic rotation and token blacklisting on logout.
- **Identity Model**: Custom `User` model with UUID primary keys supporting dual-login by phone number or email.
- **Mobile OTP Engine**: Pluggable SMS service with built-in rate-limiting cooldown (60s), cryptographic 6-digit generation, expiration tracking, and adapters for:
  - `console` (default for local dev – prints to console and returns in response when `DEBUG=True`)
  - `twilio` (Twilio SMS API)
  - `fast2sms` (Fast2SMS API)
  - `custom_http` (generic SMS gateway webhook)
- **Google Sign-In**: Verifies Google OAuth2 ID tokens via Google Auth library (`google-auth`) with dev mock fallback (`mock-google:<email>` during debug mode).
- **Account Recovery**: Secure OTP-based password reset for phone numbers and email addresses.

---

## 2. API Endpoints

### 2.1 Mobile OTP Authentication

#### A. Request Mobile OTP
- **URL**: `POST /api/auth/otp/send/`
- **Permissions**: Public (`AllowAny`)
- **Request Body**:
```json
{
  "phone_number": "+919876543210",
  "purpose": "login"
}
```
> Note: `purpose` can be `login`, `verify_phone`, or `password_reset`. Defaults to `login`.

- **Success Response (200 OK)**:
```json
{
  "success": true,
  "message": "OTP sent to +919876543210 successfully.",
  "purpose": "login",
  "expires_in_minutes": 5,
  "dev_otp": "729481" 
}
```
*(In debug mode, `dev_otp` is included for effortless testing without waiting for SMS delivery).*

- **Rate Limit Response (429 Too Many Requests)**:
```json
{
  "error": "Please wait 54 seconds before requesting a new OTP."
}
```

---

#### B. Verify Mobile OTP (Passwordless Login / Registration)
- **URL**: `POST /api/auth/otp/verify/`
- **Permissions**: Public (`AllowAny`)
- **Request Body**:
```json
{
  "phone_number": "+919876543210",
  "otp_code": "729481",
  "purpose": "login"
}
```

- **Success Response (200 OK)**:
```json
{
  "message": "Authentication successful.",
  "is_new_user": true,
  "tokens": {
    "refresh": "<jwt_refresh_token>",
    "access": "<jwt_access_token>"
  },
  "user": {
    "id": "e4b6c310-8b43-4f90-a4a9-a99f182c478a",
    "email": null,
    "phone_number": "+919876543210",
    "first_name": "",
    "last_name": "",
    "full_name": "+919876543210",
    "avatar_url": null,
    "is_email_verified": false,
    "is_phone_verified": true,
    "auth_provider": "phone",
    "date_joined": "2026-10-16T10:30:00Z"
  }
}
```

---

### 2.2 Google Sign-In

- **URL**: `POST /api/auth/google/`
- **Permissions**: Public (`AllowAny`)
- **Request Body**:
```json
{
  "id_token": "<google_oauth2_id_token>"
}
```
*(For local testing in `DEBUG=True`, you can pass `"id_token": "mock-google:doctor@clinicrise.com"`)*

- **Success Response (200 OK)**:
```json
{
  "message": "Google authentication successful.",
  "is_new_user": false,
  "tokens": {
    "refresh": "<jwt_refresh_token>",
    "access": "<jwt_access_token>"
  },
  "user": {
    "id": "c138db31-50e8-466d-8ff7-c6b758b29df9",
    "email": "doctor@clinicrise.com",
    "phone_number": null,
    "first_name": "Doctor",
    "last_name": "Clinic",
    "full_name": "Doctor Clinic",
    "avatar_url": "https://lh3.googleusercontent.com/...",
    "is_email_verified": true,
    "is_phone_verified": false,
    "auth_provider": "google",
    "date_joined": "2026-10-16T10:30:00Z"
  }
}
```

---

### 2.3 Session Management

#### A. Refresh Access Token
- **URL**: `POST /api/auth/token/refresh/`
- **Permissions**: Public (`AllowAny`)
- **Request Body**:
```json
{
  "refresh": "<jwt_refresh_token>"
}
```
- **Success Response (200 OK)**:
```json
{
  "access": "<new_jwt_access_token>",
  "refresh": "<new_jwt_rotated_refresh_token>"
}
```

---

#### B. Logout (Terminate Session & Invalidate Token)
- **URL**: `POST /api/auth/logout/`
- **Permissions**: Authenticated (`IsAuthenticated` with `Bearer <access_token>`)
- **Request Body**:
```json
{
  "refresh": "<jwt_refresh_token>"
}
```
- **Success Response (200 OK)**:
```json
{
  "success": true,
  "message": "Successfully logged out. Session invalidated."
}
```

---

#### C. Get / Update Current User Profile
- **URL**: `GET /api/auth/me/` | `PATCH /api/auth/me/`
- **Permissions**: Authenticated (`Bearer <access_token>`)
- **Request Body (PATCH)**:
```json
{
  "first_name": "Aditi",
  "last_name": "Sharma",
  "avatar_url": "https://example.com/avatar.jpg"
}
```

---

### 2.4 Account Recovery

#### A. Request Password Reset OTP
- **URL**: `POST /api/auth/password-reset/request/`
- **Permissions**: Public (`AllowAny`)
- **Request Body**:
```json
{
  "identifier": "doctor@clinicrise.com"
}
```
*(Accepts either registered email or registered phone number `+919876543210`)*

- **Success Response (200 OK)**:
```json
{
  "success": true,
  "message": "Password reset OTP sent to doctor@clinicrise.com.",
  "channel": "email",
  "dev_otp": "618392"
}
```

---

#### B. Confirm Password Reset with OTP
- **URL**: `POST /api/auth/password-reset/confirm/`
- **Permissions**: Public (`AllowAny`)
- **Request Body**:
```json
{
  "identifier": "doctor@clinicrise.com",
  "otp_code": "618392",
  "new_password": "NewSecretPassword2026!",
  "confirm_password": "NewSecretPassword2026!"
}
```
- **Success Response (200 OK)**:
```json
{
  "success": true,
  "message": "Password has been successfully reset.",
  "tokens": {
    "access": "<new_jwt_access_token>",
    "refresh": "<new_jwt_refresh_token>"
  },
  "user": { ... }
}
```

---

#### C. Change Password (Authenticated User)
- **URL**: `POST /api/auth/password/change/`
- **Permissions**: Authenticated (`Bearer <access_token>`)
- **Request Body**:
```json
{
  "old_password": "CurrentPassword123!",
  "new_password": "NewSecretPassword2026!",
  "confirm_password": "NewSecretPassword2026!"
}
```

---

### 2.5 Standard Email/Password Auth

- **Register**: `POST /api/auth/register/` (payload: `email`, `password`, `first_name`, `last_name`, `phone_number`)
- **Login**: `POST /api/auth/login/` (payload: `email`, `password`)

---

## 3. Database Migration Command

Run the following command in your terminal to apply the database migrations:

```powershell
python manage.py migrate
```

To run the automated authentication test suite:

```powershell
python manage.py test authentication
```

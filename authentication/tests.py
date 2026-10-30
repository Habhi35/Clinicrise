from datetime import timedelta
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from authentication.models import User, VerificationOTP
from authentication.services.otp_service import OTPService


class AuthenticationTests(APITestCase):

    def setUp(self):
        self.phone_number = "+919876543210"
        self.email = "doctor@clinicrise.com"
        self.password = "ClinicRiseSecret123!"

    def test_send_otp_success(self):
        """Test sending an OTP for mobile login."""
        url = reverse('authentication:otp_send')
        data = {
            "phone_number": self.phone_number,
            "purpose": "login"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get('success'))
        self.assertIn('dev_otp', response.data)

        # Check DB
        otp = VerificationOTP.objects.filter(identifier=self.phone_number, purpose='login').first()
        self.assertIsNotNone(otp)
        self.assertEqual(otp.otp_code, response.data['dev_otp'])

    def test_send_otp_rate_limiting(self):
        """Test rate-limiting cooldown prevents sending consecutive OTPs immediately."""
        url = reverse('authentication:otp_send')
        data = {"phone_number": self.phone_number, "purpose": "login"}

        first_res = self.client.post(url, data, format='json')
        self.assertEqual(first_res.status_code, status.HTTP_200_OK)

        # Immediate second request should be throttled
        second_res = self.client.post(url, data, format='json')
        self.assertEqual(second_res.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("Please wait", second_res.data.get('error', ''))

    def test_verify_otp_and_login_new_user(self):
        """Test verifying OTP creates a new user and returns JWT session tokens."""
        otp_record = OTPService.create_otp(self.phone_number, purpose='login')

        url = reverse('authentication:otp_verify')
        data = {
            "phone_number": self.phone_number,
            "otp_code": otp_record.otp_code,
            "purpose": "login"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get('is_new_user'))
        self.assertIn('tokens', response.data)
        self.assertIn('access', response.data['tokens'])
        self.assertIn('refresh', response.data['tokens'])

        user = User.objects.get(phone_number=self.phone_number)
        self.assertTrue(user.is_phone_verified)
        self.assertEqual(user.auth_provider, 'phone')

    def test_verify_otp_invalid_code(self):
        """Test verifying with incorrect OTP code fails."""
        OTPService.create_otp(self.phone_number, purpose='login')

        url = reverse('authentication:otp_verify')
        data = {
            "phone_number": self.phone_number,
            "otp_code": "000000",
            "purpose": "login"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get('error'), "Invalid OTP code.")

    def test_verify_otp_expired(self):
        """Test expired OTP is rejected."""
        otp_record = OTPService.create_otp(self.phone_number, purpose='login')
        otp_record.expires_at = timezone.now() - timedelta(minutes=1)
        otp_record.save()

        url = reverse('authentication:otp_verify')
        data = {
            "phone_number": self.phone_number,
            "otp_code": otp_record.otp_code,
            "purpose": "login"
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("expired", response.data.get('error', ''))

    def test_account_recovery_password_reset(self):
        """Test account recovery workflow: request reset OTP -> confirm new password."""
        user = User.objects.create_user(
            email=self.email,
            phone_number=self.phone_number,
            password=self.password,
            auth_provider='email'
        )

        # 1. Request recovery OTP
        req_url = reverse('authentication:password_reset_request')
        req_res = self.client.post(req_url, {"identifier": self.email}, format='json')
        self.assertEqual(req_res.status_code, status.HTTP_200_OK)

        otp_record = VerificationOTP.objects.filter(identifier=self.email, purpose='password_reset').first()
        self.assertIsNotNone(otp_record)

        # 2. Confirm password reset
        confirm_url = reverse('authentication:password_reset_confirm')
        new_pass = "ClinicRiseUpdatedPass2026!"
        confirm_data = {
            "identifier": self.email,
            "otp_code": otp_record.otp_code,
            "new_password": new_pass,
            "confirm_password": new_pass
        }
        confirm_res = self.client.post(confirm_url, confirm_data, format='json')
        self.assertEqual(confirm_res.status_code, status.HTTP_200_OK)
        self.assertIn('tokens', confirm_res.data)

        # 3. Verify user can authenticate with the new password
        user.refresh_from_db()
        self.assertTrue(user.check_password(new_pass))

    def test_session_logout_blacklists_refresh_token(self):
        """Test logging out blacklists the refresh token preventing further token refreshes."""
        user = User.objects.create_user(
            email=self.email,
            phone_number=self.phone_number,
            password=self.password
        )

        # Obtain token
        from authentication.services.jwt_service import get_tokens_for_user
        tokens = get_tokens_for_user(user)

        # Authenticate client
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # Call logout
        logout_url = reverse('authentication:logout')
        logout_res = self.client.post(logout_url, {"refresh": tokens['refresh']}, format='json')
        self.assertEqual(logout_res.status_code, status.HTTP_200_OK)

        # Attempt to refresh token using the blacklisted refresh token
        refresh_url = reverse('authentication:token_refresh')
        refresh_res = self.client.post(refresh_url, {"refresh": tokens['refresh']}, format='json')
        self.assertEqual(refresh_res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_google_login_mock(self):
        """Test Google Sign-In endpoint with mock token in debug mode."""
        url = reverse('authentication:google_auth')
        data = {"id_token": "mock-google:doctor.clinic@gmail.com"}

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get('is_new_user'))
        self.assertIn('tokens', response.data)
        self.assertEqual(response.data['user']['email'], 'doctor.clinic@gmail.com')
        self.assertEqual(response.data['user']['auth_provider'], 'google')


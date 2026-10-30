import logging
import os
import secrets
from datetime import timedelta
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
import requests

from authentication.models import VerificationOTP

logger = logging.getLogger(__name__)


class OTPService:
    """Service to handle generation, dispatch, and validation of One-Time Passwords."""

    OTP_EXPIRY_MINUTES = getattr(settings, 'OTP_EXPIRY_MINUTES', 5)
    OTP_COOLDOWN_SECONDS = getattr(settings, 'OTP_COOLDOWN_SECONDS', 60)

    @classmethod
    def generate_code(cls) -> str:
        """Generates a secure 6-digit random string."""
        return str(secrets.SystemRandom().randint(100000, 999999))

    @classmethod
    def can_request_otp(cls, identifier: str, purpose: str):
        """Checks rate limiting: prevents requesting another OTP before the cooldown expires."""
        latest_otp = (
            VerificationOTP.objects.filter(
                identifier=identifier,
                purpose=purpose,
            )
            .order_by('-created_at')
            .first()
        )

        if latest_otp:
            time_since_creation = (timezone.now() - latest_otp.created_at).total_seconds()
            if time_since_creation < cls.OTP_COOLDOWN_SECONDS:
                remaining = int(cls.OTP_COOLDOWN_SECONDS - time_since_creation)
                return False, f"Please wait {remaining} seconds before requesting a new OTP."

        return True, None

    @classmethod
    def create_otp(cls, identifier: str, purpose: str = 'login') -> VerificationOTP:
        """
        Creates and stores a new OTP record for the identifier.
        Invalidates any previous unused OTPs for this identifier and purpose.
        """
        # Invalidate previous unused OTPs
        VerificationOTP.objects.filter(
            identifier=identifier,
            purpose=purpose,
            is_used=False
        ).update(is_used=True)

        code = cls.generate_code()
        expires_at = timezone.now() + timedelta(minutes=cls.OTP_EXPIRY_MINUTES)

        otp = VerificationOTP.objects.create(
            identifier=identifier,
            otp_code=code,
            purpose=purpose,
            expires_at=expires_at,
        )
        return otp

    @classmethod
    def send_sms(cls, phone_number: str, otp_code: str) -> dict:
        """
        Dispatches SMS via configured provider:
        - console (default for dev/local)
        - twilio (Twilio SMS API)
        - fast2sms (Fast2SMS API)
        - custom_http (Generic webhook/gateway)
        """
        provider = getattr(settings, 'OTP_PROVIDER', 'console').lower()
        message = f"Your ClinicRise verification code is {otp_code}. Valid for {cls.OTP_EXPIRY_MINUTES} minutes. Do not share this with anyone."

        logger.info(f"Dispatching OTP via provider '{provider}' to {phone_number}")

        if provider == 'twilio':
            return cls._send_twilio(phone_number, message)
        elif provider == 'fast2sms':
            return cls._send_fast2sms(phone_number, otp_code)
        elif provider == 'custom_http':
            return cls._send_custom_http(phone_number, message, otp_code)
        else:
            # Default to console/logging
            return cls._send_console(phone_number, otp_code, message)

    @classmethod
    def _send_console(cls, phone_number: str, otp_code: str, message: str) -> dict:
        banner = "=" * 50
        print(f"\n{banner}\n[ClinicRise OTP SERVICE]\nPhone: {phone_number}\nOTP Code: {otp_code}\nMessage: {message}\n{banner}\n")
        logger.info(f"[SMS OTP Dev Console] Sent OTP {otp_code} to {phone_number}")
        return {"success": True, "provider": "console"}

    @classmethod
    def _send_twilio(cls, phone_number: str, message: str) -> dict:
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        from_number = os.getenv('TWILIO_PHONE_NUMBER')

        if not all([account_sid, auth_token, from_number]):
            logger.warning("Twilio credentials not configured; falling back to console.")
            return cls._send_console(phone_number, "TwilioNotConfigured", message)

        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
            response = requests.post(
                url,
                data={'From': from_number, 'To': phone_number, 'Body': message},
                auth=(account_sid, auth_token),
                timeout=10
            )
            if response.status_code in [200, 201]:
                return {"success": True, "provider": "twilio"}
            else:
                logger.error(f"Twilio error: {response.text}")
                return {"success": False, "error": response.text}
        except Exception as e:
            logger.exception("Failed to send SMS via Twilio")
            return {"success": False, "error": str(e)}

    @classmethod
    def _send_fast2sms(cls, phone_number: str, otp_code: str) -> dict:
        api_key = os.getenv('FAST2SMS_API_KEY')
        if not api_key:
            logger.warning("Fast2SMS API key not found; falling back to console.")
            return cls._send_console(phone_number, otp_code, "Fast2SMSNotConfigured")

        try:
            url = "https://www.fast2sms.com/dev/bulkV2"
            headers = {"authorization": api_key}
            payload = {
                "variables_values": otp_code,
                "route": "otp",
                "numbers": phone_number.replace("+91", "").strip(),
            }
            response = requests.post(url, data=payload, headers=headers, timeout=10)
            res_json = response.json()
            if res_json.get("return") is True:
                return {"success": True, "provider": "fast2sms"}
            else:
                return {"success": False, "error": res_json.get("message")}
        except Exception as e:
            logger.exception("Failed to send SMS via Fast2SMS")
            return {"success": False, "error": str(e)}

    @classmethod
    def _send_custom_http(cls, phone_number: str, message: str, otp_code: str) -> dict:
        gateway_url = os.getenv('SMS_GATEWAY_URL')
        if not gateway_url:
            return cls._send_console(phone_number, otp_code, message)
        try:
            response = requests.post(
                gateway_url,
                json={"phone": phone_number, "otp": otp_code, "message": message},
                timeout=10
            )
            return {"success": response.ok, "status_code": response.status_code}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    def send_email_otp(cls, email: str, otp_code: str, purpose_display: str = "Account Recovery") -> dict:
        """Sends verification code via email."""
        subject = f"ClinicRise - {purpose_display} Verification Code"
        message = (
            f"Hello,\n\n"
            f"Your verification code for {purpose_display} is: {otp_code}\n\n"
            f"This code will expire in {cls.OTP_EXPIRY_MINUTES} minutes. If you did not make this request, please ignore this email.\n\n"
            f"Best regards,\nThe ClinicRise Team"
        )
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@clinicrise.com'),
                recipient_list=[email],
                fail_silently=False,
            )
            return {"success": True}
        except Exception as e:
            logger.exception("Failed to send OTP email")
            # If in debug mode or console backend, still return success for developer ease
            if settings.DEBUG:
                print(f"[ClinicRise Email Dev Console] To: {email} | Code: {otp_code}")
                return {"success": True, "note": "Logged to console"}
            return {"success": False, "error": str(e)}

    @classmethod
    def verify_otp(cls, identifier: str, code: str, purpose: str = 'login'):
        """
        Validates OTP code for the given identifier and purpose.
        Returns (is_valid: bool, message: str).
        """
        otp = (
            VerificationOTP.objects.filter(
                identifier=identifier,
                purpose=purpose,
                is_used=False
            )
            .order_by('-created_at')
            .first()
        )

        if not otp:
            return False, "No active OTP found for this request. Please request a new OTP."

        return otp.is_valid(code)

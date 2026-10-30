from django.conf import settings
from django.contrib.auth import update_session_auth_hash
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from authentication.models import User, VerificationOTP
from authentication.serializers import (
    GoogleAuthSerializer,
    LoginSerializer,
    LogoutSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    SendOTPSerializer,
    UserSerializer,
    VerifyOTPSerializer,
)
from authentication.services.google_service import GoogleAuthService
from authentication.services.jwt_service import get_tokens_for_user
from authentication.services.otp_service import OTPService


class SendOTPView(APIView):
    """
    Endpoint to request a 6-digit OTP for Mobile Login, Verification, or Password Reset.
    POST /api/auth/otp/send/
    Payload: {"phone_number": "+919876543210", "purpose": "login"}
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data['phone_number']
        purpose = serializer.validated_data.get('purpose', 'login')

        # Check rate-limit cooldown
        can_send, cooldown_msg = OTPService.can_request_otp(phone_number, purpose)
        if not can_send:
            return Response(
                {"error": cooldown_msg},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        # Create OTP
        otp_record = OTPService.create_otp(phone_number, purpose=purpose)

        # Dispatch SMS
        dispatch_result = OTPService.send_sms(phone_number, otp_record.otp_code)

        resp_data = {
            "success": True,
            "message": f"OTP sent to {phone_number} successfully.",
            "purpose": purpose,
            "expires_in_minutes": OTPService.OTP_EXPIRY_MINUTES,
        }

        # In DEBUG mode or console OTP provider, return OTP in response for instant testing
        if getattr(settings, 'DEBUG', False) or getattr(settings, 'OTP_PROVIDER', '') == 'console':
            resp_data["dev_otp"] = otp_record.otp_code

        return Response(resp_data, status=status.HTTP_200_OK)


class VerifyOTPView(APIView):
    """
    Endpoint to verify OTP and authenticate user (Phone OTP Login).
    POST /api/auth/otp/verify/
    Payload: {"phone_number": "+919876543210", "otp_code": "123456", "purpose": "login"}
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data['phone_number']
        otp_code = serializer.validated_data['otp_code']
        purpose = serializer.validated_data.get('purpose', 'login')

        is_valid, validation_msg = OTPService.verify_otp(phone_number, otp_code, purpose=purpose)
        if not is_valid:
            return Response({"error": validation_msg}, status=status.HTTP_400_BAD_REQUEST)

        # Handle login / registration via phone OTP
        if purpose in ['login', 'verify_phone']:
            user, is_new_user = User.objects.get_or_create(
                phone_number=phone_number,
                defaults={
                    'is_phone_verified': True,
                    'auth_provider': 'phone',
                    'is_active': True,
                }
            )

            if not is_new_user and not user.is_phone_verified:
                user.is_phone_verified = True
                user.save(update_fields=['is_phone_verified'])

            user.last_login = timezone.now()
            user.save(update_fields=['last_login'])

            tokens = get_tokens_for_user(user)
            return Response(
                {
                    "message": "Authentication successful.",
                    "is_new_user": is_new_user,
                    "tokens": tokens,
                    "user": UserSerializer(user).data,
                },
                status=status.HTTP_200_OK
            )

        return Response(
            {"success": True, "message": validation_msg},
            status=status.HTTP_200_OK
        )


class GoogleAuthView(APIView):
    """
    Endpoint for Google Sign-In / Sign-Up.
    POST /api/auth/google/
    Payload: {"id_token": "<google_jwt_id_token>"}
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        id_token_str = serializer.validated_data['id_token']

        try:
            google_user_info = GoogleAuthService.verify_token(id_token_str)
        except ValueError as err:
            return Response({"error": str(err)}, status=status.HTTP_400_BAD_REQUEST)

        email = google_user_info['email']
        user = User.objects.filter(email=email).first()
        is_new_user = False

        if not user:
            is_new_user = True
            user = User.objects.create_user(
                email=email,
                first_name=google_user_info.get('first_name', ''),
                last_name=google_user_info.get('last_name', ''),
                avatar_url=google_user_info.get('avatar_url', ''),
                is_email_verified=True,
                auth_provider='google',
                is_active=True,
            )
        else:
            # Update verification & profile details if missing
            updated_fields = []
            if not user.is_email_verified:
                user.is_email_verified = True
                updated_fields.append('is_email_verified')
            if not user.avatar_url and google_user_info.get('avatar_url'):
                user.avatar_url = google_user_info['avatar_url']
                updated_fields.append('avatar_url')
            if not user.first_name and google_user_info.get('first_name'):
                user.first_name = google_user_info['first_name']
                updated_fields.append('first_name')
            if not user.last_name and google_user_info.get('last_name'):
                user.last_name = google_user_info['last_name']
                updated_fields.append('last_name')

            user.last_login = timezone.now()
            updated_fields.append('last_login')
            user.save(update_fields=updated_fields)

        tokens = get_tokens_for_user(user)

        return Response(
            {
                "message": "Google authentication successful.",
                "is_new_user": is_new_user,
                "tokens": tokens,
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK
        )


class PasswordResetRequestView(APIView):
    """
    Endpoint to request password recovery OTP via Phone or Email.
    POST /api/auth/password-reset/request/
    Payload: {"identifier": "+919876543210"} or {"identifier": "doctor@clinicrise.com"}
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        identifier = serializer.validated_data['identifier']
        is_email = '@' in identifier

        # Check user existence
        user = (
            User.objects.filter(email=identifier).first()
            if is_email
            else User.objects.filter(phone_number=identifier).first()
        )

        if not user:
            # We return a generic response for security to prevent user enumeration
            return Response(
                {
                    "success": True,
                    "message": "If an account exists with this credential, a recovery OTP has been sent."
                },
                status=status.HTTP_200_OK
            )

        # Check cooldown
        can_send, cooldown_msg = OTPService.can_request_otp(identifier, purpose='password_reset')
        if not can_send:
            return Response({"error": cooldown_msg}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        otp_record = OTPService.create_otp(identifier, purpose='password_reset')

        if is_email:
            OTPService.send_email_otp(identifier, otp_record.otp_code, purpose_display="Password Reset")
        else:
            OTPService.send_sms(identifier, otp_record.otp_code)

        resp_data = {
            "success": True,
            "message": f"Password reset OTP sent to {identifier}.",
            "channel": "email" if is_email else "sms",
        }

        if getattr(settings, 'DEBUG', False) or getattr(settings, 'OTP_PROVIDER', '') == 'console':
            resp_data["dev_otp"] = otp_record.otp_code

        return Response(resp_data, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    """
    Endpoint to verify OTP and set a new password.
    POST /api/auth/password-reset/confirm/
    Payload: {
        "identifier": "doctor@clinicrise.com",
        "otp_code": "123456",
        "new_password": "NewStrongPassword123!",
        "confirm_password": "NewStrongPassword123!"
    }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        identifier = serializer.validated_data['identifier']
        otp_code = serializer.validated_data['otp_code']
        new_password = serializer.validated_data['new_password']

        # Validate OTP
        is_valid, msg = OTPService.verify_otp(identifier, otp_code, purpose='password_reset')
        if not is_valid:
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch user
        is_email = '@' in identifier
        user = (
            User.objects.filter(email=identifier).first()
            if is_email
            else User.objects.filter(phone_number=identifier).first()
        )

        if not user:
            return Response({"error": "User account not found."}, status=status.HTTP_404_NOT_FOUND)

        # Update password
        user.set_password(new_password)
        user.save()

        # Generate fresh JWT session tokens
        tokens = get_tokens_for_user(user)

        return Response(
            {
                "success": True,
                "message": "Password has been successfully reset.",
                "tokens": tokens,
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK
        )


class PasswordChangeView(APIView):
    """
    Endpoint for authenticated user session to change password.
    POST /api/auth/password/change/
    Payload: {"old_password": "...", "new_password": "...", "confirm_password": "..."}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        old_password = serializer.validated_data['old_password']
        new_password = serializer.validated_data['new_password']

        if not user.check_password(old_password):
            return Response(
                {"old_password": ["Current password is incorrect."]},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(new_password)
        user.save()

        # Update session hash so session doesn't abruptly break
        update_session_auth_hash(request, user)

        # Issue refreshed JWT tokens
        tokens = get_tokens_for_user(user)

        return Response(
            {
                "success": True,
                "message": "Password changed successfully.",
                "tokens": tokens,
            },
            status=status.HTTP_200_OK
        )


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    Endpoint to retrieve and update the authenticated user's profile and active session.
    GET /api/auth/me/
    PATCH /api/auth/me/
    """
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class LogoutView(APIView):
    """
    Endpoint for secure session termination (revoking refresh token via SimpleJWT blacklist).
    POST /api/auth/logout/
    Payload: {"refresh": "<refresh_token>"}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refresh_token_str = serializer.validated_data['refresh']

        try:
            token = RefreshToken(refresh_token_str)
            token.blacklist()
            return Response(
                {"success": True, "message": "Successfully logged out. Session invalidated."},
                status=status.HTTP_200_OK
            )
        except TokenError as e:
            return Response(
                {"error": f"Invalid or already blacklisted token: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )


class RegisterView(APIView):
    """
    Standard Email/Password registration endpoint.
    POST /api/auth/register/
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        tokens = get_tokens_for_user(user)
        return Response(
            {
                "message": "Registration successful.",
                "tokens": tokens,
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED
        )


class LoginView(APIView):
    """
    Standard Email/Password login endpoint.
    POST /api/auth/login/
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])

        tokens = get_tokens_for_user(user)
        return Response(
            {
                "message": "Login successful.",
                "tokens": tokens,
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK
        )

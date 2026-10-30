import re
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from authentication.models import User, VerificationOTP


class UserSerializer(serializers.ModelSerializer):
    """Serializer for displaying and updating user profile information."""
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'phone_number',
            'first_name',
            'last_name',
            'full_name',
            'avatar_url',
            'is_email_verified',
            'is_phone_verified',
            'auth_provider',
            'date_joined',
        ]
        read_only_fields = [
            'id',
            'auth_provider',
            'is_email_verified',
            'is_phone_verified',
            'date_joined',
        ]


def normalize_phone_number(phone: str) -> str:
    """Helper to clean phone numbers and ensure valid format."""
    cleaned = re.sub(r'[\s\-\(\)]', '', phone.strip())
    if not cleaned:
        raise serializers.ValidationError("Phone number cannot be empty.")
    # Allow + or digits only
    if not re.match(r'^\+?[0-9]{7,15}$', cleaned):
        raise serializers.ValidationError(
            "Enter a valid phone number (e.g., +919876543210 or 9876543210 with 7-15 digits)."
        )
    return cleaned


class SendOTPSerializer(serializers.Serializer):
    """Serializer for requesting an OTP to be sent via SMS."""
    phone_number = serializers.CharField(max_length=20, required=True)
    purpose = serializers.ChoiceField(
        choices=VerificationOTP.PURPOSE_CHOICES,
        default='login',
        required=False
    )

    def validate_phone_number(self, value):
        return normalize_phone_number(value)


class VerifyOTPSerializer(serializers.Serializer):
    """Serializer for verifying a received OTP."""
    phone_number = serializers.CharField(max_length=20, required=True)
    otp_code = serializers.CharField(max_length=6, min_length=4, required=True)
    purpose = serializers.ChoiceField(
        choices=VerificationOTP.PURPOSE_CHOICES,
        default='login',
        required=False
    )

    def validate_phone_number(self, value):
        return normalize_phone_number(value)


class GoogleAuthSerializer(serializers.Serializer):
    """Serializer for authenticating via Google ID Token."""
    id_token = serializers.CharField(
        required=True,
        help_text="Google OAuth2 ID Token from client Google SDK"
    )


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer to request an account recovery / password reset OTP."""
    identifier = serializers.CharField(
        required=True,
        help_text="Registered email address or phone number"
    )

    def validate_identifier(self, value):
        val = value.strip()
        if '@' in val:
            return val.lower()
        return normalize_phone_number(val)


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer to verify reset OTP and set new password."""
    identifier = serializers.CharField(required=True)
    otp_code = serializers.CharField(max_length=6, required=True)
    new_password = serializers.CharField(min_length=8, write_only=True, required=True)
    confirm_password = serializers.CharField(min_length=8, write_only=True, required=True)

    def validate_identifier(self, value):
        val = value.strip()
        if '@' in val:
            return val.lower()
        return normalize_phone_number(val)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        # Run Django password validators
        validate_password(attrs['new_password'])
        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for authenticated users to change their password."""
    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(min_length=8, write_only=True, required=True)
    confirm_password = serializers.CharField(min_length=8, write_only=True, required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "New passwords do not match."})
        validate_password(attrs['new_password'])
        return attrs


class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for email/password registration."""
    password = serializers.CharField(min_length=8, write_only=True, required=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'phone_number', 'first_name', 'last_name', 'password']
        extra_kwargs = {
            'email': {'required': True},
        }

    def validate_email(self, value):
        normalized = value.strip().lower()
        if User.objects.filter(email=normalized).exists():
            raise serializers.ValidationError("A user with this email address already exists.")
        return normalized

    def validate_phone_number(self, value):
        if value:
            cleaned = normalize_phone_number(value)
            if User.objects.filter(phone_number=cleaned).exists():
                raise serializers.ValidationError("A user with this phone number already exists.")
            return cleaned
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        return User.objects.create_user(
            auth_provider='email',
            password=password,
            **validated_data
        )


class LoginSerializer(serializers.Serializer):
    """Serializer for email/password login."""
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        email = attrs.get('email', '').strip().lower()
        password = attrs.get('password')

        user = User.objects.filter(email=email).first()
        if not user or not user.check_password(password):
            raise serializers.ValidationError("Invalid email or password.")

        if not user.is_active:
            raise serializers.ValidationError("This account is currently deactivated.")

        attrs['user'] = user
        return attrs


class LogoutSerializer(serializers.Serializer):
    """Serializer to blacklist refresh token on logout."""
    refresh = serializers.CharField(required=True, help_text="Refresh token to invalidate")

import uuid
from datetime import timedelta
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """Custom manager for User model supporting email and phone number identification."""

    def create_user(self, email=None, phone_number=None, password=None, **extra_fields):
        if not email and not phone_number:
            raise ValueError("A user must have either an email address or a phone number.")

        if email:
            email = self.normalize_email(email).lower()

        if phone_number:
            phone_number = phone_number.strip().replace(" ", "").replace("-", "")

        user = self.model(
            email=email,
            phone_number=phone_number,
            **extra_fields
        )

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if not email:
            raise ValueError("Superuser must have an email address.")

        if extra_fields.get('is_staff') is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get('is_superuser') is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email=email, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model for ClinicRise supporting:
    - Mobile OTP Authentication
    - Google OAuth2 Login
    - Email/Password Authentication
    """
    AUTH_PROVIDER_CHOICES = [
        ('email', 'Email & Password'),
        ('phone', 'Mobile OTP'),
        ('google', 'Google Sign-In'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, null=True, blank=True, db_index=True)
    phone_number = models.CharField(max_length=20, unique=True, null=True, blank=True, db_index=True)

    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    avatar_url = models.URLField(max_length=500, blank=True, null=True)

    is_email_verified = models.BooleanField(default=False)
    is_phone_verified = models.BooleanField(default=False)

    auth_provider = models.CharField(max_length=20, choices=AUTH_PROVIDER_CHOICES, default='email')

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']

    def __str__(self):
        if self.phone_number and self.email:
            return f"{self.phone_number} ({self.email})"
        return self.phone_number or self.email or str(self.id)

    @property
    def full_name(self):
        full = f"{self.first_name} {self.last_name}".strip()
        return full or self.email or self.phone_number or "User"

    @full_name.setter
    def full_name(self, value):
        if value:
            parts = str(value).strip().split(maxsplit=1)
            self.first_name = parts[0]
            self.last_name = parts[1] if len(parts) > 1 else ""

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.first_name or self.email or "User"


class VerificationOTP(models.Model):
    """
    Model to store and validate OTPs for:
    - Phone number login/signup
    - Phone verification
    - Password recovery/reset
    """
    PURPOSE_CHOICES = [
        ('login', 'Phone Login / Sign Up'),
        ('verify_phone', 'Verify Phone Number'),
        ('password_reset', 'Password Recovery'),
    ]

    identifier = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Phone number (E.164 format) or Email address"
    )
    otp_code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES, default='login')
    is_used = models.BooleanField(default=False)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        verbose_name = 'Verification OTP'
        verbose_name_plural = 'Verification OTPs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['identifier', 'purpose', 'is_used']),
        ]

    def __str__(self):
        return f"{self.purpose} OTP for {self.identifier} (Expires: {self.expires_at})"

    def is_expired(self):
        return timezone.now() > self.expires_at

    def is_valid(self, code):
        if self.is_used:
            return False, "OTP has already been used."
        if self.is_expired():
            return False, "OTP has expired. Please request a new one."
        if self.attempts >= 5:
            return False, "Too many failed attempts. Please request a new OTP."

        self.attempts += 1
        self.save(update_fields=['attempts'])

        if self.otp_code != str(code).strip():
            return False, "Invalid OTP code."

        self.is_used = True
        self.save(update_fields=['is_used'])
        return True, "OTP verified successfully."

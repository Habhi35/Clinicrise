from rest_framework import serializers
from authentication.models import User
from authentication.serializers import normalize_phone_number
from practices.models import (
    DoctorOnboarding,
    DoctorProfile,
    DoctorSchedule,
    Practice,
    PracticeImage,
    PracticeInvitation,
    PracticeMembership,
    PracticeService,
)


class DoctorProfileSerializer(serializers.ModelSerializer):
    """Serializer for Doctor profiles."""
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_phone = serializers.CharField(source='user.phone_number', read_only=True)
    user_avatar = serializers.CharField(source='user.avatar_url', read_only=True)
    photo_display_url = serializers.CharField(read_only=True)

    class Meta:
        model = DoctorProfile
        fields = [
            'id',
            'user_name',
            'user_email',
            'user_phone',
            'user_avatar',
            'title',
            'gender',
            'medical_license_number',
            'registration_council',
            'registration_year',
            'specialization',
            'qualifications',
            'experience_years',
            'languages_spoken',
            'bio',
            'default_consultation_fee',
            'profile_photo',
            'profile_photo_url',
            'photo_display_url',
            'registration_certificate',
            'registration_certificate_url',
            'is_verified',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'photo_display_url', 'is_verified', 'created_at', 'updated_at']

    def create(self, validated_data):
        user = self.context['request'].user
        if hasattr(user, 'doctor_profile'):
            raise serializers.ValidationError("A doctor profile already exists for this user account.")
        return DoctorProfile.objects.create(user=user, **validated_data)


class PracticeMembershipSerializer(serializers.ModelSerializer):
    """Serializer for displaying membership details in a practice."""
    user_id = serializers.UUIDField(source='user.id', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_phone = serializers.CharField(source='user.phone_number', read_only=True)
    user_avatar = serializers.CharField(source='user.avatar_url', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    doctor_profile = DoctorProfileSerializer(source='user.doctor_profile', read_only=True)

    class Meta:
        model = PracticeMembership
        fields = [
            'id',
            'user_id',
            'user_name',
            'user_email',
            'user_phone',
            'user_avatar',
            'role',
            'role_display',
            'is_active',
            'joined_at',
            'doctor_profile',
        ]
        read_only_fields = ['id', 'user_id', 'joined_at', 'role_display']


class PracticeSerializer(serializers.ModelSerializer):
    """Serializer for Practice / Clinic tenant."""
    owner_name = serializers.CharField(source='owner.full_name', read_only=True)
    owner_email = serializers.CharField(source='owner.email', read_only=True)
    clinic_type_display = serializers.CharField(source='get_clinic_type_display', read_only=True)
    logo_display_url = serializers.CharField(read_only=True)
    members_count = serializers.SerializerMethodField()
    current_user_role = serializers.SerializerMethodField()

    class Meta:
        model = Practice
        fields = [
            'id',
            'name',
            'slug',
            'owner_name',
            'owner_email',
            'clinic_type',
            'clinic_type_display',
            'tagline',
            'about',
            'phone_number',
            'email',
            'website',
            'logo_url',
            'logo_image',
            'logo_display_url',
            'address',
            'landmark',
            'city',
            'state',
            'postal_code',
            'country',
            'gst_number',
            'established_year',
            'currency',
            'timezone',
            'is_active',
            'members_count',
            'current_user_role',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'slug', 'clinic_type_display', 'logo_display_url', 'is_active', 'created_at', 'updated_at']

    def get_members_count(self, obj):
        return obj.memberships.filter(is_active=True).count()

    def get_current_user_role(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        membership = obj.memberships.filter(user=request.user, is_active=True).first()
        return membership.role if membership else None

    def create(self, validated_data):
        user = self.context['request'].user
        practice = Practice.objects.create(owner=user, **validated_data)
        PracticeMembership.objects.create(
            practice=practice,
            user=user,
            role=PracticeMembership.ROLE_OWNER
        )
        return practice


class PracticeServiceSerializer(serializers.ModelSerializer):
    """Serializer for Practice clinical services."""
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    doctor_name = serializers.CharField(source='doctor.user.full_name', read_only=True)

    class Meta:
        model = PracticeService
        fields = [
            'id',
            'practice',
            'doctor',
            'doctor_name',
            'name',
            'category',
            'category_display',
            'description',
            'duration_minutes',
            'price',
            'is_active',
            'is_teleconsultation',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'practice', 'category_display', 'doctor_name', 'created_at', 'updated_at']


class DoctorScheduleSerializer(serializers.ModelSerializer):
    """Serializer for Doctor consultation timings and schedules."""
    day_of_week_display = serializers.CharField(source='get_day_of_week_display', read_only=True)
    doctor_name = serializers.CharField(source='doctor.user.full_name', read_only=True)

    class Meta:
        model = DoctorSchedule
        fields = [
            'id',
            'practice',
            'doctor',
            'doctor_name',
            'day_of_week',
            'day_of_week_display',
            'session_name',
            'start_time',
            'end_time',
            'slot_duration_minutes',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'practice', 'day_of_week_display', 'doctor_name', 'created_at', 'updated_at']


class PracticeImageSerializer(serializers.ModelSerializer):
    """Serializer for Clinic and Practice photos."""
    image_type_display = serializers.CharField(source='get_image_type_display', read_only=True)

    class Meta:
        model = PracticeImage
        fields = [
            'id',
            'practice',
            'image',
            'image_url',
            'image_type',
            'image_type_display',
            'caption',
            'is_primary',
            'order',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'practice', 'image_type_display', 'created_at', 'updated_at']


class DoctorOnboardingSerializer(serializers.ModelSerializer):
    """Serializer for Doctor Onboarding state & saved progress."""
    progress_percentage = serializers.IntegerField(read_only=True)
    current_step_display = serializers.CharField(source='get_current_step_display', read_only=True)
    practice_name = serializers.CharField(source='practice.name', read_only=True)

    class Meta:
        model = DoctorOnboarding
        fields = [
            'id',
            'user',
            'practice',
            'practice_name',
            'current_step',
            'current_step_display',
            'completed_steps',
            'draft_data',
            'is_completed',
            'completed_at',
            'progress_percentage',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'user',
            'practice_name',
            'current_step_display',
            'progress_percentage',
            'created_at',
            'updated_at',
        ]


# Step-specific input serializers

class DoctorProfileStepSerializer(serializers.Serializer):
    """Input serializer for Onboarding Step 1: Doctor Profile & Registration."""
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    title = serializers.CharField(max_length=20, default='Dr.', required=False)
    gender = serializers.ChoiceField(
        choices=DoctorProfile.GENDER_CHOICES,
        default=DoctorProfile.GENDER_UNSPECIFIED,
        required=False
    )
    medical_license_number = serializers.CharField(
        max_length=100,
        required=True,
        help_text="Registration number with State Medical Council or National Authority"
    )
    registration_council = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        help_text="e.g. Maharashtra Medical Council, Delhi Medical Council"
    )
    registration_year = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1950,
        max_value=2050
    )
    specialization = serializers.CharField(
        max_length=150,
        required=True,
        help_text="e.g. General Physician, Dentist, Cardiologist, Pediatrician"
    )
    qualifications = serializers.CharField(
        max_length=255,
        required=True,
        help_text="e.g. MBBS, MD, BDS, MDS, MS"
    )
    experience_years = serializers.IntegerField(
        required=False,
        default=0,
        min_value=0,
        max_value=70
    )
    languages_spoken = serializers.CharField(
        max_length=255,
        required=False,
        default='English'
    )
    bio = serializers.CharField(
        required=False,
        allow_blank=True
    )
    default_consultation_fee = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        required=False
    )
    profile_photo_url = serializers.URLField(
        max_length=500,
        required=False,
        allow_blank=True,
        allow_null=True
    )
    registration_certificate_url = serializers.URLField(
        max_length=500,
        required=False,
        allow_blank=True,
        allow_null=True
    )


class ClinicDetailsStepSerializer(serializers.Serializer):
    """Input serializer for Onboarding Step 2: Clinic & Practice Details."""
    name = serializers.CharField(max_length=255, required=True, help_text="Clinic Name")
    clinic_type = serializers.ChoiceField(
        choices=Practice.CLINIC_TYPE_CHOICES,
        default=Practice.CLINIC_TYPE_SOLO,
        required=False
    )
    tagline = serializers.CharField(max_length=255, required=False, allow_blank=True)
    about = serializers.CharField(required=False, allow_blank=True)
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    website = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    logo_url = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    address = serializers.CharField(required=False, allow_blank=True)
    landmark = serializers.CharField(max_length=255, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    state = serializers.CharField(max_length=100, required=False, allow_blank=True)
    postal_code = serializers.CharField(max_length=20, required=False, allow_blank=True)
    country = serializers.CharField(max_length=100, default='India', required=False)
    gst_number = serializers.CharField(max_length=30, required=False, allow_blank=True)
    established_year = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1800,
        max_value=2050
    )
    currency = serializers.CharField(max_length=10, default='INR', required=False)
    timezone = serializers.CharField(max_length=50, default='Asia/Kolkata', required=False)


class ServiceItemSerializer(serializers.Serializer):
    """Individual service item serializer."""
    name = serializers.CharField(max_length=255, required=True)
    category = serializers.ChoiceField(
        choices=PracticeService.CATEGORY_CHOICES,
        default=PracticeService.CATEGORY_CONSULTATION,
        required=False
    )
    description = serializers.CharField(required=False, allow_blank=True)
    duration_minutes = serializers.IntegerField(default=15, min_value=5, max_value=240, required=False)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, default=0.00, required=False)
    is_teleconsultation = serializers.BooleanField(default=False, required=False)
    is_active = serializers.BooleanField(default=True, required=False)


class ServicesStepSerializer(serializers.Serializer):
    """Input serializer for Onboarding Step 3: Clinical Services."""
    services = serializers.ListField(
        child=ServiceItemSerializer(),
        allow_empty=False,
        help_text="List of clinical services offered by doctor/clinic"
    )


class TimingItemSerializer(serializers.Serializer):
    """Individual schedule / shift item serializer."""
    day_of_week = serializers.ChoiceField(
        choices=DoctorSchedule.DAY_CHOICES,
        required=True
    )
    session_name = serializers.CharField(max_length=100, default='General OPD', required=False)
    start_time = serializers.TimeField(format='%H:%M', input_formats=['%H:%M', '%H:%M:%S'], required=True)
    end_time = serializers.TimeField(format='%H:%M', input_formats=['%H:%M', '%H:%M:%S'], required=True)
    slot_duration_minutes = serializers.IntegerField(default=15, min_value=5, max_value=120, required=False)
    is_active = serializers.BooleanField(default=True, required=False)

    def validate(self, attrs):
        if attrs['start_time'] >= attrs['end_time']:
            raise serializers.ValidationError("start_time must be strictly earlier than end_time.")
        return attrs


class TimingsStepSerializer(serializers.Serializer):
    """Input serializer for Onboarding Step 4: Clinic Timings & Schedule."""
    timings = serializers.ListField(
        child=TimingItemSerializer(),
        allow_empty=False,
        help_text="Weekly timings and consultation shifts"
    )


class ImageItemSerializer(serializers.Serializer):
    """Individual image item serializer."""
    image_url = serializers.URLField(max_length=500, required=True)
    image_type = serializers.ChoiceField(
        choices=PracticeImage.IMAGE_TYPE_CHOICES,
        default=PracticeImage.IMAGE_TYPE_OTHER,
        required=False
    )
    caption = serializers.CharField(max_length=255, required=False, allow_blank=True)
    is_primary = serializers.BooleanField(default=False, required=False)
    order = serializers.IntegerField(default=0, required=False)


class ImagesStepSerializer(serializers.Serializer):
    """Input serializer for Onboarding Step 5: Clinic Images."""
    images = serializers.ListField(
        child=ImageItemSerializer(),
        required=False,
        default=list
    )
    doctor_avatar_url = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    registration_certificate_url = serializers.URLField(required=False, allow_blank=True, allow_null=True)


class SaveDraftSerializer(serializers.Serializer):
    """Serializer for saving in-progress onboarding drafts."""
    step = serializers.ChoiceField(
        choices=[
            (DoctorOnboarding.STEP_DOCTOR_PROFILE, 'Doctor Profile'),
            (DoctorOnboarding.STEP_CLINIC_DETAILS, 'Clinic Details'),
            (DoctorOnboarding.STEP_SERVICES, 'Services'),
            (DoctorOnboarding.STEP_TIMINGS, 'Timings'),
            (DoctorOnboarding.STEP_IMAGES, 'Images'),
            (DoctorOnboarding.STEP_REVIEW, 'Review'),
        ],
        required=True
    )
    data = serializers.DictField(required=True)


class InviteMemberSerializer(serializers.Serializer):
    """Serializer to invite a doctor or staff member to a practice."""
    identifier = serializers.CharField(
        required=True,
        help_text="Email or Phone Number of the person being invited"
    )
    role = serializers.ChoiceField(
        choices=[
            (PracticeMembership.ROLE_ADMIN, 'Practice Admin'),
            (PracticeMembership.ROLE_DOCTOR, 'Doctor / Practitioner'),
            (PracticeMembership.ROLE_RECEPTIONIST, 'Frontdesk / Receptionist'),
            (PracticeMembership.ROLE_ASSISTANT, 'Clinical Assistant / Nurse'),
            (PracticeMembership.ROLE_STAFF, 'General Staff'),
        ],
        default=PracticeMembership.ROLE_DOCTOR
    )

    def validate_identifier(self, value):
        val = value.strip()
        if '@' in val:
            return val.lower()
        return normalize_phone_number(val)


class UpdateMemberSerializer(serializers.ModelSerializer):
    """Serializer for updating a member's role or active status."""
    class Meta:
        model = PracticeMembership
        fields = ['role', 'is_active']

    def validate_role(self, value):
        if value == PracticeMembership.ROLE_OWNER:
            raise serializers.ValidationError(
                "Ownership cannot be reassigned via this endpoint. Use practice ownership transfer."
            )
        return value


class PracticeInvitationSerializer(serializers.ModelSerializer):
    """Serializer for viewing practice invitations."""
    practice_name = serializers.CharField(source='practice.name', read_only=True)
    invited_by_name = serializers.CharField(source='invited_by.full_name', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = PracticeInvitation
        fields = [
            'id',
            'practice_name',
            'email',
            'phone_number',
            'role',
            'role_display',
            'invite_code',
            'status',
            'invited_by_name',
            'created_at',
            'expires_at',
        ]
        read_only_fields = ['id', 'invite_code', 'status', 'created_at', 'expires_at']

from rest_framework import serializers
from practices.models import DoctorProfile, PracticeService
from bookings.models import (
    BookingRequest,
    BookingTimeline,
    DoctorSessionCapacity,
    PracticeLocation,
)


class PracticeLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PracticeLocation
        fields = [
            'id',
            'name',
            'code',
            'address',
            'landmark',
            'city',
            'state',
            'postal_code',
            'country',
            'phone_number',
            'email',
            'google_maps_url',
            'is_telehealth_default',
            'is_primary',
            'is_active',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class DoctorSessionCapacitySerializer(serializers.ModelSerializer):
    doctor_name = serializers.SerializerMethodField()
    location_name = serializers.SerializerMethodField()
    booking_mode_display = serializers.CharField(source='get_booking_mode_display', read_only=True)

    class Meta:
        model = DoctorSessionCapacity
        fields = [
            'id',
            'doctor',
            'doctor_name',
            'location',
            'location_name',
            'session_name',
            'booking_mode',
            'booking_mode_display',
            'max_tokens_per_session',
            'slot_duration_minutes',
            'auto_confirm',
        ]
        read_only_fields = ['id']

    def get_doctor_name(self, obj):
        return getattr(obj.doctor.user, 'full_name', str(obj.doctor.user))

    def get_location_name(self, obj):
        return obj.location.name if obj.location else "All Locations"


class BookingTimelineSerializer(serializers.ModelSerializer):
    performed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = BookingTimeline
        fields = [
            'id',
            'action',
            'performed_by',
            'performed_by_name',
            'note',
            'metadata',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_performed_by_name(self, obj):
        if not obj.performed_by:
            return "System / Patient"
        return getattr(obj.performed_by, 'full_name', str(obj.performed_by))


class BookingRequestSerializer(serializers.ModelSerializer):
    """List serializer for booking management."""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    consultation_mode_display = serializers.CharField(source='get_consultation_mode_display', read_only=True)
    booking_mode_display = serializers.CharField(source='get_booking_mode_display', read_only=True)
    preferred_time_window_display = serializers.CharField(source='get_preferred_time_window_display', read_only=True)
    location_name = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    service_name = serializers.SerializerMethodField()

    class Meta:
        model = BookingRequest
        fields = [
            'id',
            'booking_reference',
            'patient_name',
            'phone_number',
            'email',
            'location',
            'location_name',
            'doctor',
            'doctor_name',
            'service',
            'service_name',
            'consultation_mode',
            'consultation_mode_display',
            'preferred_date',
            'preferred_time_window',
            'preferred_time_window_display',
            'chief_complaint',
            'patient_notes',
            'booking_mode',
            'booking_mode_display',
            'appointment_date',
            'session_name',
            'token_number',
            'start_time',
            'end_time',
            'status',
            'status_display',
            'confirmed_at',
            'source',
            'created_at',
        ]
        read_only_fields = ['id', 'booking_reference', 'created_at', 'status_display']

    def get_location_name(self, obj):
        return obj.location.name if obj.location else None

    def get_doctor_name(self, obj):
        if not obj.doctor:
            return None
        return getattr(obj.doctor.user, 'full_name', str(obj.doctor.user))

    def get_service_name(self, obj):
        return obj.service.name if obj.service else None


class BookingRequestDetailSerializer(BookingRequestSerializer):
    """Detailed booking serializer with audit timeline and clinical details."""
    timeline = BookingTimelineSerializer(many=True, read_only=True)
    confirmed_by_name = serializers.SerializerMethodField()

    class Meta(BookingRequestSerializer.Meta):
        fields = BookingRequestSerializer.Meta.fields + [
            'gender',
            'age',
            'date_of_birth',
            'patient_type',
            'clinic_notes',
            'rejection_reason',
            'cancellation_reason',
            'cancelled_at',
            'confirmed_by',
            'confirmed_by_name',
            'consent_given',
            'consent_timestamp',
            'timeline',
            'lead',
        ]

    def get_confirmed_by_name(self, obj):
        if not obj.confirmed_by:
            return None
        return getattr(obj.confirmed_by, 'full_name', str(obj.confirmed_by))


class PublicBookingRequestSerializer(serializers.Serializer):
    """Validates public appointment booking request submitted by patient."""
    patient_name = serializers.CharField(max_length=200, required=True)
    phone_number = serializers.CharField(max_length=30, required=True)
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    gender = serializers.ChoiceField(
        choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')],
        required=False,
        allow_blank=True,
        default=""
    )
    age = serializers.IntegerField(required=False, allow_null=True, default=None)
    date_of_birth = serializers.DateField(required=False, allow_null=True, default=None)
    location_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    doctor_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    service_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    consultation_mode = serializers.ChoiceField(
        choices=BookingRequest.CONSULTATION_MODE_CHOICES,
        default=BookingRequest.MODE_IN_PERSON
    )
    preferred_date = serializers.DateField(required=True)
    preferred_time_window = serializers.ChoiceField(
        choices=BookingRequest.TIME_WINDOW_CHOICES,
        default=BookingRequest.WINDOW_ANY
    )
    booking_mode = serializers.ChoiceField(
        choices=BookingRequest.SCHEDULING_MODE_CHOICES,
        required=False,
        default=BookingRequest.SCHEDULING_MODE_SLOT
    )
    session_name = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    start_time = serializers.TimeField(required=False, allow_null=True, default=None)
    chief_complaint = serializers.CharField(required=False, allow_blank=True, default="")
    patient_notes = serializers.CharField(required=False, allow_blank=True, default="")
    consent_given = serializers.BooleanField(default=True)

    def validate_phone_number(self, value):
        cleaned = value.strip()
        if len(cleaned) < 6:
            raise serializers.ValidationError("Valid phone number is required.")
        return cleaned


class BookingConfirmSerializer(serializers.Serializer):
    """Payload for clinic staff confirming a booking request."""
    confirmed_date = serializers.DateField(required=False, allow_null=True, default=None)
    start_time = serializers.TimeField(required=False, allow_null=True, default=None)
    end_time = serializers.TimeField(required=False, allow_null=True, default=None)
    session_name = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    token_number = serializers.IntegerField(required=False, allow_null=True, default=None)
    clinic_notes = serializers.CharField(required=False, allow_blank=True, default="")


class BookingRescheduleSerializer(serializers.Serializer):
    """Payload for rescheduling an appointment."""
    new_date = serializers.DateField(required=True)
    new_start_time = serializers.TimeField(required=False, allow_null=True, default=None)
    new_end_time = serializers.TimeField(required=False, allow_null=True, default=None)
    new_session = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class BookingActionReasonSerializer(serializers.Serializer):
    """Payload for cancelling or declining a booking."""
    reason = serializers.CharField(required=True)

from rest_framework import serializers
from patients.models import (
    Patient,
    PatientFollowUp,
    PatientNote,
    PatientTimeline,
    PatientVitals,
    normalize_patient_phone,
)


class PatientNoteSerializer(serializers.ModelSerializer):
    """Serializer for patient notes (frontdesk, assistant prep, doctor notes, follow-up logs)."""
    author_name = serializers.CharField(source='author.full_name', read_only=True)
    pinned_by_name = serializers.CharField(source='pinned_by.full_name', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = PatientNote
        fields = [
            'id',
            'patient',
            'author',
            'author_name',
            'author_role',
            'category',
            'category_display',
            'note',
            'is_pinned',
            'pinned_at',
            'pinned_by',
            'pinned_by_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'patient', 'author', 'author_name', 'author_role', 'category_display', 'pinned_at', 'pinned_by', 'pinned_by_name', 'created_at', 'updated_at']


class PatientVitalsSerializer(serializers.ModelSerializer):
    """Serializer for clinical vitals recorded by assistants or nurses."""
    recorded_by_name = serializers.CharField(source='recorded_by.full_name', read_only=True)

    class Meta:
        model = PatientVitals
        fields = [
            'id',
            'patient',
            'recorded_by',
            'recorded_by_name',
            'booking',
            'blood_pressure_systolic',
            'blood_pressure_diastolic',
            'pulse_bpm',
            'temperature_fahrenheit',
            'oxygen_saturation_spo2',
            'respiratory_rate',
            'weight_kg',
            'height_cm',
            'bmi',
            'blood_sugar_fasting',
            'blood_sugar_random',
            'notes',
            'created_at',
        ]
        read_only_fields = ['id', 'patient', 'recorded_by', 'recorded_by_name', 'bmi', 'created_at']


class PatientFollowUpSerializer(serializers.ModelSerializer):
    """Serializer for scheduled follow-up tasks and recalls."""
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    patient_phone = serializers.CharField(source='patient.phone_number', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.full_name', read_only=True)
    completed_by_name = serializers.CharField(source='completed_by.full_name', read_only=True)
    follow_up_type_display = serializers.CharField(source='get_follow_up_type_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = PatientFollowUp
        fields = [
            'id',
            'patient',
            'patient_name',
            'patient_phone',
            'booking',
            'created_by',
            'created_by_name',
            'assigned_to',
            'assigned_to_name',
            'follow_up_type',
            'follow_up_type_display',
            'priority',
            'priority_display',
            'due_date',
            'status',
            'status_display',
            'title',
            'instructions',
            'outcome_notes',
            'completed_at',
            'completed_by',
            'completed_by_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'patient_name',
            'patient_phone',
            'created_by',
            'created_by_name',
            'assigned_to_name',
            'completed_by',
            'completed_by_name',
            'follow_up_type_display',
            'priority_display',
            'status_display',
            'completed_at',
            'created_at',
            'updated_at',
        ]


class PatientTimelineSerializer(serializers.ModelSerializer):
    """Serializer for chronological patient timeline events."""
    performed_by_name = serializers.CharField(source='performed_by.full_name', read_only=True)
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)

    class Meta:
        model = PatientTimeline
        fields = [
            'id',
            'patient',
            'performed_by',
            'performed_by_name',
            'performer_role',
            'event_type',
            'event_type_display',
            'title',
            'description',
            'metadata',
            'created_at',
        ]
        read_only_fields = ['id', 'patient', 'performed_by_name', 'event_type_display', 'created_at']


class PatientListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for patient search and table listings."""
    full_name = serializers.CharField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    gender_display = serializers.CharField(source='get_gender_display', read_only=True)
    has_allergies = serializers.SerializerMethodField()
    has_medical_alerts = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = [
            'id',
            'patient_id',
            'first_name',
            'last_name',
            'full_name',
            'phone_number',
            'email',
            'gender',
            'gender_display',
            'age',
            'date_of_birth',
            'blood_group',
            'status',
            'status_display',
            'allergies',
            'has_allergies',
            'medical_alerts',
            'has_medical_alerts',
            'tags',
            'total_visits_count',
            'last_visit_date',
            'created_at',
        ]
        read_only_fields = ['id', 'patient_id', 'full_name', 'status_display', 'gender_display', 'created_at']

    def get_has_allergies(self, obj) -> bool:
        return bool(obj.allergies and obj.allergies.strip())

    def get_has_medical_alerts(self, obj) -> bool:
        return bool(obj.medical_alerts and obj.medical_alerts.strip())


class PatientDetailSerializer(serializers.ModelSerializer):
    """Comprehensive clinical chart serializer with pinned alerts, latest vitals, and stats."""
    full_name = serializers.CharField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    gender_display = serializers.CharField(source='get_gender_display', read_only=True)
    source_display = serializers.CharField(source='get_source_display', read_only=True)
    primary_doctor_name = serializers.CharField(source='primary_doctor.user.full_name', read_only=True)

    pinned_notes = serializers.SerializerMethodField()
    latest_vitals = serializers.SerializerMethodField()
    pending_followups_count = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = [
            'id',
            'patient_id',
            'first_name',
            'last_name',
            'full_name',
            'phone_number',
            'email',
            'gender',
            'gender_display',
            'date_of_birth',
            'age',
            'blood_group',
            'address',
            'city',
            'postal_code',
            'emergency_contact_name',
            'emergency_contact_phone',
            'emergency_contact_relation',
            'allergies',
            'chronic_conditions',
            'medical_alerts',
            'tags',
            'status',
            'status_display',
            'source',
            'source_display',
            'primary_doctor',
            'primary_doctor_name',
            'total_visits_count',
            'last_visit_date',
            'preferred_language',
            'whatsapp_opt_in',
            'sms_opt_in',
            'call_opt_in',
            'email_opt_in',
            'pinned_notes',
            'latest_vitals',
            'pending_followups_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'patient_id', 'full_name', 'status_display', 'gender_display', 'source_display', 'created_at', 'updated_at']

    def get_pinned_notes(self, obj):
        pinned = obj.notes.filter(is_pinned=True).order_by('-pinned_at')
        return PatientNoteSerializer(pinned, many=True).data

    def get_latest_vitals(self, obj):
        latest = obj.vitals.first()
        return PatientVitalsSerializer(latest).data if latest else None

    def get_pending_followups_count(self, obj) -> int:
        return obj.follow_ups.filter(status__in=[PatientFollowUp.STATUS_PENDING, PatientFollowUp.STATUS_IN_PROGRESS]).count()


class PatientCreateUpdateSerializer(serializers.ModelSerializer):
    """Input serializer for registering or editing patient records."""
    class Meta:
        model = Patient
        fields = [
            'first_name',
            'last_name',
            'phone_number',
            'email',
            'gender',
            'date_of_birth',
            'age',
            'blood_group',
            'address',
            'city',
            'postal_code',
            'emergency_contact_name',
            'emergency_contact_phone',
            'emergency_contact_relation',
            'allergies',
            'chronic_conditions',
            'medical_alerts',
            'tags',
            'source',
            'status',
            'primary_doctor',
            'preferred_language',
            'whatsapp_opt_in',
            'sms_opt_in',
            'call_opt_in',
            'email_opt_in',
        ]

    def validate_phone_number(self, value):
        val = normalize_patient_phone(value)
        if len(val) < 10:
            raise serializers.ValidationError("Please provide a valid phone number with at least 10 digits.")
        return val


class LogCallSerializer(serializers.Serializer):
    """Input serializer for receptionists logging patient phone calls."""
    call_type = serializers.ChoiceField(
        choices=[('outgoing', 'Outgoing Call'), ('incoming', 'Incoming Call'), ('missed', 'Missed Call')],
        default='outgoing'
    )
    outcome = serializers.ChoiceField(
        choices=[
            ('answered', 'Call Answered / Spoke to Patient'),
            ('no_answer', 'No Answer / Unreachable'),
            ('busy', 'Busy / Line Engaged'),
            ('callback_requested', 'Patient Requested Callback'),
            ('wrong_number', 'Wrong Number'),
        ],
        default='answered'
    )
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class CompleteFollowUpSerializer(serializers.Serializer):
    """Input serializer when receptionist or assistant completes a follow-up task."""
    outcome_notes = serializers.CharField(required=True, allow_blank=False, help_text="Clinical or administrative notes on follow-up outcome")

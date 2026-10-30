from rest_framework import serializers
from authentication.models import User
from leads.models import Lead, LeadActivity, ClickEvent


class LeadActivitySerializer(serializers.ModelSerializer):
    performed_by_name = serializers.SerializerMethodField()
    activity_type_display = serializers.CharField(source='get_activity_type_display', read_only=True)

    class Meta:
        model = LeadActivity
        fields = [
            'id',
            'activity_type',
            'activity_type_display',
            'performed_by',
            'performed_by_name',
            'previous_status',
            'new_status',
            'note',
            'metadata',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_performed_by_name(self, obj):
        if not obj.performed_by:
            return "System / Public"
        return getattr(obj.performed_by, 'full_name', str(obj.performed_by))


class ClickEventSerializer(serializers.ModelSerializer):
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)

    class Meta:
        model = ClickEvent
        fields = [
            'id',
            'event_type',
            'event_type_display',
            'target_phone',
            'doctor_id',
            'doctor_name',
            'service_name',
            'page_url',
            'referrer',
            'utm_source',
            'utm_medium',
            'utm_campaign',
            'device_type',
            'visitor_id',
            'ip_address',
            'lead',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class LeadSerializer(serializers.ModelSerializer):
    """
    Serializer for listing leads in the inbox with key summary fields,
    badges, and counters.
    """
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    source_display = serializers.CharField(source='get_source_display', read_only=True)
    assigned_to_name = serializers.SerializerMethodField()
    activities_count = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = [
            'id',
            'patient_name',
            'phone_number',
            'email',
            'preferred_date',
            'preferred_time_slot',
            'service_requested',
            'doctor_requested',
            'message',
            'status',
            'status_display',
            'priority',
            'priority_display',
            'source',
            'source_display',
            'is_read',
            'assigned_to',
            'assigned_to_name',
            'last_contacted_at',
            'follow_up_date',
            'activities_count',
            'consent_given',
            'whatsapp_opt_in',
            'call_opt_in',
            'sms_opt_in',
            'email_opt_in',
            'consent_withdrawn',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_assigned_to_name(self, obj):
        if not obj.assigned_to:
            return None
        return obj.assigned_to.get_full_name() or obj.assigned_to.email

    def get_activities_count(self, obj):
        return obj.activities.count()


class LeadDetailSerializer(LeadSerializer):
    """
    Detailed serializer for a single Lead, including full consent history,
    marketing attribution, and embedded timeline activities.
    """
    activities = LeadActivitySerializer(many=True, read_only=True)
    click_events = ClickEventSerializer(many=True, read_only=True)

    class Meta(LeadSerializer.Meta):
        fields = LeadSerializer.Meta.fields + [
            'source_url',
            'referrer',
            'utm_source',
            'utm_medium',
            'utm_campaign',
            'utm_term',
            'utm_content',
            'device_type',
            'ip_address',
            'user_agent',
            'consent_text',
            'consent_timestamp',
            'consent_ip_address',
            'consent_withdrawn_at',
            'consent_withdrawn_reason',
            'lost_reason',
            'activities',
            'click_events',
        ]


class LeadCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for frontdesk / clinic staff to manually log leads.
    """
    class Meta:
        model = Lead
        fields = [
            'patient_name',
            'phone_number',
            'email',
            'preferred_date',
            'preferred_time_slot',
            'service_requested',
            'doctor_requested',
            'message',
            'priority',
            'assigned_to',
            'follow_up_date',
            'source',
            'consent_given',
            'whatsapp_opt_in',
            'call_opt_in',
            'sms_opt_in',
            'email_opt_in',
        ]

    def validate_phone_number(self, value):
        cleaned = value.strip()
        if len(cleaned) < 6:
            raise serializers.ValidationError("Please provide a valid phone number.")
        return cleaned


class PublicEnquirySerializer(serializers.Serializer):
    """
    Public website/landing page lead intake serializer.
    Captures patient inquiry and explicit consent.
    """
    patient_name = serializers.CharField(max_length=200, required=True)
    phone_number = serializers.CharField(max_length=30, required=True)
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    preferred_date = serializers.DateField(required=False, allow_null=True, default=None)
    preferred_time_slot = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    service_requested = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    doctor_requested = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    message = serializers.CharField(required=False, allow_blank=True, default="")

    # Consent fields
    consent_given = serializers.BooleanField(default=True)
    consent_text = serializers.CharField(required=False, allow_blank=True, default="")
    whatsapp_opt_in = serializers.BooleanField(default=True)
    call_opt_in = serializers.BooleanField(default=True)
    sms_opt_in = serializers.BooleanField(default=True)
    email_opt_in = serializers.BooleanField(default=True)

    # Attribution
    source_url = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    referrer = serializers.CharField(required=False, allow_blank=True, default="")
    utm_source = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    utm_medium = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    utm_campaign = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    utm_term = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    utm_content = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    device_type = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")

    def validate_phone_number(self, value):
        cleaned = value.strip()
        if len(cleaned) < 6:
            raise serializers.ValidationError("Please provide a valid contact number.")
        return cleaned


class PublicClickEventSerializer(serializers.Serializer):
    """
    Public serializer for recording Call & WhatsApp button clicks.
    """
    event_type = serializers.ChoiceField(choices=ClickEvent.EVENT_CHOICES)
    target_phone = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    doctor_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    doctor_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    service_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    page_url = serializers.CharField(required=False, allow_blank=True, default="")
    referrer = serializers.CharField(required=False, allow_blank=True, default="")
    utm_source = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    utm_medium = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    utm_campaign = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    visitor_id = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    device_type = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")

    # Optional visitor contact conversion (e.g. quick callback before opening WhatsApp/Call)
    patient_name = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    phone_number = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")
    consent_given = serializers.BooleanField(default=True)


class LeadStatusUpdateSerializer(serializers.Serializer):
    """
    Validates status transition with optional activity note,
    follow-up scheduling, and lost reason.
    """
    status = serializers.ChoiceField(choices=Lead.STATUS_CHOICES)
    note = serializers.CharField(required=False, allow_blank=True, default="")
    follow_up_date = serializers.DateTimeField(required=False, allow_null=True, default=None)
    lost_reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class LeadActivityCreateSerializer(serializers.Serializer):
    """
    Adds a note, logs a call or WhatsApp message in the lead's timeline.
    """
    activity_type = serializers.ChoiceField(
        choices=[
            (LeadActivity.TYPE_NOTE, 'Internal Note Added'),
            (LeadActivity.TYPE_CALL, 'Phone Call Logged'),
            (LeadActivity.TYPE_WHATSAPP, 'WhatsApp Message Sent'),
            (LeadActivity.TYPE_EMAIL, 'Email Sent'),
        ],
        default=LeadActivity.TYPE_NOTE
    )
    note = serializers.CharField(required=True)
    metadata = serializers.DictField(required=False, default=dict)


class LeadConsentUpdateSerializer(serializers.Serializer):
    """
    Updates patient communication opt-ins or records consent revocation.
    """
    consent_withdrawn = serializers.BooleanField(required=False, default=False)
    consent_withdrawn_reason = serializers.CharField(required=False, allow_blank=True, default="")
    whatsapp_opt_in = serializers.BooleanField(required=False)
    call_opt_in = serializers.BooleanField(required=False)
    sms_opt_in = serializers.BooleanField(required=False)
    email_opt_in = serializers.BooleanField(required=False)


class PublicConsentOptOutSerializer(serializers.Serializer):
    """
    Public opt-out request by phone number.
    """
    phone_number = serializers.CharField(max_length=30, required=True)
    reason = serializers.CharField(required=False, allow_blank=True, default="")

from rest_framework import serializers
from whatsapp.models import (
    WhatsAppConfig,
    WhatsAppTemplate,
    WhatsAppOptOut,
    WhatsAppReminder,
    WhatsAppMessageLog,
    normalize_phone_number
)


class WhatsAppConfigSerializer(serializers.ModelSerializer):
    """Configuration settings serializer with masked credentials."""
    masked_access_token = serializers.SerializerMethodField()

    class Meta:
        model = WhatsAppConfig
        fields = [
            'id',
            'provider',
            'phone_number_id',
            'waba_id',
            'access_token',
            'masked_access_token',
            'webhook_verify_token',
            'display_phone_number',
            'business_name',
            'is_enabled',
            'auto_confirmation_enabled',
            'auto_reminders_enabled',
            'lead_auto_reply_enabled',
            'post_visit_review_enabled',
            'daily_send_limit',
            'created_at',
            'updated_at',
        ]
        extra_kwargs = {
            'access_token': {'write_only': True, 'required': False}
        }

    def get_masked_access_token(self, obj):
        if not obj.access_token:
            return ""
        return f"{obj.access_token[:6]}••••••••{obj.access_token[-4:]}" if len(obj.access_token) > 10 else "••••••••"


class WhatsAppTemplateSerializer(serializers.ModelSerializer):
    """Template serializer for Meta WhatsApp templates."""
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    meta_status_display = serializers.CharField(source='get_meta_status_display', read_only=True)

    class Meta:
        model = WhatsAppTemplate
        fields = [
            'id',
            'template_name',
            'title',
            'category',
            'category_display',
            'language',
            'header_type',
            'header_text',
            'body_text',
            'footer_text',
            'buttons',
            'variable_mapping',
            'meta_template_id',
            'meta_status',
            'meta_status_display',
            'is_active',
            'is_system_default',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'is_system_default', 'created_at', 'updated_at']


class WhatsAppOptOutSerializer(serializers.ModelSerializer):
    """Opt-out registry serializer."""
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    source_channel_display = serializers.CharField(source='get_source_channel_display', read_only=True)

    class Meta:
        model = WhatsAppOptOut
        fields = [
            'id',
            'phone_number',
            'patient_name',
            'reason',
            'reason_display',
            'reason_notes',
            'is_opted_out',
            'opted_out_at',
            'opted_in_at',
            'source_channel',
            'source_channel_display',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'opted_out_at', 'opted_in_at', 'created_at', 'updated_at']

    def validate_phone_number(self, value):
        norm = normalize_phone_number(value)
        if not norm or len(norm) < 10:
            raise serializers.ValidationError("Please provide a valid E.164 phone number.")
        return norm


class WhatsAppReminderSerializer(serializers.ModelSerializer):
    """Scheduled reminders serializer."""
    reminder_type_display = serializers.CharField(source='get_reminder_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    booking_reference = serializers.CharField(source='booking.booking_reference', read_only=True, default=None)
    patient_name = serializers.SerializerMethodField()
    recipient_phone = serializers.SerializerMethodField()

    class Meta:
        model = WhatsAppReminder
        fields = [
            'id',
            'booking',
            'booking_reference',
            'lead',
            'patient_name',
            'recipient_phone',
            'reminder_type',
            'reminder_type_display',
            'scheduled_for',
            'status',
            'status_display',
            'sent_at',
            'error_message',
            'created_at',
        ]
        read_only_fields = ['id', 'status', 'sent_at', 'created_at']

    def get_patient_name(self, obj):
        if obj.booking:
            return obj.booking.patient_name
        if obj.lead:
            return obj.lead.patient_name
        return ""

    def get_recipient_phone(self, obj):
        if obj.booking:
            return obj.booking.phone_number
        if obj.lead:
            return obj.lead.phone_number
        return ""


class WhatsAppMessageLogSerializer(serializers.ModelSerializer):
    """Message audit log serializer."""
    direction_display = serializers.CharField(source='get_direction_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    booking_reference = serializers.CharField(source='booking.booking_reference', read_only=True, default=None)

    class Meta:
        model = WhatsAppMessageLog
        fields = [
            'id',
            'message_id',
            'provider_message_id',
            'direction',
            'direction_display',
            'recipient_phone',
            'recipient_name',
            'sender_phone',
            'template',
            'template_name',
            'message_body',
            'parameters',
            'status',
            'status_display',
            'booking',
            'booking_reference',
            'lead',
            'reminder',
            'error_code',
            'error_message',
            'cost_tier',
            'sent_at',
            'delivered_at',
            'read_at',
            'failed_at',
            'created_at',
        ]
        read_only_fields = fields


class WhatsAppTestSendSerializer(serializers.Serializer):
    """Serializer for test message dispatch."""
    recipient_phone = serializers.CharField(max_length=30)
    template_name = serializers.CharField(max_length=100)
    custom_context = serializers.DictField(required=False, default=dict)

    def validate_recipient_phone(self, value):
        norm = normalize_phone_number(value)
        if not norm:
            raise serializers.ValidationError("Valid phone number required.")
        return norm

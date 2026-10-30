from django.contrib import admin
from whatsapp.models import (
    WhatsAppConfig,
    WhatsAppTemplate,
    WhatsAppOptOut,
    WhatsAppReminder,
    WhatsAppMessageLog,
)


@admin.register(WhatsAppConfig)
class WhatsAppConfigAdmin(admin.ModelAdmin):
    list_display = ('practice', 'provider', 'display_phone_number', 'is_enabled', 'auto_confirmation_enabled', 'auto_reminders_enabled')
    list_filter = ('provider', 'is_enabled', 'auto_confirmation_enabled', 'auto_reminders_enabled')
    search_fields = ('practice__name', 'display_phone_number', 'business_name')


@admin.register(WhatsAppTemplate)
class WhatsAppTemplateAdmin(admin.ModelAdmin):
    list_display = ('template_name', 'title', 'practice', 'category', 'language', 'meta_status', 'is_active', 'is_system_default')
    list_filter = ('category', 'language', 'meta_status', 'is_active', 'is_system_default')
    search_fields = ('template_name', 'title', 'body_text')


@admin.register(WhatsAppOptOut)
class WhatsAppOptOutAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'patient_name', 'practice', 'is_opted_out', 'reason', 'source_channel', 'opted_out_at')
    list_filter = ('is_opted_out', 'reason', 'source_channel')
    search_fields = ('phone_number', 'patient_name', 'practice__name')


@admin.register(WhatsAppReminder)
class WhatsAppReminderAdmin(admin.ModelAdmin):
    list_display = ('reminder_type', 'practice', 'booking', 'lead', 'scheduled_for', 'status', 'sent_at')
    list_filter = ('reminder_type', 'status', 'scheduled_for')
    search_fields = ('booking__booking_reference', 'booking__patient_name', 'practice__name')


@admin.register(WhatsAppMessageLog)
class WhatsAppMessageLogAdmin(admin.ModelAdmin):
    list_display = ('message_id', 'recipient_phone', 'direction', 'template_name', 'status', 'practice', 'sent_at')
    list_filter = ('direction', 'status', 'template_name', 'sent_at')
    search_fields = ('message_id', 'provider_message_id', 'recipient_phone', 'recipient_name', 'message_body')

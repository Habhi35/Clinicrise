from django.contrib import admin
from leads.models import ClickEvent, Lead, LeadActivity


class LeadActivityInline(admin.TabularInline):
    model = LeadActivity
    extra = 0
    readonly_fields = ['created_at', 'performed_by', 'activity_type', 'previous_status', 'new_status', 'note']


class ClickEventInline(admin.TabularInline):
    model = ClickEvent
    extra = 0
    readonly_fields = ['created_at', 'event_type', 'target_phone', 'doctor_name', 'service_name', 'page_url']


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = [
        'patient_name',
        'phone_number',
        'practice',
        'status',
        'priority',
        'source',
        'is_read',
        'consent_given',
        'whatsapp_opt_in',
        'created_at',
    ]
    list_filter = [
        'status',
        'priority',
        'source',
        'is_read',
        'consent_given',
        'whatsapp_opt_in',
        'practice',
    ]
    search_fields = [
        'patient_name',
        'phone_number',
        'email',
        'service_requested',
        'doctor_requested',
        'message',
    ]
    readonly_fields = [
        'id',
        'created_at',
        'updated_at',
        'consent_timestamp',
        'consent_ip_address',
        'consent_withdrawn_at',
        'ip_address',
        'user_agent',
    ]
    inlines = [LeadActivityInline, ClickEventInline]


@admin.register(LeadActivity)
class LeadActivityAdmin(admin.ModelAdmin):
    list_display = ['lead', 'activity_type', 'performed_by', 'previous_status', 'new_status', 'created_at']
    list_filter = ['activity_type', 'practice']
    search_fields = ['lead__patient_name', 'lead__phone_number', 'note']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ClickEvent)
class ClickEventAdmin(admin.ModelAdmin):
    list_display = ['event_type', 'practice', 'target_phone', 'doctor_name', 'service_name', 'created_at']
    list_filter = ['event_type', 'practice']
    search_fields = ['target_phone', 'doctor_name', 'service_name', 'page_url', 'visitor_id']
    readonly_fields = ['created_at', 'updated_at']

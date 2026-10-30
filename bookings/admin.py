from django.contrib import admin
from bookings.models import (
    BookingRequest,
    BookingTimeline,
    DoctorSessionCapacity,
    PracticeLocation,
)


class BookingTimelineInline(admin.TabularInline):
    model = BookingTimeline
    extra = 0
    readonly_fields = ['action', 'performed_by', 'note', 'created_at']


@admin.register(PracticeLocation)
class PracticeLocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'practice', 'city', 'phone_number', 'is_telehealth_default', 'is_primary', 'is_active']
    list_filter = ['is_active', 'is_primary', 'is_telehealth_default', 'practice']
    search_fields = ['name', 'code', 'city', 'address']


@admin.register(DoctorSessionCapacity)
class DoctorSessionCapacityAdmin(admin.ModelAdmin):
    list_display = ['doctor', 'practice', 'session_name', 'booking_mode', 'max_tokens_per_session', 'auto_confirm']
    list_filter = ['booking_mode', 'auto_confirm', 'practice']
    search_fields = ['doctor__user__first_name', 'doctor__user__last_name', 'session_name']


@admin.register(BookingRequest)
class BookingRequestAdmin(admin.ModelAdmin):
    list_display = [
        'booking_reference',
        'patient_name',
        'phone_number',
        'practice',
        'doctor',
        'appointment_date',
        'booking_mode',
        'token_number',
        'start_time',
        'status',
        'created_at',
    ]
    list_filter = [
        'status',
        'booking_mode',
        'consultation_mode',
        'appointment_date',
        'practice',
    ]
    search_fields = [
        'booking_reference',
        'patient_name',
        'phone_number',
        'email',
        'chief_complaint',
    ]
    readonly_fields = [
        'id',
        'booking_reference',
        'created_at',
        'updated_at',
        'confirmed_at',
        'cancelled_at',
    ]
    inlines = [BookingTimelineInline]


@admin.register(BookingTimeline)
class BookingTimelineAdmin(admin.ModelAdmin):
    list_display = ['booking', 'action', 'performed_by', 'created_at']
    list_filter = ['action', 'practice']
    search_fields = ['booking__booking_reference', 'note']
    readonly_fields = ['created_at', 'updated_at']

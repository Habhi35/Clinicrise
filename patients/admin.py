from django.contrib import admin
from patients.models import (
    Patient,
    PatientFollowUp,
    PatientNote,
    PatientTimeline,
    PatientVitals,
)


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ['patient_id', 'full_name', 'phone_number', 'gender', 'age', 'blood_group', 'status', 'practice', 'created_at']
    list_filter = ['practice', 'status', 'gender', 'blood_group', 'created_at']
    search_fields = ['patient_id', 'first_name', 'last_name', 'phone_number', 'email']
    ordering = ['-created_at']


@admin.register(PatientNote)
class PatientNoteAdmin(admin.ModelAdmin):
    list_display = ['patient', 'category', 'author', 'author_role', 'is_pinned', 'created_at']
    list_filter = ['category', 'is_pinned', 'author_role', 'created_at']
    search_fields = ['patient__first_name', 'patient__last_name', 'note']


@admin.register(PatientVitals)
class PatientVitalsAdmin(admin.ModelAdmin):
    list_display = ['patient', 'blood_pressure_systolic', 'blood_pressure_diastolic', 'pulse_bpm', 'temperature_fahrenheit', 'oxygen_saturation_spo2', 'bmi', 'recorded_by', 'created_at']
    list_filter = ['created_at']
    search_fields = ['patient__first_name', 'patient__last_name']


@admin.register(PatientFollowUp)
class PatientFollowUpAdmin(admin.ModelAdmin):
    list_display = ['title', 'patient', 'follow_up_type', 'priority', 'status', 'due_date', 'assigned_to']
    list_filter = ['status', 'priority', 'follow_up_type', 'due_date']
    search_fields = ['title', 'patient__first_name', 'patient__last_name', 'instructions']


@admin.register(PatientTimeline)
class PatientTimelineAdmin(admin.ModelAdmin):
    list_display = ['patient', 'event_type', 'title', 'performed_by', 'performer_role', 'created_at']
    list_filter = ['event_type', 'performer_role', 'created_at']
    search_fields = ['patient__first_name', 'patient__last_name', 'title', 'description']

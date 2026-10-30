from django.contrib import admin
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


class PracticeMembershipInline(admin.TabularInline):
    model = PracticeMembership
    extra = 1
    fields = ('user', 'role', 'is_active', 'joined_at')
    readonly_fields = ('joined_at',)


class PracticeServiceInline(admin.TabularInline):
    model = PracticeService
    extra = 1
    fields = ('name', 'category', 'duration_minutes', 'price', 'is_active')


class PracticeImageInline(admin.TabularInline):
    model = PracticeImage
    extra = 1
    fields = ('image_type', 'image_url', 'caption', 'is_primary', 'order')


@admin.register(Practice)
class PracticeAdmin(admin.ModelAdmin):
    list_display = ('name', 'clinic_type', 'owner', 'phone_number', 'city', 'state', 'currency', 'is_active', 'created_at')
    list_filter = ('clinic_type', 'is_active', 'city', 'state', 'currency')
    search_fields = ('name', 'owner__email', 'owner__phone_number', 'phone_number', 'city')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [PracticeMembershipInline, PracticeServiceInline, PracticeImageInline]
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(PracticeMembership)
class PracticeMembershipAdmin(admin.ModelAdmin):
    list_display = ('practice', 'user', 'role', 'is_active', 'joined_at')
    list_filter = ('role', 'is_active', 'joined_at')
    search_fields = ('practice__name', 'user__email', 'user__phone_number')
    readonly_fields = ('id', 'joined_at', 'updated_at')


@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'medical_license_number', 'registration_council', 'specialization', 'experience_years', 'is_verified', 'created_at')
    list_filter = ('specialization', 'is_verified', 'gender', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'medical_license_number', 'registration_council', 'specialization')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(PracticeInvitation)
class PracticeInvitationAdmin(admin.ModelAdmin):
    list_display = ('practice', 'email', 'phone_number', 'role', 'status', 'invited_by', 'expires_at')
    list_filter = ('role', 'status', 'created_at')
    search_fields = ('practice__name', 'email', 'phone_number', 'invite_code')
    readonly_fields = ('id', 'invite_code', 'created_at')


@admin.register(PracticeService)
class PracticeServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'practice', 'doctor', 'category', 'duration_minutes', 'price', 'is_active')
    list_filter = ('category', 'is_active', 'is_teleconsultation')
    search_fields = ('name', 'practice__name', 'description')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(DoctorSchedule)
class DoctorScheduleAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'practice', 'day_of_week', 'session_name', 'start_time', 'end_time', 'slot_duration_minutes', 'is_active')
    list_filter = ('day_of_week', 'is_active')
    search_fields = ('doctor__user__email', 'doctor__user__first_name', 'practice__name', 'session_name')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(PracticeImage)
class PracticeImageAdmin(admin.ModelAdmin):
    list_display = ('practice', 'image_type', 'caption', 'is_primary', 'order', 'created_at')
    list_filter = ('image_type', 'is_primary')
    search_fields = ('practice__name', 'caption')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(DoctorOnboarding)
class DoctorOnboardingAdmin(admin.ModelAdmin):
    list_display = ('user', 'practice', 'current_step', 'is_completed', 'completed_at', 'updated_at')
    list_filter = ('current_step', 'is_completed')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'practice__name')
    readonly_fields = ('id', 'created_at', 'updated_at')

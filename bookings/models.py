import random
import string
import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from practices.models import TenantAwareModel


def generate_booking_reference():
    """Generates a human-friendly unique booking reference like CR-202610-8F9A."""
    date_part = timezone.now().strftime("%Y%m")
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"CR-{date_part}-{random_part}"


class PracticeLocation(TenantAwareModel):
    """
    Physical clinic branch, outpatient center, or virtual consultation facility.
    Supports multi-location practices with separate addresses and room designations.
    """
    name = models.CharField(max_length=255, help_text="Branch or facility name, e.g. Jubilee Hills Main Clinic")
    code = models.CharField(max_length=30, blank=True, help_text="Short identifier code, e.g. JH-01")
    address = models.TextField(blank=True)
    landmark = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default='India')
    phone_number = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    google_maps_url = models.URLField(max_length=500, blank=True, null=True)

    is_telehealth_default = models.BooleanField(
        default=False,
        help_text="Designates this location for remote/video teleconsultations"
    )
    is_primary = models.BooleanField(default=False, help_text="Primary headquarters or main clinic branch")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-is_primary', 'name']
        verbose_name = 'Practice Location'
        verbose_name_plural = 'Practice Locations'
        indexes = [
            models.Index(fields=['practice', 'is_active']),
            models.Index(fields=['practice', 'is_primary']),
        ]

    def __str__(self):
        primary_tag = " (Main)" if self.is_primary else ""
        return f"{self.name}{primary_tag} - {self.practice.name}"

    def save(self, *args, **kwargs):
        if self.is_primary:
            # Ensure only one primary location per practice
            PracticeLocation.objects.filter(practice=self.practice, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


class DoctorSessionCapacity(TenantAwareModel):
    """
    Configurable capacity rules and booking modes per doctor and OPD session.
    Controls whether bookings use Exact Time-Slots or Sequential OPD Tokens,
    and sets maximum patient capacity per session.
    """
    MODE_SLOT = 'slot'
    MODE_TOKEN = 'token'

    BOOKING_MODE_CHOICES = [
        (MODE_SLOT, 'Exact Time Slot Mode'),
        (MODE_TOKEN, 'Session / Token Mode'),
    ]

    doctor = models.ForeignKey(
        'practices.DoctorProfile',
        on_delete=models.CASCADE,
        related_name='session_capacities'
    )
    location = models.ForeignKey(
        PracticeLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='session_capacities',
        help_text="Optional specific location for this session"
    )
    session_name = models.CharField(max_length=100, default='General OPD', help_text="e.g. Morning OPD, Evening Shift")
    booking_mode = models.CharField(max_length=20, choices=BOOKING_MODE_CHOICES, default=MODE_SLOT)
    max_tokens_per_session = models.PositiveIntegerField(
        default=25,
        help_text="Maximum number of patient tokens allowed for this OPD session"
    )
    slot_duration_minutes = models.PositiveSmallIntegerField(
        default=15,
        help_text="Consultation slot duration in minutes (for time-slot mode)"
    )
    auto_confirm = models.BooleanField(
        default=False,
        help_text="Automatically confirm booking request if capacity check passes"
    )

    class Meta:
        verbose_name = 'Doctor Session Capacity'
        verbose_name_plural = 'Doctor Session Capacities'
        unique_together = ('practice', 'doctor', 'session_name')

    def __str__(self):
        return f"{self.doctor} - {self.session_name} ({self.get_booking_mode_display()} | Max: {self.max_tokens_per_session})"


class BookingRequest(TenantAwareModel):
    """
    Patient appointment booking request supporting both Time-Slot scheduling
    and Session/Token queue modes, multi-location clinics, and clinic confirmation.
    """
    # Consultation Mode
    MODE_IN_PERSON = 'in_person'
    MODE_VIDEO = 'video'
    MODE_PHONE = 'phone'
    MODE_HOME_VISIT = 'home_visit'

    CONSULTATION_MODE_CHOICES = [
        (MODE_IN_PERSON, 'In-Person Clinic Visit'),
        (MODE_VIDEO, 'Video Teleconsultation'),
        (MODE_PHONE, 'Phone Consultation'),
        (MODE_HOME_VISIT, 'Home Healthcare Visit'),
    ]

    # Scheduling Mode
    SCHEDULING_MODE_SLOT = 'slot'
    SCHEDULING_MODE_TOKEN = 'token'

    SCHEDULING_MODE_CHOICES = [
        (SCHEDULING_MODE_SLOT, 'Exact Time Slot'),
        (SCHEDULING_MODE_TOKEN, 'Session / Token Mode'),
    ]

    # Preferred Time Window (when requesting)
    WINDOW_MORNING = 'morning'
    WINDOW_AFTERNOON = 'afternoon'
    WINDOW_EVENING = 'evening'
    WINDOW_ANY = 'any'

    TIME_WINDOW_CHOICES = [
        (WINDOW_MORNING, 'Morning (9:00 AM - 12:00 PM)'),
        (WINDOW_AFTERNOON, 'Afternoon (12:00 PM - 4:00 PM)'),
        (WINDOW_EVENING, 'Evening (4:00 PM - 8:00 PM)'),
        (WINDOW_ANY, 'Any Available Time'),
    ]

    # Patient Type
    TYPE_NEW = 'new'
    TYPE_RETURNING = 'returning'

    PATIENT_TYPE_CHOICES = [
        (TYPE_NEW, 'New Patient'),
        (TYPE_RETURNING, 'Returning Patient'),
    ]

    # Booking Lifecycle Status
    STATUS_REQUESTED = 'requested'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_RESCHEDULED = 'rescheduled'
    STATUS_CHECKED_IN = 'checked_in'
    STATUS_IN_CONSULTATION = 'in_consultation'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_REJECTED = 'rejected'
    STATUS_NO_SHOW = 'no_show'

    STATUS_CHOICES = [
        (STATUS_REQUESTED, 'Pending Clinic Confirmation'),
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_RESCHEDULED, 'Rescheduled'),
        (STATUS_CHECKED_IN, 'Checked In / Waiting Area'),
        (STATUS_IN_CONSULTATION, 'In Consultation Room'),
        (STATUS_COMPLETED, 'Consultation Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_REJECTED, 'Declined / Rejected by Clinic'),
        (STATUS_NO_SHOW, 'Patient No Show'),
    ]

    # Booking Source
    SOURCE_WEBSITE = 'website'
    SOURCE_PATIENT_PORTAL = 'patient_portal'
    SOURCE_FRONTDESK = 'frontdesk'
    SOURCE_PHONE = 'phone'
    SOURCE_DOCTOR_REFERRAL = 'doctor_referral'

    SOURCE_CHOICES = [
        (SOURCE_WEBSITE, 'Clinic Website'),
        (SOURCE_PATIENT_PORTAL, 'Patient Portal'),
        (SOURCE_FRONTDESK, 'Frontdesk / Reception'),
        (SOURCE_PHONE, 'Phone Call'),
        (SOURCE_DOCTOR_REFERRAL, 'Doctor Referral'),
    ]

    # Core Identifiers & Relationships
    booking_reference = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
        default=generate_booking_reference,
        help_text="Public patient tracking reference, e.g. CR-202610-8F9A"
    )
    location = models.ForeignKey(
        PracticeLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings',
        help_text="Clinical branch or facility"
    )
    doctor = models.ForeignKey(
        'practices.DoctorProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings',
        help_text="Assigned practitioner"
    )
    service = models.ForeignKey(
        'practices.PracticeService',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings',
        help_text="Requested medical treatment or consultation service"
    )
    lead = models.ForeignKey(
        'leads.Lead',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings',
        help_text="Associated inquiry/lead record if converted"
    )

    # Patient Details
    patient_name = models.CharField(max_length=200, help_text="Full patient name")
    phone_number = models.CharField(max_length=30, db_index=True, help_text="Patient contact phone number")
    email = models.EmailField(blank=True, help_text="Patient email address for confirmation notices")
    gender = models.CharField(
        max_length=20,
        blank=True,
        choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')]
    )
    age = models.PositiveSmallIntegerField(null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    patient_type = models.CharField(max_length=20, choices=PATIENT_TYPE_CHOICES, default=TYPE_NEW)

    # Booking Preferences
    consultation_mode = models.CharField(max_length=30, choices=CONSULTATION_MODE_CHOICES, default=MODE_IN_PERSON)
    preferred_date = models.DateField(help_text="Patient requested date")
    preferred_time_window = models.CharField(max_length=50, choices=TIME_WINDOW_CHOICES, default=WINDOW_ANY)
    chief_complaint = models.TextField(blank=True, help_text="Patient medical issue, symptoms, or reason for visit")
    patient_notes = models.TextField(blank=True, help_text="Special requests, wheelchair assistance, etc.")

    # Scheduling Engine: Slot vs Token Mode
    booking_mode = models.CharField(
        max_length=20,
        choices=SCHEDULING_MODE_CHOICES,
        default=SCHEDULING_MODE_SLOT,
        db_index=True
    )
    appointment_date = models.DateField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Confirmed date of consultation"
    )
    session_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="OPD Session name in Token mode (e.g. Morning OPD, Evening Shift)"
    )
    token_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Sequential queue token number assigned to patient"
    )
    start_time = models.TimeField(null=True, blank=True, help_text="Start time in Slot mode")
    end_time = models.TimeField(null=True, blank=True, help_text="End time in Slot mode")
    estimated_arrival_time = models.TimeField(null=True, blank=True, help_text="Estimated arrival or consult window")

    # Status, Confirmation & Clinical Triage
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_REQUESTED, db_index=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='confirmed_bookings'
    )
    rejection_reason = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    clinic_notes = models.TextField(blank=True, help_text="Internal staff remarks and instructions")

    # Source & Consent
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES, default=SOURCE_WEBSITE)
    consent_given = models.BooleanField(default=True)
    consent_timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-appointment_date', '-created_at']
        verbose_name = 'Booking Request'
        verbose_name_plural = 'Booking Requests'
        indexes = [
            models.Index(fields=['practice', 'status']),
            models.Index(fields=['practice', 'appointment_date']),
            models.Index(fields=['practice', 'doctor', 'appointment_date']),
            models.Index(fields=['practice', 'booking_mode', 'appointment_date']),
        ]

    def __str__(self):
        mode_detail = f"Token #{self.token_number}" if self.booking_mode == self.SCHEDULING_MODE_TOKEN and self.token_number else f"{self.start_time}" if self.start_time else "Unscheduled"
        return f"{self.booking_reference}: {self.patient_name} - {self.get_status_display()} ({mode_detail}) [{self.practice.name}]"

    def confirm(self, user=None, confirmed_date=None, start_time=None, end_time=None, token_number=None, session_name=""):
        """Confirms the booking, updating status and timestamps."""
        self.status = self.STATUS_CONFIRMED
        self.confirmed_at = timezone.now()
        self.confirmed_by = user

        if confirmed_date:
            self.appointment_date = confirmed_date
        elif not self.appointment_date:
            self.appointment_date = self.preferred_date

        if self.booking_mode == self.SCHEDULING_MODE_TOKEN:
            if token_number is not None:
                self.token_number = token_number
            if session_name:
                self.session_name = session_name
        else:
            if start_time:
                self.start_time = start_time
            if end_time:
                self.end_time = end_time

        self.save()
        BookingTimeline.objects.create(
            practice=self.practice,
            booking=self,
            performed_by=user,
            action='confirmed',
            note=f"Booking confirmed. Mode: {self.get_booking_mode_display()}, Date: {self.appointment_date}"
        )


class BookingTimeline(TenantAwareModel):
    """
    Audit trail tracking booking status changes, confirmations,
    reschedules, and staff notes.
    """
    booking = models.ForeignKey(BookingRequest, on_delete=models.CASCADE, related_name='timeline')
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='booking_timeline_actions'
    )
    action = models.CharField(max_length=40, help_text="e.g. requested, confirmed, rescheduled, cancelled, checked_in")
    note = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Booking Timeline'
        verbose_name_plural = 'Booking Timelines'

    def __str__(self):
        return f"{self.booking.booking_reference} - {self.action} at {self.created_at.strftime('%Y-%m-%d %H:%M')}"

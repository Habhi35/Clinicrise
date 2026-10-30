import random
import string
import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from practices.models import TenantAwareModel


def normalize_patient_phone(phone_number: str) -> str:
    """Normalizes phone number to clean digits with country code format."""
    if not phone_number:
        return ""
    cleaned = ''.join(c for c in phone_number if c.isdigit() or c == '+')
    if not cleaned.startswith('+'):
        digits_only = ''.join(c for c in cleaned if c.isdigit())
        if len(digits_only) == 10:
            return f"+91{digits_only}"
        return f"+{digits_only}"
    return cleaned


def generate_patient_mrn():
    """Generates a human-friendly unique Medical Record Number (MRN), e.g. CR-P-202610-8A12."""
    date_part = timezone.now().strftime("%Y%m")
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"CR-P-{date_part}-{random_part}"


class Patient(TenantAwareModel):
    """
    Patient master record in ClinicRise Clinical CRM.
    Strictly tenant-isolated per Practice.
    Serves as the single source of truth across Frontdesk, Clinical Assistants, and Doctors.
    """
    GENDER_MALE = 'male'
    GENDER_FEMALE = 'female'
    GENDER_OTHER = 'other'
    GENDER_UNSPECIFIED = 'unspecified'

    GENDER_CHOICES = [
        (GENDER_MALE, 'Male'),
        (GENDER_FEMALE, 'Female'),
        (GENDER_OTHER, 'Other'),
        (GENDER_UNSPECIFIED, 'Prefer not to say'),
    ]

    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'),
        ('A-', 'A-'),
        ('B+', 'B+'),
        ('B-', 'B-'),
        ('AB+', 'AB+'),
        ('AB-', 'AB-'),
        ('O+', 'O+'),
        ('O-', 'O-'),
        ('unknown', 'Unknown / Not Tested'),
    ]

    STATUS_ACTIVE = 'active'
    STATUS_ARCHIVED = 'archived'
    STATUS_INACTIVE = 'inactive'

    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active Patient'),
        (STATUS_ARCHIVED, 'Archived / Inactive'),
        (STATUS_INACTIVE, 'Deactivated'),
    ]

    SOURCE_WALK_IN = 'walk_in'
    SOURCE_WEBSITE_BOOKING = 'website_booking'
    SOURCE_LEAD_CONVERSION = 'lead_conversion'
    SOURCE_PHONE_CALL = 'phone_call'
    SOURCE_REFERRAL = 'referral'
    SOURCE_OTHER = 'other'

    SOURCE_CHOICES = [
        (SOURCE_WALK_IN, 'Frontdesk Walk-in'),
        (SOURCE_WEBSITE_BOOKING, 'Website Booking Request'),
        (SOURCE_LEAD_CONVERSION, 'Converted from Web/WhatsApp Lead'),
        (SOURCE_PHONE_CALL, 'Phone Call Intake'),
        (SOURCE_REFERRAL, 'Doctor / Patient Referral'),
        (SOURCE_OTHER, 'Other Source'),
    ]

    patient_id = models.CharField(
        max_length=40,
        unique=True,
        default=generate_patient_mrn,
        db_index=True,
        help_text="Unique Medical Record Number (MRN) for practice patient charting"
    )

    first_name = models.CharField(max_length=100, help_text="Patient given name")
    last_name = models.CharField(max_length=100, blank=True, help_text="Patient family name / surname")
    phone_number = models.CharField(max_length=30, db_index=True, help_text="Primary contact phone number (E.164)")
    email = models.EmailField(blank=True, help_text="Optional patient email address")

    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, default=GENDER_UNSPECIFIED)
    date_of_birth = models.DateField(null=True, blank=True, help_text="Patient date of birth")
    age = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Calculated or reported age")
    blood_group = models.CharField(max_length=15, choices=BLOOD_GROUP_CHOICES, default='unknown', blank=True)

    # Address & Location
    address = models.TextField(blank=True, help_text="Residential street address")
    city = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)

    # Emergency Contact
    emergency_contact_name = models.CharField(max_length=150, blank=True)
    emergency_contact_phone = models.CharField(max_length=30, blank=True)
    emergency_contact_relation = models.CharField(max_length=50, blank=True, help_text="e.g. Spouse, Parent, Sibling")

    # Clinical Alerts & Medical History
    allergies = models.TextField(blank=True, help_text="Known drug, food, or environmental allergies (e.g. Penicillin, NSAIDs)")
    chronic_conditions = models.JSONField(default=list, blank=True, help_text="List of chronic medical conditions (e.g. Diabetes, Hypertension)")
    medical_alerts = models.TextField(blank=True, help_text="Critical clinical warnings displayed prominently in header banner")
    tags = models.JSONField(default=list, blank=True, help_text="Categorization tags (e.g. VIP, Senior Citizen, Dental Anxiety)")

    # CRM Lifecycle & Staff Assignment
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE, db_index=True)
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES, default=SOURCE_WALK_IN)
    converted_from_lead = models.ForeignKey(
        'leads.Lead',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='converted_patients',
        help_text="Original lead if this patient was converted from marketing inquiry"
    )
    primary_doctor = models.ForeignKey(
        'practices.DoctorProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='primary_patients',
        help_text="Primary attending physician or dentist"
    )

    total_visits_count = models.PositiveIntegerField(default=0)
    last_visit_date = models.DateField(null=True, blank=True)
    preferred_language = models.CharField(max_length=50, default='English', blank=True)

    # Communication Preferences & Consent
    whatsapp_opt_in = models.BooleanField(default=True)
    sms_opt_in = models.BooleanField(default=True)
    call_opt_in = models.BooleanField(default=True)
    email_opt_in = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Patient'
        verbose_name_plural = 'Patients'
        indexes = [
            models.Index(fields=['practice', 'phone_number']),
            models.Index(fields=['practice', 'status']),
            models.Index(fields=['practice', 'last_visit_date']),
            models.Index(fields=['practice', 'created_at']),
        ]

    def __str__(self):
        return f"{self.patient_id}: {self.full_name} ({self.phone_number}) [{self.practice.name}]"

    def save(self, *args, **kwargs):
        if self.phone_number:
            self.phone_number = normalize_patient_phone(self.phone_number)
        if self.emergency_contact_phone:
            self.emergency_contact_phone = normalize_patient_phone(self.emergency_contact_phone)
        if self.date_of_birth and not self.age:
            today = timezone.now().date()
            self.age = today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        parts = [self.first_name, self.last_name]
        name = ' '.join(p for p in parts if p).strip()
        return name or "Unnamed Patient"


class PatientNote(TenantAwareModel):
    """
    Chronological notes and observations for a patient.
    Supports frontdesk remarks, clinical assistant prep/triage, doctor consultation findings,
    and follow-up logs, with pinning for high-priority clinical warnings.
    """
    CATEGORY_FRONTDESK = 'frontdesk'
    CATEGORY_CLINICAL_PREP = 'clinical_prep'
    CATEGORY_DOCTOR = 'doctor_consultation'
    CATEGORY_FOLLOW_UP = 'follow_up'
    CATEGORY_GENERAL = 'general'

    CATEGORY_CHOICES = [
        (CATEGORY_FRONTDESK, 'Frontdesk / Check-In Note'),
        (CATEGORY_CLINICAL_PREP, 'Assistant Clinical Prep / Triage'),
        (CATEGORY_DOCTOR, 'Doctor Consultation Observation'),
        (CATEGORY_FOLLOW_UP, 'Follow-up Call / Recovery Check'),
        (CATEGORY_GENERAL, 'General Administrative Note'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='notes')
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='patient_notes',
        help_text="User who wrote this note"
    )
    author_role = models.CharField(max_length=30, blank=True, help_text="e.g. receptionist, assistant, doctor, admin")
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default=CATEGORY_GENERAL)
    note = models.TextField(help_text="Text content of the note")

    is_pinned = models.BooleanField(default=False, db_index=True, help_text="Pinned notes appear at top of patient profile banner")
    pinned_at = models.DateTimeField(null=True, blank=True)
    pinned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pinned_patient_notes'
    )

    class Meta:
        ordering = ['-is_pinned', '-created_at']
        verbose_name = 'Patient Note'
        verbose_name_plural = 'Patient Notes'

    def __str__(self):
        return f"[{self.get_category_display()}] Note for {self.patient.full_name} by {self.author or 'System'}"

    def toggle_pin(self, user=None):
        """Pins or unpins this note."""
        self.is_pinned = not self.is_pinned
        if self.is_pinned:
            self.pinned_at = timezone.now()
            self.pinned_by = user
        else:
            self.pinned_at = None
            self.pinned_by = None
        self.save(update_fields=['is_pinned', 'pinned_at', 'pinned_by', 'updated_at'])


class PatientVitals(TenantAwareModel):
    """
    Patient vital signs recorded by clinical assistants, nurses, or receptionists.
    Includes blood pressure, pulse, temperature, SpO2, respiratory rate, weight, height, and BMI.
    """
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='vitals')
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recorded_vitals'
    )
    booking = models.ForeignKey(
        'bookings.BookingRequest',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vitals',
        help_text="Associated appointment visit, if recorded during a clinic visit"
    )

    blood_pressure_systolic = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Systolic BP (mmHg), e.g. 120")
    blood_pressure_diastolic = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Diastolic BP (mmHg), e.g. 80")
    pulse_bpm = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Heart rate / pulse in beats per min (bpm)")
    temperature_fahrenheit = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, help_text="Body temperature in °F, e.g. 98.6")
    oxygen_saturation_spo2 = models.PositiveSmallIntegerField(null=True, blank=True, help_text="SpO2 percentage (e.g. 98%)")
    respiratory_rate = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Breaths per minute")
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Body weight in kg")
    height_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, help_text="Body height in cm")
    bmi = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, help_text="Auto-calculated Body Mass Index")
    blood_sugar_fasting = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Fasting blood sugar (mg/dL)")
    blood_sugar_random = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Random blood sugar (mg/dL)")
    notes = models.TextField(blank=True, help_text="Clinical assistant remarks or observations")

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Patient Vitals'
        verbose_name_plural = 'Patient Vitals'

    def __str__(self):
        bp = f"{self.blood_pressure_systolic}/{self.blood_pressure_diastolic}" if self.blood_pressure_systolic else "N/A"
        return f"Vitals for {self.patient.full_name}: BP {bp}, Pulse {self.pulse_bpm or 'N/A'} at {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    def save(self, *args, **kwargs):
        # Auto-compute BMI if weight and height are present
        if self.weight_kg and self.height_cm and self.height_cm > 0:
            height_m = float(self.height_cm) / 100.0
            computed_bmi = float(self.weight_kg) / (height_m * height_m)
            self.bmi = round(computed_bmi, 1)
        super().save(*args, **kwargs)


class PatientFollowUp(TenantAwareModel):
    """
    Actionable follow-up tasks assigned to receptionists, clinical assistants, or doctors.
    Includes post-procedure checks, lab report reviews, medication checks, and routine recalls.
    """
    TYPE_POST_CONSULTATION = 'post_consultation_check'
    TYPE_LAB_REPORT = 'lab_report_review'
    TYPE_MEDICATION_CHECK = 'medication_check'
    TYPE_ROUTINE_RECALL = 'routine_recall'
    TYPE_RESCHEDULE = 'booking_reschedule'
    TYPE_CUSTOM = 'custom'

    TYPE_CHOICES = [
        (TYPE_POST_CONSULTATION, 'Post-Consultation / Procedure Check'),
        (TYPE_LAB_REPORT, 'Lab / Diagnostic Report Review'),
        (TYPE_MEDICATION_CHECK, 'Medication Check & Tolerance'),
        (TYPE_ROUTINE_RECALL, 'Routine Periodic Recall / Dental Check'),
        (TYPE_RESCHEDULE, 'Missed Booking Follow-up'),
        (TYPE_CUSTOM, 'Custom Clinical Task'),
    ]

    PRIORITY_LOW = 'low'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_HIGH = 'high'
    PRIORITY_URGENT = 'urgent'

    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'Low Priority'),
        (PRIORITY_MEDIUM, 'Medium Priority'),
        (PRIORITY_HIGH, 'High Priority'),
        (PRIORITY_URGENT, 'Urgent / Priority'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_OVERDUE = 'overdue'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_IN_PROGRESS, 'In Progress / Called'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_OVERDUE, 'Overdue'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='follow_ups')
    booking = models.ForeignKey(
        'bookings.BookingRequest',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='follow_ups'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_follow_ups'
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_follow_ups',
        help_text="Receptionist, assistant, or doctor responsible for actioning this follow-up"
    )

    follow_up_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default=TYPE_POST_CONSULTATION)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)
    due_date = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)

    title = models.CharField(max_length=200, help_text="Short task summary, e.g. Post-extraction pain check")
    instructions = models.TextField(blank=True, help_text="Guidance for receptionist or assistant executing the follow-up")
    outcome_notes = models.TextField(blank=True, help_text="Notes recorded when completing follow-up")

    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='completed_follow_ups'
    )

    class Meta:
        ordering = ['due_date', '-priority']
        verbose_name = 'Patient Follow-Up'
        verbose_name_plural = 'Patient Follow-Ups'
        indexes = [
            models.Index(fields=['practice', 'status', 'due_date']),
            models.Index(fields=['practice', 'assigned_to', 'status']),
        ]

    def __str__(self):
        return f"{self.title} for {self.patient.full_name} (Due: {self.due_date.strftime('%Y-%m-%d')} | {self.get_status_display()})"

    def complete(self, user=None, outcome_notes=""):
        """Marks follow-up as completed and records outcome."""
        self.status = self.STATUS_COMPLETED
        self.completed_at = timezone.now()
        self.completed_by = user
        if outcome_notes:
            self.outcome_notes = outcome_notes
        self.save(update_fields=['status', 'completed_at', 'completed_by', 'outcome_notes', 'updated_at'])


class PatientTimeline(TenantAwareModel):
    """
    Unified chronological audit trail of all patient touchpoints across the practice.
    Includes bookings, check-ins, vitals, clinical prep, doctor notes, phone calls,
    WhatsApp notifications, and follow-ups.
    """
    EVENT_PATIENT_CREATED = 'patient_created'
    EVENT_PATIENT_UPDATED = 'patient_updated'
    EVENT_BOOKING_REQUESTED = 'booking_requested'
    EVENT_BOOKING_CONFIRMED = 'booking_confirmed'
    EVENT_PATIENT_CHECKED_IN = 'patient_checked_in'
    EVENT_CONSULTATION_STARTED = 'consultation_started'
    EVENT_CONSULTATION_COMPLETED = 'consultation_completed'
    EVENT_VITALS_RECORDED = 'vitals_recorded'
    EVENT_CLINICAL_NOTE = 'clinical_note_added'
    EVENT_FOLLOW_UP_SCHEDULED = 'follow_up_scheduled'
    EVENT_FOLLOW_UP_COMPLETED = 'follow_up_completed'
    EVENT_PHONE_CALL = 'phone_call_logged'
    EVENT_WHATSAPP_SENT = 'whatsapp_sent'
    EVENT_WHATSAPP_RECEIVED = 'whatsapp_received'
    EVENT_CONSENT_UPDATED = 'consent_updated'

    EVENT_CHOICES = [
        (EVENT_PATIENT_CREATED, 'Patient Registered / Intake'),
        (EVENT_PATIENT_UPDATED, 'Patient Profile Updated'),
        (EVENT_BOOKING_REQUESTED, 'Appointment Requested'),
        (EVENT_BOOKING_CONFIRMED, 'Appointment Confirmed'),
        (EVENT_PATIENT_CHECKED_IN, 'Patient Checked In at Frontdesk'),
        (EVENT_CONSULTATION_STARTED, 'In Consultation Room with Doctor'),
        (EVENT_CONSULTATION_COMPLETED, 'Consultation Completed'),
        (EVENT_VITALS_RECORDED, 'Vitals Recorded by Clinical Assistant'),
        (EVENT_CLINICAL_NOTE, 'Staff / Clinical Note Recorded'),
        (EVENT_FOLLOW_UP_SCHEDULED, 'Follow-up Task Scheduled'),
        (EVENT_FOLLOW_UP_COMPLETED, 'Follow-up Task Completed'),
        (EVENT_PHONE_CALL, 'Phone Call Logged'),
        (EVENT_WHATSAPP_SENT, 'WhatsApp Notification Dispatched'),
        (EVENT_WHATSAPP_RECEIVED, 'Inbound WhatsApp Reply Received'),
        (EVENT_CONSENT_UPDATED, 'Consent Preferences Updated'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='timeline')
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='patient_timeline_actions'
    )
    performer_role = models.CharField(max_length=30, blank=True, help_text="e.g. receptionist, assistant, doctor, system")
    event_type = models.CharField(max_length=40, choices=EVENT_CHOICES, db_index=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Patient Timeline Event'
        verbose_name_plural = 'Patient Timeline Events'
        indexes = [
            models.Index(fields=['patient', 'event_type', 'created_at']),
        ]

    def __str__(self):
        performer = f" by {self.performer_role}" if self.performer_role else ""
        return f"{self.title}{performer} on {self.patient.full_name} at {self.created_at.strftime('%Y-%m-%d %H:%M')}"

import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from practices.models import TenantAwareModel


class Lead(TenantAwareModel):
    """
    Prospective patient enquiry / lead captured through website forms,
    call click events, WhatsApp click events, or manual frontdesk intake.
    Strictly isolated per Practice tenant.
    """
    # Status Pipeline Choices
    STATUS_NEW = 'new'
    STATUS_CONTACTED = 'contacted'
    STATUS_IN_DISCUSSION = 'in_discussion'
    STATUS_APPOINTMENT_SCHEDULED = 'appointment_scheduled'
    STATUS_CONVERTED = 'converted'
    STATUS_LOST = 'lost'
    STATUS_JUNK = 'junk'

    STATUS_CHOICES = [
        (STATUS_NEW, 'New / Uncontacted'),
        (STATUS_CONTACTED, 'Contacted'),
        (STATUS_IN_DISCUSSION, 'In Discussion'),
        (STATUS_APPOINTMENT_SCHEDULED, 'Appointment Scheduled'),
        (STATUS_CONVERTED, 'Converted / Patient Registered'),
        (STATUS_LOST, 'Lost / Not Interested'),
        (STATUS_JUNK, 'Junk / Spam'),
    ]

    # Priority Choices
    PRIORITY_LOW = 'low'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_HIGH = 'high'
    PRIORITY_URGENT = 'urgent'

    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'Low'),
        (PRIORITY_MEDIUM, 'Medium'),
        (PRIORITY_HIGH, 'High'),
        (PRIORITY_URGENT, 'Urgent'),
    ]

    # Lead Origin & Acquisition Source
    SOURCE_WEBSITE_FORM = 'website_form'
    SOURCE_WHATSAPP_CLICK = 'whatsapp_click'
    SOURCE_CALL_CLICK = 'call_click'
    SOURCE_MANUAL = 'manual'
    SOURCE_CAMPAIGN = 'campaign'
    SOURCE_REFERRAL = 'referral'
    SOURCE_OTHER = 'other'

    SOURCE_CHOICES = [
        (SOURCE_WEBSITE_FORM, 'Website Enquiry Form'),
        (SOURCE_WHATSAPP_CLICK, 'WhatsApp Chat Click'),
        (SOURCE_CALL_CLICK, 'Phone Call Click'),
        (SOURCE_MANUAL, 'Reception / Frontdesk Manual Entry'),
        (SOURCE_CAMPAIGN, 'Marketing Ad Campaign'),
        (SOURCE_REFERRAL, 'Patient / Doctor Referral'),
        (SOURCE_OTHER, 'Other'),
    ]

    # Optional relationship to ClinicWebsite
    website = models.ForeignKey(
        'websites.ClinicWebsite',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leads',
        help_text="Website from which this lead was generated, if applicable"
    )

    # Patient Contact & Inquirer Details
    patient_name = models.CharField(max_length=200, help_text="Full name of prospective patient or contact person")
    phone_number = models.CharField(max_length=30, db_index=True, help_text="Contact phone or mobile number")
    email = models.EmailField(blank=True, help_text="Contact email address")
    preferred_date = models.DateField(null=True, blank=True, help_text="Preferred appointment or consultation date")
    preferred_time_slot = models.CharField(max_length=100, blank=True, help_text="e.g. 'Morning (9am-12pm)', 'Evening'")
    service_requested = models.CharField(max_length=255, blank=True, help_text="Requested medical treatment or specialty")
    doctor_requested = models.CharField(max_length=255, blank=True, help_text="Name of requested doctor, if any")
    message = models.TextField(blank=True, help_text="Enquiry message, patient complaint, or notes")

    # Workflow & CRM State
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_NEW, db_index=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)
    is_read = models.BooleanField(default=False, db_index=True, help_text="False if new unviewed lead in inbox")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_leads',
        help_text="Staff member or doctor assigned to triage and follow up"
    )
    last_contacted_at = models.DateTimeField(null=True, blank=True)
    follow_up_date = models.DateTimeField(null=True, blank=True, help_text="Next scheduled follow-up reminder")
    lost_reason = models.CharField(max_length=255, blank=True, help_text="Reason why lead was marked lost")

    # Attribution & Analytics
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES, default=SOURCE_WEBSITE_FORM, db_index=True)
    source_url = models.URLField(max_length=500, blank=True, help_text="Page URL where the enquiry was submitted")
    referrer = models.TextField(blank=True, help_text="HTTP Referrer URL")
    utm_source = models.CharField(max_length=100, blank=True)
    utm_medium = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=150, blank=True)
    utm_term = models.CharField(max_length=150, blank=True)
    utm_content = models.CharField(max_length=150, blank=True)
    device_type = models.CharField(max_length=50, blank=True, help_text="mobile, desktop, tablet")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    # Consent & Healthcare Privacy Compliance (GDPR / DPDP / HIPAA)
    consent_given = models.BooleanField(default=True, help_text="Explicit consent granted by user")
    consent_timestamp = models.DateTimeField(default=timezone.now, help_text="Exact timestamp of consent acceptance")
    consent_text = models.TextField(
        blank=True,
        default="I agree to receive communications regarding my enquiry via Phone, WhatsApp, SMS and Email from ClinicRise and the clinic team.",
        help_text="The exact terms/disclosure presented to the user when consent was captured"
    )
    consent_ip_address = models.GenericIPAddressField(null=True, blank=True)
    whatsapp_opt_in = models.BooleanField(default=True, help_text="Opted in for WhatsApp notifications & appointment reminders")
    call_opt_in = models.BooleanField(default=True, help_text="Opted in for phone call follow-ups")
    sms_opt_in = models.BooleanField(default=True, help_text="Opted in for SMS reminders")
    email_opt_in = models.BooleanField(default=True, help_text="Opted in for email communications")
    consent_withdrawn = models.BooleanField(default=False, help_text="Set to True if patient requests to unsubscribe/opt-out")
    consent_withdrawn_at = models.DateTimeField(null=True, blank=True)
    consent_withdrawn_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Lead / Enquiry'
        verbose_name_plural = 'Leads & Enquiries'
        indexes = [
            models.Index(fields=['practice', 'status']),
            models.Index(fields=['practice', 'is_read']),
            models.Index(fields=['practice', 'source']),
            models.Index(fields=['practice', 'created_at']),
        ]

    def __str__(self):
        return f"{self.patient_name} ({self.phone_number}) - {self.get_status_display()} [{self.practice.name}]"

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read', 'updated_at'])

    def withdraw_consent(self, reason="", performed_by=None):
        """Revoke all consent channels and log activity."""
        self.consent_withdrawn = True
        self.consent_withdrawn_at = timezone.now()
        self.consent_withdrawn_reason = reason
        self.whatsapp_opt_in = False
        self.call_opt_in = False
        self.sms_opt_in = False
        self.email_opt_in = False
        self.save(update_fields=[
            'consent_withdrawn',
            'consent_withdrawn_at',
            'consent_withdrawn_reason',
            'whatsapp_opt_in',
            'call_opt_in',
            'sms_opt_in',
            'email_opt_in',
            'updated_at'
        ])
        LeadActivity.objects.create(
            practice=self.practice,
            lead=self,
            performed_by=performed_by,
            activity_type=LeadActivity.TYPE_CONSENT_CHANGE,
            note=f"Consent withdrawn. Reason: {reason or 'Patient requested opt-out'}"
        )


class LeadActivity(TenantAwareModel):
    """
    Timeline audit trail for lead interactions, status changes,
    staff notes, calls logged, and consent updates.
    """
    TYPE_STATUS_CHANGE = 'status_change'
    TYPE_NOTE = 'note_added'
    TYPE_CALL = 'call_logged'
    TYPE_WHATSAPP = 'whatsapp_sent'
    TYPE_EMAIL = 'email_sent'
    TYPE_ASSIGNMENT = 'assignment'
    TYPE_CONSENT_CHANGE = 'consent_updated'

    ACTIVITY_CHOICES = [
        (TYPE_STATUS_CHANGE, 'Status Changed'),
        (TYPE_NOTE, 'Internal Note Added'),
        (TYPE_CALL, 'Phone Call Logged'),
        (TYPE_WHATSAPP, 'WhatsApp Message Sent'),
        (TYPE_EMAIL, 'Email Sent'),
        (TYPE_ASSIGNMENT, 'Lead Reassigned'),
        (TYPE_CONSENT_CHANGE, 'Consent Preferences Updated'),
    ]

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='activities')
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lead_activities',
        help_text="User who logged this note or changed the status (null if system/public)"
    )
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_CHOICES, default=TYPE_NOTE)
    previous_status = models.CharField(max_length=30, blank=True)
    new_status = models.CharField(max_length=30, blank=True)
    note = models.TextField(blank=True, help_text="Description, call outcome, staff note, or change explanation")
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional arbitrary metadata (duration, templates, etc.)")

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Lead Activity'
        verbose_name_plural = 'Lead Activities'

    def __str__(self):
        return f"{self.get_activity_type_display()} on {self.lead.patient_name} at {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class ClickEvent(TenantAwareModel):
    """
    Tracking for Call and WhatsApp click events from clinic websites,
    doctor profiles, and marketing landing pages.
    """
    TYPE_CALL_CLICK = 'call_click'
    TYPE_WHATSAPP_CLICK = 'whatsapp_click'
    TYPE_BOOKING_CTA = 'booking_cta_click'
    TYPE_DIRECTIONS = 'directions_click'
    TYPE_SHARE = 'share_click'

    EVENT_CHOICES = [
        (TYPE_CALL_CLICK, 'Phone Call Button Clicked'),
        (TYPE_WHATSAPP_CLICK, 'WhatsApp Chat Button Clicked'),
        (TYPE_BOOKING_CTA, 'Book Appointment CTA Clicked'),
        (TYPE_DIRECTIONS, 'Get Directions / Maps Clicked'),
        (TYPE_SHARE, 'Share Button Clicked'),
    ]

    website = models.ForeignKey(
        'websites.ClinicWebsite',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='click_events'
    )
    event_type = models.CharField(max_length=30, choices=EVENT_CHOICES, db_index=True)
    target_phone = models.CharField(max_length=50, blank=True, help_text="The phone or WhatsApp number targeted by the click")
    doctor_id = models.UUIDField(null=True, blank=True, help_text="ID of doctor card if clicked on specific practitioner")
    doctor_name = models.CharField(max_length=255, blank=True)
    service_name = models.CharField(max_length=255, blank=True)

    # Attribution & visitor context
    page_url = models.TextField(blank=True, help_text="Page URL where the click event occurred")
    referrer = models.TextField(blank=True)
    utm_source = models.CharField(max_length=100, blank=True)
    utm_medium = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=150, blank=True)
    visitor_id = models.CharField(max_length=100, blank=True, help_text="Anonymous visitor session/cookie identifier")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_type = models.CharField(max_length=50, blank=True, help_text="mobile, desktop, tablet")

    # Optional link to a created or existing Lead
    lead = models.ForeignKey(
        Lead,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='click_events',
        help_text="Associated Lead if the click was converted or visitor provided phone"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Click Event'
        verbose_name_plural = 'Click Events'
        indexes = [
            models.Index(fields=['practice', 'event_type']),
            models.Index(fields=['practice', 'created_at']),
        ]

    def __str__(self):
        return f"{self.get_event_type_display()} on {self.practice.name} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"

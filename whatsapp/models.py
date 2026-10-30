import re
import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from practices.models import TenantAwareModel


def normalize_phone_number(phone: str) -> str:
    """
    Normalizes phone numbers to standard E.164 international format.
    Strips whitespace, parentheses, dashes, and ensures a leading '+' sign.
    Defaults to India (+91) if a 10-digit mobile is provided without country code.
    """
    if not phone:
        return ""
    clean = re.sub(r'[\s\-\(\)]', '', str(phone).strip())
    if clean.startswith('+'):
        return clean
    if clean.startswith('00'):
        return f"+{clean[2:]}"
    if len(clean) == 10 and clean[0] in '6789':
        return f"+91{clean}"
    if len(clean) == 12 and clean.startswith('91'):
        return f"+{clean}"
    return f"+{clean}"


class WhatsAppConfig(TenantAwareModel):
    """
    Practice-level WhatsApp Business configuration, provider credentials,
    and automation toggles.
    """
    PROVIDER_META = 'meta_cloud_api'
    PROVIDER_TWILIO = 'twilio'
    PROVIDER_GUPSHUP = 'gupshup'
    PROVIDER_MOCK = 'mock_simulator'

    PROVIDER_CHOICES = [
        (PROVIDER_META, 'Meta WhatsApp Cloud API'),
        (PROVIDER_TWILIO, 'Twilio WhatsApp API'),
        (PROVIDER_GUPSHUP, 'Gupshup Enterprise WhatsApp'),
        (PROVIDER_MOCK, 'Mock Simulator (Testing & Local Dev)'),
    ]

    provider = models.CharField(
        max_length=50,
        choices=PROVIDER_CHOICES,
        default=PROVIDER_MOCK,
        help_text="WhatsApp gateway provider"
    )
    phone_number_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Meta Phone Number ID or Twilio Channel ID"
    )
    waba_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="WhatsApp Business Account (WABA) ID"
    )
    access_token = models.TextField(
        blank=True,
        help_text="Permanent System User Token or API Secret Key"
    )
    webhook_verify_token = models.CharField(
        max_length=128,
        blank=True,
        help_text="Secret token for verifying inbound Meta webhooks"
    )
    display_phone_number = models.CharField(
        max_length=30,
        blank=True,
        help_text="Verified clinic WhatsApp sender number (e.g. +919876543210)"
    )
    business_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Official clinic WhatsApp display brand name"
    )

    # Automation Toggles
    is_enabled = models.BooleanField(
        default=True,
        help_text="Master toggle for all outbound WhatsApp automations"
    )
    auto_confirmation_enabled = models.BooleanField(
        default=True,
        help_text="Automatically send WhatsApp confirmation when booking is confirmed"
    )
    auto_reminders_enabled = models.BooleanField(
        default=True,
        help_text="Automatically schedule 24-hour and 2-hour consultation reminders"
    )
    lead_auto_reply_enabled = models.BooleanField(
        default=True,
        help_text="Send immediate WhatsApp welcome acknowledgment to fresh inquiries"
    )
    post_visit_review_enabled = models.BooleanField(
        default=True,
        help_text="Send automated Google review request after appointment is completed"
    )
    daily_send_limit = models.PositiveIntegerField(
        default=1000,
        help_text="Maximum messages permitted per 24 hours to prevent spam flagging"
    )

    class Meta:
        verbose_name = 'WhatsApp Configuration'
        verbose_name_plural = 'WhatsApp Configurations'

    def __str__(self):
        status = "Active" if self.is_enabled else "Disabled"
        return f"{self.practice.name} - WhatsApp ({self.get_provider_display()} | {status})"

    def save(self, *args, **kwargs):
        if not self.webhook_verify_token:
            self.webhook_verify_token = f"cr_wh_{uuid.uuid4().hex[:16]}"
        super().save(*args, **kwargs)


class WhatsAppTemplate(TenantAwareModel):
    """
    Message templates compliant with Meta WhatsApp Cloud API standards.
    Supports dynamic parameter replacement and practice-level overrides.
    """
    CATEGORY_UTILITY = 'UTILITY'
    CATEGORY_MARKETING = 'MARKETING'
    CATEGORY_AUTHENTICATION = 'AUTHENTICATION'

    CATEGORY_CHOICES = [
        (CATEGORY_UTILITY, 'Utility (Appointment Confirmations & Reminders)'),
        (CATEGORY_MARKETING, 'Marketing (Promotions & GBP Review Requests)'),
        (CATEGORY_AUTHENTICATION, 'Authentication (OTP / Verification)'),
    ]

    STATUS_APPROVED = 'APPROVED'
    STATUS_PENDING = 'PENDING'
    STATUS_REJECTED = 'REJECTED'
    STATUS_PAUSED = 'PAUSED'

    STATUS_CHOICES = [
        (STATUS_APPROVED, 'Approved by Meta'),
        (STATUS_PENDING, 'Pending Meta Approval'),
        (STATUS_REJECTED, 'Rejected by Meta'),
        (STATUS_PAUSED, 'Paused'),
    ]

    HEADER_NONE = 'none'
    HEADER_TEXT = 'text'
    HEADER_IMAGE = 'image'

    HEADER_CHOICES = [
        (HEADER_NONE, 'None'),
        (HEADER_TEXT, 'Text Header'),
        (HEADER_IMAGE, 'Image Header'),
    ]

    template_name = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Unique slug identifier (e.g. appointment_confirmation_slot)"
    )
    title = models.CharField(
        max_length=200,
        help_text="Human-readable title (e.g. Appointment Confirmation - Slot Mode)"
    )
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_UTILITY
    )
    language = models.CharField(
        max_length=15,
        default='en_US',
        help_text="BCP 47 language code (e.g. en_US, hi, te, ta)"
    )
    meta_template_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Remote ID from Meta Business Manager"
    )
    meta_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_APPROVED
    )

    header_type = models.CharField(
        max_length=20,
        choices=HEADER_CHOICES,
        default=HEADER_NONE
    )
    header_text = models.CharField(max_length=100, blank=True)
    body_text = models.TextField(
        help_text="Template body with placeholders: e.g. {{1}}, {{2}} or {{patient_name}}"
    )
    footer_text = models.CharField(
        max_length=100,
        blank=True,
        default="Reply STOP to unsubscribe",
        help_text="Mandatory compliance opt-out footer"
    )
    buttons = models.JSONField(
        default=list,
        blank=True,
        help_text="Interactive buttons: Quick Reply, URL CTA, or Phone Call"
    )
    variable_mapping = models.JSONField(
        default=dict,
        blank=True,
        help_text="Mapping from index or token to context key (e.g. {'1': 'patient_name'})"
    )

    is_active = models.BooleanField(default=True)
    is_system_default = models.BooleanField(
        default=False,
        help_text="Standard template provided out of the box by ClinicRise"
    )

    class Meta:
        ordering = ['category', 'template_name']
        unique_together = ('practice', 'template_name', 'language')
        verbose_name = 'WhatsApp Template'
        verbose_name_plural = 'WhatsApp Templates'

    def __str__(self):
        default_tag = " (Default)" if self.is_system_default else ""
        return f"{self.title} [{self.template_name} - {self.language}]{default_tag}"


class WhatsAppOptOut(TenantAwareModel):
    """
    Patient opt-out registry enforcing compliance with WhatsApp Business Policy,
    TRAI / DND, TCPA, and India DPDP Act.
    """
    REASON_KEYWORD_STOP = 'keyword_stop'
    REASON_PATIENT_REQUEST = 'patient_request'
    REASON_STAFF_MANUAL = 'staff_manual'
    REASON_DELIVERY_BOUNCE = 'delivery_bounce'
    REASON_OTHER = 'other'

    REASON_CHOICES = [
        (REASON_KEYWORD_STOP, 'Inbound STOP / Opt-Out Keyword'),
        (REASON_PATIENT_REQUEST, 'Patient Verbal / Written Request'),
        (REASON_STAFF_MANUAL, 'Frontdesk Receptionist Manual Toggle'),
        (REASON_DELIVERY_BOUNCE, 'Repeated Delivery Bounce / Invalid Number'),
        (REASON_OTHER, 'Other Compliance Withdrawal'),
    ]

    SOURCE_WHATSAPP = 'inbound_whatsapp'
    SOURCE_WEB_FORM = 'web_form'
    SOURCE_RECEPTION = 'reception_desk'
    SOURCE_PATIENT_PORTAL = 'patient_portal'
    SOURCE_API = 'api'

    SOURCE_CHOICES = [
        (SOURCE_WHATSAPP, 'Inbound WhatsApp Message'),
        (SOURCE_WEB_FORM, 'Website Privacy Form'),
        (SOURCE_RECEPTION, 'Frontdesk / Reception'),
        (SOURCE_PATIENT_PORTAL, 'Patient Portal'),
        (SOURCE_API, 'API / Integration'),
    ]

    phone_number = models.CharField(
        max_length=30,
        db_index=True,
        help_text="Normalized E.164 patient phone number"
    )
    patient_name = models.CharField(max_length=200, blank=True)
    reason = models.CharField(max_length=50, choices=REASON_CHOICES, default=REASON_KEYWORD_STOP)
    reason_notes = models.TextField(blank=True)
    is_opted_out = models.BooleanField(
        default=True,
        db_index=True,
        help_text="True if currently unsubscribed from WhatsApp communications"
    )
    opted_out_at = models.DateTimeField(default=timezone.now)
    opted_in_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp of re-subscription if opted back in")
    source_channel = models.CharField(max_length=40, choices=SOURCE_CHOICES, default=SOURCE_WHATSAPP)

    class Meta:
        ordering = ['-opted_out_at']
        unique_together = ('practice', 'phone_number')
        indexes = [
            models.Index(fields=['practice', 'phone_number', 'is_opted_out']),
        ]
        verbose_name = 'WhatsApp Opt-Out'
        verbose_name_plural = 'WhatsApp Opt-Outs'

    def __str__(self):
        status = "OPTED OUT" if self.is_opted_out else "ACTIVE (Re-opted In)"
        return f"{self.phone_number} - {status} ({self.practice.name})"

    def save(self, *args, **kwargs):
        self.phone_number = normalize_phone_number(self.phone_number)
        super().save(*args, **kwargs)


class WhatsAppReminder(TenantAwareModel):
    """
    Queue of automated reminders for upcoming appointments and lead follow-ups.
    """
    TYPE_APPT_24H = 'appointment_24h'
    TYPE_APPT_2H = 'appointment_2h'
    TYPE_APPT_DAY_OF = 'appointment_day_of'
    TYPE_LEAD_FOLLOW_UP = 'lead_follow_up'
    TYPE_POST_VISIT_REVIEW = 'post_visit_review'

    TYPE_CHOICES = [
        (TYPE_APPT_24H, '24-Hour Advance Appointment Reminder'),
        (TYPE_APPT_2H, '2-Hour Immediate Consultation Reminder'),
        (TYPE_APPT_DAY_OF, 'Day-of Morning Consultation Reminder'),
        (TYPE_LEAD_FOLLOW_UP, '24-Hour Lead Follow-up Reminder'),
        (TYPE_POST_VISIT_REVIEW, 'Post-Consultation Google Review Request'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_SENT = 'sent'
    STATUS_CANCELLED = 'cancelled'
    STATUS_FAILED = 'failed'
    STATUS_SKIPPED_OPT_OUT = 'skipped_opt_out'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Scheduled / Pending Dispatch'),
        (STATUS_SENT, 'Dispatched Successfully'),
        (STATUS_CANCELLED, 'Cancelled (Rescheduled or Cancelled Visit)'),
        (STATUS_FAILED, 'Failed to Dispatch'),
        (STATUS_SKIPPED_OPT_OUT, 'Skipped (Patient Opted Out)'),
    ]

    booking = models.ForeignKey(
        'bookings.BookingRequest',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='whatsapp_reminders',
        help_text="Target appointment for this reminder"
    )
    lead = models.ForeignKey(
        'leads.Lead',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='whatsapp_reminders',
        help_text="Target inquiry for lead follow-up"
    )
    reminder_type = models.CharField(max_length=40, choices=TYPE_CHOICES, db_index=True)
    scheduled_for = models.DateTimeField(db_index=True, help_text="When reminder should trigger")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['scheduled_for']
        indexes = [
            models.Index(fields=['practice', 'status', 'scheduled_for']),
            models.Index(fields=['practice', 'booking', 'reminder_type']),
        ]
        verbose_name = 'WhatsApp Reminder'
        verbose_name_plural = 'WhatsApp Reminders'

    def __str__(self):
        target = self.booking.booking_reference if self.booking else f"Lead #{self.lead_id}"
        return f"{self.get_reminder_type_display()} for {target} [{self.get_status_display()}]"


def generate_whatsapp_message_id():
    """Generates unique internal tracking ID for WhatsApp message log."""
    return f"msg_{uuid.uuid4().hex}"


class WhatsAppMessageLog(TenantAwareModel):
    """
    Complete audit and delivery log for every inbound and outbound WhatsApp message.
    Tracks provider delivery receipts (sent, delivered, read, failed).
    """
    DIRECTION_OUTBOUND = 'outbound'
    DIRECTION_INBOUND = 'inbound'

    DIRECTION_CHOICES = [
        (DIRECTION_OUTBOUND, 'Outbound (Sent to Patient)'),
        (DIRECTION_INBOUND, 'Inbound (Received from Patient)'),
    ]

    STATUS_QUEUED = 'queued'
    STATUS_SENT = 'sent'
    STATUS_DELIVERED = 'delivered'
    STATUS_READ = 'read'
    STATUS_FAILED = 'failed'
    STATUS_BLOCKED_OPT_OUT = 'blocked_opt_out'

    STATUS_CHOICES = [
        (STATUS_QUEUED, 'Queued for Delivery'),
        (STATUS_SENT, 'Sent by Gateway'),
        (STATUS_DELIVERED, 'Delivered to Recipient Device'),
        (STATUS_READ, 'Read / Opened by Recipient'),
        (STATUS_FAILED, 'Delivery Failed'),
        (STATUS_BLOCKED_OPT_OUT, 'Blocked by Opt-Out Registry'),
    ]

    message_id = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        default=generate_whatsapp_message_id,
        help_text="Internal ClinicRise unique message tracking ID"
    )
    provider_message_id = models.CharField(
        max_length=128,
        blank=True,
        db_index=True,
        help_text="External message ID returned by WhatsApp provider (e.g. wamid.HBgM...)"
    )
    direction = models.CharField(
        max_length=20,
        choices=DIRECTION_CHOICES,
        default=DIRECTION_OUTBOUND,
        db_index=True
    )
    recipient_phone = models.CharField(
        max_length=30,
        db_index=True,
        help_text="Normalized recipient mobile number (E.164)"
    )
    recipient_name = models.CharField(max_length=200, blank=True)
    sender_phone = models.CharField(max_length=30, blank=True)

    template = models.ForeignKey(
        WhatsAppTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='message_logs'
    )
    template_name = models.CharField(max_length=100, blank=True)
    message_body = models.TextField(help_text="Rendered message text")
    parameters = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=STATUS_SENT,
        db_index=True
    )

    # Context Relationships
    booking = models.ForeignKey(
        'bookings.BookingRequest',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='whatsapp_messages'
    )
    lead = models.ForeignKey(
        'leads.Lead',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='whatsapp_messages'
    )
    reminder = models.ForeignKey(
        WhatsAppReminder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='message_logs'
    )

    error_code = models.CharField(max_length=50, blank=True)
    error_message = models.TextField(blank=True)
    cost_tier = models.CharField(max_length=30, default='utility')

    # Status Timestamps
    sent_at = models.DateTimeField(default=timezone.now, db_index=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['practice', 'status']),
            models.Index(fields=['practice', 'recipient_phone']),
            models.Index(fields=['practice', 'direction', 'sent_at']),
            models.Index(fields=['provider_message_id']),
        ]
        verbose_name = 'WhatsApp Message Log'
        verbose_name_plural = 'WhatsApp Message Logs'

    def __str__(self):
        return f"[{self.direction.upper()}] {self.recipient_phone} - {self.get_status_display()} ({self.template_name or 'custom'})"

    def save(self, *args, **kwargs):
        self.recipient_phone = normalize_phone_number(self.recipient_phone)
        super().save(*args, **kwargs)

import hashlib
import json
import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from practices.models import TenantAwareModel


class AuditLog(TenantAwareModel):
    """
    Immutable compliance & security audit trail.
    Records authentication events, role changes, PHI/patient data views,
    consent updates, content approvals, financial transactions, and rate limits.
    """
    CATEGORY_AUTH = 'auth'
    CATEGORY_RBAC = 'rbac'
    CATEGORY_PATIENT_PRIVACY = 'patient_privacy'
    CATEGORY_CONSENT = 'consent'
    CATEGORY_CLINICAL = 'clinical'
    CATEGORY_BILLING = 'billing'
    CATEGORY_BACKUP = 'backup'
    CATEGORY_SECURITY = 'security'

    CATEGORY_CHOICES = [
        (CATEGORY_AUTH, 'Authentication & Access'),
        (CATEGORY_RBAC, 'Roles & Team Permissions'),
        (CATEGORY_PATIENT_PRIVACY, 'Patient Privacy & PHI Access'),
        (CATEGORY_CONSENT, 'Patient Consent Management'),
        (CATEGORY_CLINICAL, 'Clinical Content & Approvals'),
        (CATEGORY_BILLING, 'Billing & Financial Operations'),
        (CATEGORY_BACKUP, 'Data Backup & Disaster Recovery'),
        (CATEGORY_SECURITY, 'System Security & Rate Limiting'),
    ]

    SEVERITY_INFO = 'info'
    SEVERITY_WARNING = 'warning'
    SEVERITY_CRITICAL = 'critical'

    SEVERITY_CHOICES = [
        (SEVERITY_INFO, 'Informational'),
        (SEVERITY_WARNING, 'Security Warning'),
        (SEVERITY_CRITICAL, 'Critical Alert'),
    ]

    # Actor (User who triggered action; null for anonymous/system)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='security_audit_logs',
        help_text="User who initiated the action"
    )
    actor_email = models.CharField(max_length=255, blank=True, help_text="Cached email for historical permanence")
    actor_role = models.CharField(max_length=50, blank=True, help_text="Role at the time of the action")

    # Classification
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, db_index=True)
    action = models.CharField(max_length=100, db_index=True, help_text="e.g. auth.login, role.grant, patient.export")
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default=SEVERITY_INFO, db_index=True)

    # Target Entity
    target_model = models.CharField(max_length=100, blank=True, help_text="e.g. BookingRequest, Lead, WebsitePage")
    target_id = models.CharField(max_length=100, blank=True, help_text="UUID or identifier of affected entity")
    target_repr = models.CharField(max_length=255, blank=True, help_text="Human-readable representation")

    # Change Details & Audit Context
    description = models.TextField(help_text="Clear explanation of the action performed")
    changes = models.JSONField(default=dict, blank=True, help_text="Old vs New state dictionary")

    # Technical Network Context
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    request_path = models.CharField(max_length=500, blank=True)
    request_method = models.CharField(max_length=10, blank=True)
    status_code = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        indexes = [
            models.Index(fields=['practice', 'created_at']),
            models.Index(fields=['practice', 'category']),
            models.Index(fields=['practice', 'action']),
            models.Index(fields=['practice', 'severity']),
            models.Index(fields=['practice', 'actor']),
        ]

    def __str__(self):
        return f"[{self.severity.upper()}] {self.action} by {self.actor_email or 'System'} at {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class ConsentRecord(TenantAwareModel):
    """
    Cryptographically verifiable patient consent management (DPDP Act / GDPR / HIPAA).
    Records informed consent across marketing, teleconsultation, procedures,
    data sharing, and messaging channels.
    """
    TYPE_TELECONSULTATION = 'teleconsultation'
    TYPE_MARKETING = 'marketing'
    TYPE_TREATMENT_PROCEDURE = 'treatment_procedure'
    TYPE_RECORDS_SHARING = 'records_sharing'
    TYPE_WHATSAPP_NOTIFICATIONS = 'whatsapp_notifications'
    TYPE_SMS_NOTIFICATIONS = 'sms_notifications'
    TYPE_GENERAL_INTAKE = 'general_intake'

    TYPE_CHOICES = [
        (TYPE_TELECONSULTATION, 'Telemedicine & Video Consultation Recording'),
        (TYPE_MARKETING, 'Promotional & Educational Health Communications'),
        (TYPE_TREATMENT_PROCEDURE, 'Informed Clinical Procedure / Surgery Consent'),
        (TYPE_RECORDS_SHARING, 'Sharing Health Records with Diagnostic Labs & Specialists'),
        (TYPE_WHATSAPP_NOTIFICATIONS, 'WhatsApp Reminders & Care Updates'),
        (TYPE_SMS_NOTIFICATIONS, 'SMS Alerts & Reminders'),
        (TYPE_GENERAL_INTAKE, 'General Clinic Intake & Privacy Terms'),
    ]

    STATUS_GRANTED = 'granted'
    STATUS_WITHDRAWN = 'withdrawn'
    STATUS_EXPIRED = 'expired'

    STATUS_CHOICES = [
        (STATUS_GRANTED, 'Granted / Active'),
        (STATUS_WITHDRAWN, 'Revoked / Withdrawn'),
        (STATUS_EXPIRED, 'Expired'),
    ]

    patient_identifier = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Phone number (+91...), email, or patient hospital ID"
    )
    patient_name = models.CharField(max_length=200, blank=True)
    consent_type = models.CharField(max_length=50, choices=TYPE_CHOICES, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_GRANTED, db_index=True)

    # Disclosure & Verification
    consent_text = models.TextField(help_text="Exact legal disclosure / terms shown to the patient")
    version = models.CharField(max_length=20, default='1.0', help_text="Version of clinic terms agreed upon")
    audit_hash = models.CharField(
        max_length=64,
        editable=False,
        db_index=True,
        help_text="SHA-256 cryptographic signature of agreement"
    )

    # Technical Context
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_fingerprint = models.CharField(max_length=128, blank=True)
    source_url = models.URLField(max_length=500, blank=True)

    # Lifecycle
    granted_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    withdrawn_reason = models.TextField(blank=True)
    withdrawn_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='revoked_consents'
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Consent Record'
        verbose_name_plural = 'Consent Records'
        indexes = [
            models.Index(fields=['practice', 'patient_identifier']),
            models.Index(fields=['practice', 'consent_type', 'status']),
            models.Index(fields=['practice', 'created_at']),
        ]

    def __str__(self):
        return f"{self.patient_identifier} - {self.get_consent_type_display()} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.audit_hash:
            self.audit_hash = self.generate_audit_hash()
        super().save(*args, **kwargs)

    def generate_audit_hash(self) -> str:
        """Computes an immutable SHA-256 checksum over the consent terms."""
        payload = f"{self.practice_id}:{self.patient_identifier}:{self.consent_type}:{self.version}:{self.consent_text}:{self.granted_at.isoformat() if self.granted_at else ''}"
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()

    def withdraw(self, reason: str = "", performed_by=None):
        """Revokes consent and updates state."""
        self.status = self.STATUS_WITHDRAWN
        self.withdrawn_at = timezone.now()
        self.withdrawn_reason = reason or "Patient requested opt-out"
        self.withdrawn_by = performed_by
        self.save(update_fields=['status', 'withdrawn_at', 'withdrawn_reason', 'withdrawn_by', 'updated_at'])


class BackupRecord(TenantAwareModel):
    """
    On-demand and automated practice database snapshots.
    Preserves clinic configuration, websites, pages, blogs, leads, bookings, and consent logs.
    """
    TYPE_MANUAL = 'manual'
    TYPE_AUTOMATED = 'automated'
    TYPE_PRE_UPDATE = 'pre_update'

    TYPE_CHOICES = [
        (TYPE_MANUAL, 'Manual Practice Snapshot'),
        (TYPE_AUTOMATED, 'Automated Scheduled Backup'),
        (TYPE_PRE_UPDATE, 'Pre-System Update Snapshot'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_EXPIRED = 'expired'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Generating Snapshot...'),
        (STATUS_COMPLETED, 'Completed & Integrity Verified'),
        (STATUS_FAILED, 'Generation Failed'),
        (STATUS_EXPIRED, 'Expired & Purged'),
    ]

    backup_name = models.CharField(max_length=255)
    backup_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default=TYPE_MANUAL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_backups'
    )

    file_path = models.CharField(max_length=500, blank=True)
    file_size_bytes = models.BigIntegerField(default=0)
    records_count = models.PositiveIntegerField(default=0)
    checksum_sha256 = models.CharField(max_length=64, blank=True)
    manifest = models.JSONField(default=dict, blank=True, help_text="Summary of exported tables and record counts")
    expires_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Practice Backup'
        verbose_name_plural = 'Practice Backups'
        indexes = [
            models.Index(fields=['practice', 'created_at']),
            models.Index(fields=['practice', 'status']),
        ]

    def __str__(self):
        return f"{self.backup_name} ({self.get_status_display()}) - {self.practice.name}"

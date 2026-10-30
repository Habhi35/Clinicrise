from typing import Optional
from django.db.models import Q
from django.utils import timezone
from practices.models import Practice
from whatsapp.models import WhatsAppOptOut, WhatsAppReminder, normalize_phone_number


class WhatsAppOptOutService:
    """
    Compliance and consent engine for WhatsApp communications.
    Enforces DND / TRAI, TCPA, GDPR, and India DPDP Act regulations.
    Provides bidirectional synchronization with Security ConsentRecord and Leads CRM.
    """

    STOP_KEYWORDS = {
        'stop', 'unsubscribe', 'cancel', 'quit', 'end', 'optout',
        'opt-out', 'stopall', 'block', 'no', 'halt'
    }

    START_KEYWORDS = {
        'start', 'unstop', 'resume', 'subscribe', 'yes', 'rejoin'
    }

    @classmethod
    def is_opted_out(cls, practice: Practice, phone_number: str) -> bool:
        """
        Returns True if the recipient has opted out of WhatsApp messages
        or withdrawn communication consent.
        """
        norm_phone = normalize_phone_number(phone_number)
        if not norm_phone:
            return True

        # 1. Check dedicated WhatsAppOptOut table
        opt_record = WhatsAppOptOut.objects.filter(
            practice=practice,
            phone_number=norm_phone
        ).first()
        if opt_record is not None:
            return opt_record.is_opted_out

        # 2. Check Security ConsentRecord (latest record check)
        try:
            from security.models import ConsentRecord
            latest_consent = ConsentRecord.objects.filter(
                practice=practice,
                patient_identifier=norm_phone,
                consent_type=ConsentRecord.TYPE_WHATSAPP_NOTIFICATIONS
            ).order_by('-created_at').first()
            if latest_consent and latest_consent.status == ConsentRecord.STATUS_WITHDRAWN:
                return True
        except Exception:
            pass

        # 3. Check Leads CRM consent flags
        try:
            from leads.models import Lead
            withdrawn_lead = Lead.objects.filter(
                practice=practice,
                phone_number=norm_phone
            ).filter(
                Q(whatsapp_opt_in=False) | Q(consent_withdrawn=True)
            ).exists()
            if withdrawn_lead:
                return True
        except Exception:
            pass

        return False

    @classmethod
    def register_opt_out(
        cls,
        practice: Practice,
        phone_number: str,
        reason: str = WhatsAppOptOut.REASON_KEYWORD_STOP,
        source_channel: str = WhatsAppOptOut.SOURCE_WHATSAPP,
        patient_name: str = "",
        reason_notes: str = "",
        performed_by=None,
        request=None
    ) -> WhatsAppOptOut:
        """
        Registers a patient opt-out, revokes security consent, updates Lead CRM,
        and cancels pending scheduled reminders for this recipient.
        """
        norm_phone = normalize_phone_number(phone_number)
        now = timezone.now()

        opt_record, created = WhatsAppOptOut.objects.update_or_create(
            practice=practice,
            phone_number=norm_phone,
            defaults={
                "patient_name": patient_name or "",
                "reason": reason,
                "reason_notes": reason_notes,
                "is_opted_out": True,
                "opted_out_at": now,
                "source_channel": source_channel
            }
        )

        # 1. Sync Security ConsentRecord
        try:
            from security.services.consent_service import ConsentService
            from security.models import ConsentRecord
            revoked_count = ConsentService.withdraw_consent(
                practice=practice,
                patient_identifier=norm_phone,
                consent_type=ConsentRecord.TYPE_WHATSAPP_NOTIFICATIONS,
                reason=f"WhatsApp Opt-Out ({reason})",
                performed_by=performed_by,
                request=request
            )
            if not revoked_count:
                ConsentRecord.objects.create(
                    practice=practice,
                    patient_identifier=norm_phone,
                    patient_name=patient_name or "",
                    consent_type=ConsentRecord.TYPE_WHATSAPP_NOTIFICATIONS,
                    status=ConsentRecord.STATUS_WITHDRAWN,
                    consent_text="WhatsApp opt-out registered by recipient or staff.",
                    withdrawn_at=now,
                    withdrawn_reason=f"WhatsApp Opt-Out ({reason})",
                    withdrawn_by=performed_by
                )
        except Exception:
            pass

        # 2. Sync Leads CRM
        try:
            from leads.models import Lead
            leads = Lead.objects.filter(practice=practice, phone_number=norm_phone)
            for lead in leads:
                lead.withdraw_consent(
                    reason=f"WhatsApp opt-out: {reason}",
                    performed_by=performed_by
                )
        except Exception:
            pass

        # 3. Cancel pending reminders for this number
        WhatsAppReminder.objects.filter(
            practice=practice,
            status=WhatsAppReminder.STATUS_PENDING
        ).filter(
            Q(booking__phone_number=norm_phone) | Q(lead__phone_number=norm_phone)
        ).update(
            status=WhatsAppReminder.STATUS_SKIPPED_OPT_OUT,
            error_message="Skipped: Patient opted out of WhatsApp messaging"
        )

        # 4. Audit Log
        try:
            from security.services.audit_service import AuditService
            from security.models import AuditLog
            AuditService.log_action(
                practice=practice,
                action='whatsapp_opt_out_recorded',
                user=performed_by,
                resource_type='WhatsAppOptOut',
                resource_id=opt_record.id,
                details={
                    "phone_number": norm_phone,
                    "reason": reason,
                    "channel": source_channel
                },
                request=request
            )
        except Exception:
            pass

        return opt_record

    @classmethod
    def register_opt_in(
        cls,
        practice: Practice,
        phone_number: str,
        source_channel: str = WhatsAppOptOut.SOURCE_WHATSAPP,
        patient_name: str = "",
        performed_by=None,
        request=None
    ) -> WhatsAppOptOut:
        """
        Re-subscribes a patient to WhatsApp communications upon explicit keyword/request.
        """
        norm_phone = normalize_phone_number(phone_number)
        now = timezone.now()

        opt_record, created = WhatsAppOptOut.objects.update_or_create(
            practice=practice,
            phone_number=norm_phone,
            defaults={
                "patient_name": patient_name or "",
                "is_opted_out": False,
                "opted_in_at": now,
                "source_channel": source_channel
            }
        )

        # 1. Restore Security ConsentRecord
        try:
            from security.services.consent_service import ConsentService
            from security.models import ConsentRecord
            ConsentRecord.objects.filter(
                practice=practice,
                patient_identifier=norm_phone,
                consent_type=ConsentRecord.TYPE_WHATSAPP_NOTIFICATIONS,
                status=ConsentRecord.STATUS_WITHDRAWN
            ).update(status=ConsentRecord.STATUS_GRANTED)
            ConsentService.record_consent(
                practice=practice,
                data={
                    "patient_identifier": norm_phone,
                    "patient_name": patient_name,
                    "consent_type": ConsentRecord.TYPE_WHATSAPP_NOTIFICATIONS,
                    "consent_text": "I agree to receive appointment reminders and clinical updates via WhatsApp from ClinicRise.",
                    "version": "1.0",
                    "source_url": "whatsapp_opt_in"
                },
                request=request
            )
        except Exception:
            pass

        # 2. Restore Leads CRM opt-in
        try:
            from leads.models import Lead
            Lead.objects.filter(practice=practice, phone_number=norm_phone).update(
                whatsapp_opt_in=True,
                consent_withdrawn=False,
                updated_at=now
            )
        except Exception:
            pass

        return opt_record

    @classmethod
    def detect_keyword(cls, message_text: str) -> Optional[str]:
        """
        Detects inbound compliance keywords ('opt_out', 'opt_in', or None).
        Handles punctuation, leading/trailing whitespace, and single word messages.
        """
        if not message_text:
            return None
        clean = message_text.strip().lower()
        # Remove punctuation like periods or exclamation marks
        clean = "".join(c for c in clean if c.isalnum() or c in (' ', '-'))
        words = clean.split()
        if not words:
            return None

        # Check single-word command or first word command
        first_word = words[0]
        if first_word in cls.STOP_KEYWORDS or clean in cls.STOP_KEYWORDS:
            return 'opt_out'
        if first_word in cls.START_KEYWORDS or clean in cls.START_KEYWORDS:
            return 'opt_in'

        return None

    @classmethod
    def get_opt_out_acknowledgment(cls, clinic_name: str) -> str:
        return (
            f"You have been successfully unsubscribed from WhatsApp notifications from {clinic_name}. "
            "You will not receive any further automated reminders. "
            "Reply START at any time to resume communications."
        )

    @classmethod
    def get_opt_in_acknowledgment(cls, clinic_name: str) -> str:
        return (
            f"Welcome back! You have resubscribed to WhatsApp notifications from {clinic_name}. "
            "You will now receive your appointment reminders and clinical updates. "
            "Reply STOP at any time to unsubscribe."
        )

from django.db.models import Q
from django.utils import timezone
from practices.models import Practice
from security.models import AuditLog, ConsentRecord
from security.services.audit_service import AuditService


class ConsentService:
    """
    Healthcare consent governance engine (DPDP Act / GDPR / HIPAA).
    Manages explicit consent tracking, immutable audit hashing, and patient opt-outs.
    """

    @classmethod
    def record_consent(cls, practice: Practice, data: dict, request=None) -> ConsentRecord:
        """
        Creates an immutable, cryptographically hashed ConsentRecord.
        """
        ip_address = None
        user_agent = ""
        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0].strip()
            else:
                ip_address = request.META.get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_AGENT', '')

        patient_identifier = (data.get('patient_identifier') or '').strip()
        consent_type = data.get('consent_type', ConsentRecord.TYPE_GENERAL_INTAKE)
        consent_text = (data.get('consent_text') or '').strip() or "Standard clinical intake and communications consent."

        record = ConsentRecord.objects.create(
            practice=practice,
            patient_identifier=patient_identifier,
            patient_name=(data.get('patient_name') or '').strip(),
            consent_type=consent_type,
            status=ConsentRecord.STATUS_GRANTED,
            consent_text=consent_text,
            version=data.get('version', '1.0'),
            ip_address=ip_address or data.get('ip_address'),
            user_agent=user_agent or data.get('user_agent', ''),
            device_fingerprint=data.get('device_fingerprint', ''),
            source_url=data.get('source_url', ''),
            granted_at=timezone.now(),
            expires_at=data.get('expires_at'),
            metadata=data.get('metadata', {})
        )

        AuditService.log(
            practice=practice,
            action="consent.granted",
            category=AuditLog.CATEGORY_CONSENT,
            description=f"Consent granted for {patient_identifier} ({record.get_consent_type_display()}).",
            target_model="ConsentRecord",
            target_id=str(record.id),
            target_repr=patient_identifier,
            changes={"consent_type": consent_type, "audit_hash": record.audit_hash},
            request=request
        )

        return record

    @classmethod
    def withdraw_consent(
        cls,
        practice: Practice,
        patient_identifier: str,
        consent_type: str = None,
        reason: str = "",
        performed_by=None,
        request=None
    ) -> list[ConsentRecord]:
        """
        Revokes consent for a patient and records audit logs.
        """
        qs = ConsentRecord.objects.filter(
            practice=practice,
            patient_identifier=patient_identifier.strip(),
            status=ConsentRecord.STATUS_GRANTED
        )
        if consent_type:
            qs = qs.filter(consent_type=consent_type)

        revoked = []
        for record in qs:
            record.withdraw(reason=reason, performed_by=performed_by)
            revoked.append(record)

            AuditService.log(
                practice=practice,
                action="consent.withdrawn",
                category=AuditLog.CATEGORY_CONSENT,
                description=f"Consent withdrawn for {patient_identifier} ({record.get_consent_type_display()}). Reason: {reason or 'Patient requested opt-out'}",
                actor=performed_by,
                severity=AuditLog.SEVERITY_WARNING,
                target_model="ConsentRecord",
                target_id=str(record.id),
                target_repr=patient_identifier,
                changes={"status": ConsentRecord.STATUS_WITHDRAWN, "reason": reason},
                request=request
            )

        return revoked

    revoke_consent = withdraw_consent

    @classmethod
    def has_active_consent(cls, practice: Practice, patient_identifier: str, consent_type: str) -> bool:
        """
        Verifies if patient has granted active and unexpired consent.
        """
        now = timezone.now()
        return ConsentRecord.objects.filter(
            practice=practice,
            patient_identifier=patient_identifier.strip(),
            consent_type=consent_type,
            status=ConsentRecord.STATUS_GRANTED
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now)
        ).exists()

import logging
from practices.models import Practice, PracticeMembership
from security.models import AuditLog

logger = logging.getLogger(__name__)


class AuditService:
    """
    Centralized security and compliance audit logging service.
    Guarantees non-blocking execution so logging exceptions never disrupt business operations.
    """

    @classmethod
    def log(
        cls,
        practice: Practice,
        action: str,
        category: str,
        description: str,
        actor=None,
        severity: str = AuditLog.SEVERITY_INFO,
        target_model: str = "",
        target_id: str = "",
        target_repr: str = "",
        changes: dict = None,
        request=None
    ) -> AuditLog:
        """
        Creates an immutable AuditLog entry with technical and actor context.
        """
        try:
            actor_email = ""
            actor_role = ""
            ip_address = None
            user_agent = ""
            request_path = ""
            request_method = ""
            status_code = None

            # Resolve Actor
            if not actor and request and hasattr(request, 'user') and request.user.is_authenticated:
                actor = request.user

            if actor and actor.is_authenticated:
                actor_email = getattr(actor, 'email', '') or getattr(actor, 'phone_number', '')
                # Find role in this practice
                membership = PracticeMembership.objects.filter(
                    practice=practice,
                    user=actor,
                    is_active=True
                ).first()
                if membership:
                    actor_role = membership.role

            # Extract Network Headers
            if request:
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    ip_address = x_forwarded_for.split(',')[0].strip()
                else:
                    ip_address = request.META.get('REMOTE_ADDR')

                user_agent = request.META.get('HTTP_USER_AGENT', '')
                request_path = request.path or ''
                request_method = request.method or ''

            return AuditLog.objects.create(
                practice=practice,
                actor=actor if actor and actor.is_authenticated else None,
                actor_email=actor_email,
                actor_role=actor_role,
                category=category,
                action=action,
                severity=severity,
                target_model=target_model,
                target_id=str(target_id) if target_id else "",
                target_repr=target_repr,
                description=description,
                changes=changes or {},
                ip_address=ip_address,
                user_agent=user_agent,
                request_path=request_path,
                request_method=request_method,
                status_code=status_code,
            )
        except Exception as exc:
            logger.error(f"AuditService failed to record audit log for practice {practice.id}: {exc}", exc_info=True)
            return None

    @classmethod
    def log_auth(cls, practice: Practice, actor, action: str, description: str, request=None, success: bool = True):
        severity = AuditLog.SEVERITY_INFO if success else AuditLog.SEVERITY_WARNING
        return cls.log(
            practice=practice,
            action=action,
            category=AuditLog.CATEGORY_AUTH,
            description=description,
            actor=actor,
            severity=severity,
            request=request
        )

    @classmethod
    def log_role_change(cls, practice: Practice, actor, member_user, new_role: str, old_role: str = "", request=None):
        return cls.log(
            practice=practice,
            action="rbac.role_updated",
            category=AuditLog.CATEGORY_RBAC,
            description=f"Role for {member_user.email} changed from '{old_role}' to '{new_role}'.",
            actor=actor,
            severity=AuditLog.SEVERITY_WARNING,
            target_model="PracticeMembership",
            target_id=str(member_user.id),
            target_repr=member_user.email,
            changes={"previous_role": old_role, "new_role": new_role},
            request=request
        )

    @classmethod
    def log_phi_access(cls, practice: Practice, actor, patient_name: str, action: str, request=None):
        return cls.log(
            practice=practice,
            action=f"patient_privacy.{action}",
            category=AuditLog.CATEGORY_PATIENT_PRIVACY,
            description=f"Patient record for '{patient_name}' accessed ({action}).",
            actor=actor,
            severity=AuditLog.SEVERITY_INFO,
            target_model="PatientRecord",
            target_repr=patient_name,
            request=request
        )

    @classmethod
    def log_rate_limited(cls, practice: Practice, action: str, request=None):
        return cls.log(
            practice=practice,
            action="security.rate_limited",
            category=AuditLog.CATEGORY_SECURITY,
            description=f"Rate limit exceeded on action '{action}'. Access throttled.",
            severity=AuditLog.SEVERITY_WARNING,
            request=request
        )

    @classmethod
    def log_action(cls, practice: Practice, action: str, user=None, resource_type: str = "", resource_id="", details: dict = None, request=None):
        return cls.log(
            practice=practice,
            action=action,
            category=AuditLog.CATEGORY_CONSENT,
            description=f"Action '{action}' on {resource_type}.",
            actor=user,
            target_model=resource_type,
            target_id=str(resource_id),
            changes=details or {},
            request=request
        )


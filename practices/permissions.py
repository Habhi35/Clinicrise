import uuid
from rest_framework import permissions
from practices.models import PracticeMembership


def get_membership(user, practice):
    """Helper to fetch active membership for a user in a practice."""
    if not user.is_authenticated or not practice:
        return None
    return PracticeMembership.objects.filter(
        practice=practice,
        user=user,
        is_active=True
    ).first()


def resolve_request_membership(request, view):
    """
    Resolves the user's active PracticeMembership for the given request and view.
    Checks:
    1. Pre-resolved request.membership
    2. URL kwargs (practice_id or pk on PracticeDetailView)
    3. X-Practice-ID / HTTP_X_PRACTICE_ID header
    4. View pk
    5. Single active practice fallback
    """
    if not request.user or not request.user.is_authenticated:
        return None

    membership = getattr(request, 'membership', None)
    if membership and membership.is_active:
        return membership

    target_practice_id = view.kwargs.get('practice_id')
    if not target_practice_id and view.__class__.__name__ == 'PracticeDetailView':
        target_practice_id = view.kwargs.get('pk')

    if not target_practice_id:
        target_practice_id = (
            request.headers.get('X-Practice-ID')
            or request.META.get('HTTP_X_PRACTICE_ID')
            or view.kwargs.get('pk')
        )

    if target_practice_id:
        try:
            p_uuid = uuid.UUID(str(target_practice_id).strip())
            membership = PracticeMembership.objects.filter(
                practice_id=p_uuid,
                user=request.user,
                is_active=True
            ).select_related('practice').first()
            if membership:
                request.practice = membership.practice
                request.membership = membership
                return membership
            return None
        except (ValueError, TypeError):
            return None

    memberships = list(
        PracticeMembership.objects.filter(
            user=request.user,
            is_active=True,
            practice__is_active=True
        ).select_related('practice')[:2]
    )
    if len(memberships) == 1:
        request.practice = memberships[0].practice
        request.membership = memberships[0]
        return memberships[0]

    return None


class IsPracticeMember(permissions.BasePermission):
    """
    Requires the user to have an active membership in the current practice.
    Works with header-based active practice (`request.practice`, `X-Practice-ID`), view kwargs, or single practice membership.
    """
    message = "You are not an active member of this practice."

    def has_permission(self, request, view):
        return bool(resolve_request_membership(request, view))

    def has_object_permission(self, request, view, obj):
        practice = getattr(obj, 'practice', obj if hasattr(obj, 'memberships') else None)
        if not practice:
            return False
        return PracticeMembership.objects.filter(
            practice=practice,
            user=request.user,
            is_active=True
        ).exists()


class IsFrontdeskStaff(permissions.BasePermission):
    """
    Requires user to be Receptionist, Frontdesk Staff, Admin, or Owner.
    Permits patient check-in, registration, walk-in ticketing, frontdesk notes, and follow-ups.
    """
    message = "Only frontdesk receptionists and administrators have permission to perform this action."

    def has_permission(self, request, view):
        membership = resolve_request_membership(request, view)
        return bool(membership and membership.is_frontdesk)


class IsClinicalStaff(permissions.BasePermission):
    """
    Requires user to be a Clinical Assistant, Nurse, Doctor, Admin, or Owner.
    Permits recording patient vitals, intake triage, prep notes, and clinical follow-ups.
    """
    message = "Only clinical assistants, doctors, and practice administrators have permission to perform this action."

    def has_permission(self, request, view):
        membership = resolve_request_membership(request, view)
        return bool(membership and membership.is_clinical_staff)


class IsPracticeReceptionist(permissions.BasePermission):
    """Requires user to be a dedicated Receptionist or Staff."""
    message = "Only frontdesk receptionists have permission to perform this action."

    def has_permission(self, request, view):
        membership = resolve_request_membership(request, view)
        return bool(membership and membership.is_receptionist)


class IsPracticeAssistant(permissions.BasePermission):
    """Requires user to be a Clinical Assistant or Nurse."""
    message = "Only clinical assistants and nurses have permission to perform this action."

    def has_permission(self, request, view):
        membership = resolve_request_membership(request, view)
        return bool(membership and membership.is_assistant)


class IsPracticeDoctor(permissions.BasePermission):
    """
    Requires the user to be a Doctor, Admin, or Owner in the practice.
    """
    message = "Only medical practitioners and administrators have permission to perform this action."

    def has_permission(self, request, view):
        membership = resolve_request_membership(request, view)
        return bool(membership and membership.is_doctor)


class IsPracticeAdmin(permissions.BasePermission):
    """
    Requires the user to be a Practice Admin or Practice Owner.
    """
    message = "Only practice administrators or owners can perform this action."

    def has_permission(self, request, view):
        membership = resolve_request_membership(request, view)
        return bool(membership and membership.is_admin)


class IsPracticeOwner(permissions.BasePermission):
    """
    Requires the user to be the legal Owner of the practice.
    """
    message = "Only the practice owner can perform this action."

    def has_permission(self, request, view):
        membership = resolve_request_membership(request, view)
        return bool(membership and membership.is_owner)


class HasDoctorProfile(permissions.BasePermission):
    """
    Verifies that the user has an existing DoctorProfile.
    """
    message = "A registered Doctor profile is required to perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and hasattr(request.user, 'doctor_profile')
        )

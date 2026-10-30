from rest_framework import permissions
from practices.models import PracticeMembership


class RoleChecker:
    """
    Utility for evaluating user roles and granular permissions within a practice tenant.
    """

    @classmethod
    def get_membership(cls, user, practice) -> PracticeMembership:
        if not user or not user.is_authenticated or not practice:
            return None
        return PracticeMembership.objects.filter(
            practice=practice,
            user=user,
            is_active=True
        ).first()

    @classmethod
    def get_role(cls, user, practice) -> str:
        membership = cls.get_membership(user, practice)
        return membership.role if membership else ""

    @classmethod
    def has_role(cls, user, practice, allowed_roles: list) -> bool:
        membership = cls.get_membership(user, practice)
        return bool(membership and membership.role in allowed_roles)

    @classmethod
    def is_owner(cls, user, practice) -> bool:
        return cls.has_role(user, practice, [PracticeMembership.ROLE_OWNER])

    @classmethod
    def is_admin(cls, user, practice) -> bool:
        return cls.has_role(user, practice, [PracticeMembership.ROLE_OWNER, PracticeMembership.ROLE_ADMIN])

    @classmethod
    def is_doctor(cls, user, practice) -> bool:
        return cls.has_role(user, practice, [
            PracticeMembership.ROLE_OWNER,
            PracticeMembership.ROLE_ADMIN,
            PracticeMembership.ROLE_DOCTOR
        ])

    @classmethod
    def is_staff(cls, user, practice) -> bool:
        return cls.has_role(user, practice, [
            PracticeMembership.ROLE_OWNER,
            PracticeMembership.ROLE_ADMIN,
            PracticeMembership.ROLE_DOCTOR,
            PracticeMembership.ROLE_STAFF
        ])


def _extract_practice_from_request(request, view, obj=None):
    """Helper to resolve Practice tenant across headers, view kwargs, and objects."""
    if getattr(request, 'practice', None):
        return request.practice

    if obj:
        if hasattr(obj, 'practice'):
            return obj.practice
        if hasattr(obj, 'memberships'):
            return obj

    practice_id = view.kwargs.get('practice_id') or view.kwargs.get('pk')
    if practice_id:
        from practices.models import Practice
        try:
            return Practice.objects.filter(id=practice_id).first()
        except Exception:
            pass
    return None


class IsPracticeOwner(permissions.BasePermission):
    """Restricts access exclusively to the Practice Owner."""
    message = "Only the Practice Owner has authority to perform this operation."

    def has_permission(self, request, view):
        practice = _extract_practice_from_request(request, view)
        return RoleChecker.is_owner(request.user, practice)

    def has_object_permission(self, request, view, obj):
        practice = _extract_practice_from_request(request, view, obj)
        return RoleChecker.is_owner(request.user, practice)


class IsPracticeAdmin(permissions.BasePermission):
    """Restricts access to Practice Admins and Owners."""
    message = "Only Practice Administrators or Practice Owners have access to this resource."

    def has_permission(self, request, view):
        practice = _extract_practice_from_request(request, view)
        return RoleChecker.is_admin(request.user, practice)

    def has_object_permission(self, request, view, obj):
        practice = _extract_practice_from_request(request, view, obj)
        return RoleChecker.is_admin(request.user, practice)


class IsPracticeDoctor(permissions.BasePermission):
    """Restricts access to Doctors, Admins, and Owners."""
    message = "Medical practitioner or administrator credentials are required."

    def has_permission(self, request, view):
        practice = _extract_practice_from_request(request, view)
        return RoleChecker.is_doctor(request.user, practice)

    def has_object_permission(self, request, view, obj):
        practice = _extract_practice_from_request(request, view, obj)
        return RoleChecker.is_doctor(request.user, practice)


class IsPracticeStaff(permissions.BasePermission):
    """Requires any active membership in the practice."""
    message = "You are not an active member of this practice tenant."

    def has_permission(self, request, view):
        practice = _extract_practice_from_request(request, view)
        return RoleChecker.is_staff(request.user, practice)

    def has_object_permission(self, request, view, obj):
        practice = _extract_practice_from_request(request, view, obj)
        return RoleChecker.is_staff(request.user, practice)


class RequiresRoles:
    """Dynamic permission factory: RequiresRoles('owner', 'admin')"""
    def __init__(self, *roles):
        self.roles = roles

    def __call__(self):
        class DynamicRolePermission(permissions.BasePermission):
            message = f"Operation requires one of the following roles: {', '.join(self.roles)}"

            def has_permission(sub_self, request, view):
                practice = _extract_practice_from_request(request, view)
                return RoleChecker.has_role(request.user, practice, list(self.roles))

            def has_object_permission(sub_self, request, view, obj):
                practice = _extract_practice_from_request(request, view, obj)
                return RoleChecker.has_role(request.user, practice, list(self.roles))
        return DynamicRolePermission

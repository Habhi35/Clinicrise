from datetime import datetime
from django.utils import timezone
from rest_framework import permissions
from practices.models import PracticeMembership


def get_practice_subscription(practice):
    """Retrieves the active PracticeSubscription, initializing free trial if missing."""
    if not practice:
        return None
    if hasattr(practice, 'subscription') and practice.subscription:
        return practice.subscription
    from billing.services.billing_service import BillingService
    return BillingService.create_trial_subscription(practice)


def check_quota(practice, resource_type):
    """
    Checks if a practice is within its plan's quota limits for a specific resource.
    Returns: (is_allowed: bool, current_count: int, max_limit: int, message: str)
    """
    subscription = get_practice_subscription(practice)
    if not subscription:
        return False, 0, 0, "No active subscription found for practice."

    plan = subscription.plan

    if resource_type == 'doctors':
        current_count = PracticeMembership.objects.filter(
            practice=practice,
            role__in=[PracticeMembership.ROLE_DOCTOR, PracticeMembership.ROLE_OWNER],
            is_active=True
        ).count()
        limit = plan.max_doctors
    elif resource_type == 'staff':
        current_count = PracticeMembership.objects.filter(
            practice=practice,
            role=PracticeMembership.ROLE_STAFF,
            is_active=True
        ).count()
        limit = plan.max_staff
    elif resource_type == 'locations':
        try:
            from bookings.models import PracticeLocation
            current_count = PracticeLocation.objects.filter(practice=practice, is_active=True).count()
        except ImportError:
            current_count = 0
        limit = plan.max_locations
    elif resource_type == 'appointments_this_month':
        try:
            from bookings.models import Appointment
            now = timezone.now()
            start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            current_count = Appointment.objects.filter(practice=practice, created_at__gte=start_of_month).count()
        except ImportError:
            current_count = 0
        limit = plan.max_appointments_per_month
    else:
        return True, 0, -1, ""

    if limit == -1:
        return True, current_count, -1, ""

    if current_count >= limit:
        return (
            False,
            current_count,
            limit,
            f"You have reached your plan limit of {limit} {resource_type.replace('_', ' ')}. Upgrade your plan to add more."
        )

    return True, current_count, limit, ""


def check_feature(practice, feature_flag):
    """
    Checks if a specific feature toggle is unlocked on the practice's active plan.
    Returns: (is_allowed: bool, message: str)
    """
    subscription = get_practice_subscription(practice)
    if not subscription:
        return False, "No active subscription found."

    if not subscription.is_active_access:
        return False, "Your subscription is inactive or expired. Please renew your plan."

    plan = subscription.plan
    is_allowed = getattr(plan, feature_flag, False)
    if not is_allowed:
        feature_human = feature_flag.replace('_enabled', '').replace('_', ' ').title()
        return False, f"The '{feature_human}' feature is not included in your current '{plan.name}' plan. Please upgrade to unlock."

    return True, ""


class RequireSubscriptionFeature(permissions.BasePermission):
    """
    DRF Permission class enforcing feature entitlements.
    Usage:
        permission_classes = [IsAuthenticated, RequireSubscriptionFeature('teleconsultation_enabled')]
    """
    def __init__(self, feature_flag):
        self.feature_flag = feature_flag

    def __call__(self):
        return self

    def has_permission(self, request, view):
        practice = getattr(request, 'practice', None)
        if not practice:
            return True
        allowed, msg = check_feature(practice, self.feature_flag)
        self.message = msg
        return allowed

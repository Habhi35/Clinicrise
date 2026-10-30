import threading
import uuid
from django.utils.deprecation import MiddlewareMixin
from practices.models import PracticeMembership

_thread_locals = threading.local()


def get_current_practice():
    """Returns the current Practice tenant from thread-local storage."""
    return getattr(_thread_locals, 'practice', None)


def set_current_practice(practice):
    """Sets the current Practice tenant in thread-local storage."""
    _thread_locals.practice = practice


class TenantIsolationMiddleware(MiddlewareMixin):
    """
    Middleware enforcing multi-tenant isolation across ClinicRise.
    
    1. Inspects request header 'X-Practice-ID'.
    2. Validates that request.user holds an active PracticeMembership for that practice.
    3. Attaches 'request.practice' and 'request.membership' to the request object.
    4. Syncs the active practice to thread-local storage for model-level isolation.
    """

    def process_request(self, request):
        request.practice = None
        request.membership = None
        set_current_practice(None)

        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return

        practice_id_header = request.headers.get('X-Practice-ID') or request.META.get('HTTP_X_PRACTICE_ID')

        if practice_id_header:
            try:
                practice_uuid = uuid.UUID(practice_id_header.strip())
                membership = (
                    PracticeMembership.objects.filter(
                        practice_id=practice_uuid,
                        user=request.user,
                        is_active=True,
                        practice__is_active=True
                    )
                    .select_related('practice')
                    .first()
                )
                if membership:
                    request.practice = membership.practice
                    request.membership = membership
                    set_current_practice(membership.practice)
            except (ValueError, TypeError):
                pass
        else:
            # If no header provided and user has only ONE active practice membership, auto-select it
            memberships = list(
                PracticeMembership.objects.filter(
                    user=request.user,
                    is_active=True,
                    practice__is_active=True
                )
                .select_related('practice')[:2]
            )
            if len(memberships) == 1:
                request.practice = memberships[0].practice
                request.membership = memberships[0]
                set_current_practice(memberships[0].practice)

    def process_response(self, request, response):
        # Clear thread-local reference at request completion
        set_current_practice(None)
        return response

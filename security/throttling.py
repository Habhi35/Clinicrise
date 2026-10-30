from rest_framework.throttling import SimpleRateThrottle
from security.services.audit_service import AuditService


class SecurityAuditThrottleMixin:
    """Logs rate-limit throttling violations to AuditLog."""
    def throttle_failure(self):
        try:
            practice = getattr(self, 'practice', None)
            request = getattr(self, 'request', None)
            if not practice and request:
                practice = getattr(request, 'practice', None)

            if practice:
                AuditService.log_rate_limited(
                    practice=practice,
                    action=f"rate_limit.{self.scope or 'endpoint'}",
                    request=request
                )
        except Exception:
            pass
        return super().throttle_failure()


class AuthRateThrottle(SecurityAuditThrottleMixin, SimpleRateThrottle):
    """
    Limits authentication attempts (OTP requests, logins) to prevent brute-force attacks.
    Default: 5 requests / minute per IP or identifier.
    """
    scope = 'auth_attempt'

    def get_cache_key(self, request, view):
        self.request = request
        if request.user.is_authenticated:
            ident = str(request.user.id)
        else:
            ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }


class PublicInquiryThrottle(SecurityAuditThrottleMixin, SimpleRateThrottle):
    """
    Limits public patient intake submissions (lead forms & booking requests)
    to prevent spam bots and denial of service.
    Default: 10 requests / minute per IP.
    """
    scope = 'public_inquiry'

    def get_cache_key(self, request, view):
        self.request = request
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }


class AnalyticsBeaconThrottle(SecurityAuditThrottleMixin, SimpleRateThrottle):
    """
    Limits public website pageview and click-event beacons to prevent telemetry flooding.
    Default: 120 requests / minute per IP.
    """
    scope = 'analytics_beacon'

    def get_cache_key(self, request, view):
        self.request = request
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }


class BackupExportThrottle(SecurityAuditThrottleMixin, SimpleRateThrottle):
    """
    Protects practice snapshot exports against excessive resource utilization.
    Default: 5 requests / hour per user/practice.
    """
    scope = 'backup_export'

    def get_cache_key(self, request, view):
        self.request = request
        if request.user.is_authenticated:
            ident = str(request.user.id)
        else:
            ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }

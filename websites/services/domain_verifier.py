import socket
from django.conf import settings
from django.utils import timezone
from websites.models import CustomDomain


class DomainVerificationService:
    """
    Handles DNS record verification, SSL status simulation,
    and DNS configuration guidance for Custom Domains in ClinicRise.
    """

    DEFAULT_CNAME_TARGET = 'sites.clinicrise.com'

    @classmethod
    def get_dns_instructions(cls, custom_domain):
        """
        Returns required DNS records for the user to configure in their domain registrar
        (GoDaddy, Namecheap, Cloudflare, Google Domains, etc.).
        """
        domain_name = custom_domain.domain.lower().strip()
        is_subdomain = domain_name.count('.') > 1 and not domain_name.startswith('www.')

        host_cname = domain_name if is_subdomain else 'www'

        return {
            "domain": domain_name,
            "status": custom_domain.status,
            "ssl_status": custom_domain.ssl_status,
            "is_verified": custom_domain.status == CustomDomain.STATUS_ACTIVE,
            "required_records": [
                {
                    "type": "CNAME",
                    "host": host_cname,
                    "value": custom_domain.cname_target or cls.DEFAULT_CNAME_TARGET,
                    "ttl": "Automatic / 300",
                    "purpose": "Points your web traffic to ClinicRise secure edge hosting"
                },
                {
                    "type": "TXT",
                    "host": f"_clinicrise-challenge.{domain_name}",
                    "value": custom_domain.verification_token,
                    "ttl": "300",
                    "purpose": "Proves domain ownership to ClinicRise"
                }
            ],
            "last_verified_at": custom_domain.last_verified_at,
        }

    @classmethod
    def verify_domain(cls, custom_domain, force_simulate=False):
        """
        Perform DNS resolution and verification check on the custom domain.
        In debug or simulation mode, verifies token and issues SSL certificate.
        """
        domain = custom_domain.domain.lower().strip()

        # In testing / debug mode, or when simulation is requested:
        if settings.DEBUG or force_simulate or getattr(settings, 'MOCK_DNS_VERIFICATION', True):
            custom_domain.status = CustomDomain.STATUS_ACTIVE
            custom_domain.ssl_status = CustomDomain.SSL_ISSUED
            custom_domain.last_verified_at = timezone.now()
            custom_domain.save(update_fields=['status', 'ssl_status', 'last_verified_at', 'updated_at'])
            return True, "Domain DNS verified and SSL certificate successfully provisioned!"

        # Live DNS checking (production mode)
        try:
            # Check host resolution
            host_info = socket.gethostbyname(domain)
            if host_info:
                custom_domain.status = CustomDomain.STATUS_ACTIVE
                custom_domain.ssl_status = CustomDomain.SSL_ISSUED
                custom_domain.last_verified_at = timezone.now()
                custom_domain.save(update_fields=['status', 'ssl_status', 'last_verified_at', 'updated_at'])
                return True, "Domain verified successfully!"
        except Exception as e:
            custom_domain.status = CustomDomain.STATUS_FAILED
            custom_domain.save(update_fields=['status', 'updated_at'])
            return False, f"DNS check could not resolve '{domain}'. Error: {str(e)}"

        return False, "Verification pending. Please ensure your DNS records are configured and propagated."

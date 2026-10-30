import uuid
import secrets
from django.conf import settings
from django.db import models
from django.utils import timezone


class ClinicWebsite(models.Model):
    """
    Website entity associated with a Practice tenant.
    Controls branding, templates, SEO, domain routing, and publishing state.
    """
    TEMPLATE_MODERN_MINIMAL = 'modern_minimal'
    TEMPLATE_CLINICAL_CLEAN = 'clinical_clean'
    TEMPLATE_PEDIATRIC_WARM = 'pediatric_warm'
    TEMPLATE_DENTAL_BRIGHT = 'dental_bright'
    TEMPLATE_LUXURY_WELLNESS = 'luxury_wellness'
    TEMPLATE_DARK_PREMIUM = 'dark_premium'

    TEMPLATE_CHOICES = [
        (TEMPLATE_MODERN_MINIMAL, 'Modern Minimalist (Sleek, Typography-focused)'),
        (TEMPLATE_CLINICAL_CLEAN, 'Clinical Clean (Hospital & General OPD)'),
        (TEMPLATE_PEDIATRIC_WARM, 'Pediatric Warm (Friendly, Playful Accents)'),
        (TEMPLATE_DENTAL_BRIGHT, 'Dental Bright (Vibrant, Smile-oriented)'),
        (TEMPLATE_LUXURY_WELLNESS, 'Luxury Wellness & Aesthetic (High-end, Soft Tones)'),
        (TEMPLATE_DARK_PREMIUM, 'Dark Mode Premium (Bold, High Contrast)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    practice = models.OneToOneField(
        'practices.Practice',
        on_delete=models.CASCADE,
        related_name='clinic_website'
    )
    title = models.CharField(max_length=255, help_text="Public site title (e.g. City Dental Care)")
    tagline = models.CharField(max_length=255, blank=True, help_text="Short subtitle or value proposition")
    subdomain = models.SlugField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Subdomain for free hosting (e.g. 'citydental' -> citydental.clinicrise.com)"
    )

    # Template & Theme Tokens
    template_style = models.CharField(
        max_length=50,
        choices=TEMPLATE_CHOICES,
        default=TEMPLATE_MODERN_MINIMAL
    )
    primary_color = models.CharField(
        max_length=20,
        default='#0D9488',
        help_text="Hex brand color (e.g. #0D9488)"
    )
    secondary_color = models.CharField(
        max_length=20,
        default='#0F172A',
        help_text="Hex accent color (e.g. #0F172A)"
    )
    font_family = models.CharField(
        max_length=50,
        default='Inter',
        help_text="Google Font family name (e.g. Inter, Outfit, Plus Jakarta Sans)"
    )

    # Header & Footer Navigation
    logo_url = models.URLField(max_length=500, blank=True, null=True)
    favicon_url = models.URLField(max_length=500, blank=True, null=True)
    header_cta_text = models.CharField(max_length=50, default='Book Appointment')
    header_cta_link = models.CharField(max_length=255, default='#appointment')
    footer_text = models.CharField(max_length=255, blank=True)

    # Social & Contact Quicklinks
    contact_phone = models.CharField(max_length=30, blank=True)
    contact_email = models.EmailField(blank=True)
    whatsapp_number = models.CharField(max_length=30, blank=True, help_text="With country code for direct chat")
    emergency_contact = models.CharField(max_length=30, blank=True)
    google_maps_url = models.URLField(max_length=500, blank=True, null=True)
    facebook_url = models.URLField(blank=True, null=True)
    instagram_url = models.URLField(blank=True, null=True)
    linkedin_url = models.URLField(blank=True, null=True)

    # Global SEO
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)
    meta_keywords = models.CharField(max_length=255, blank=True)
    og_image_url = models.URLField(max_length=500, blank=True, null=True)
    google_analytics_id = models.CharField(max_length=50, blank=True)

    # Status & Publishing
    is_published = models.BooleanField(default=False)
    is_maintenance = models.BooleanField(
        default=False,
        help_text="Show maintenance under-construction notice to public visitors"
    )
    has_unpublished_changes = models.BooleanField(default=True)
    published_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Clinic Website'
        verbose_name_plural = 'Clinic Websites'

    def __str__(self):
        return f"{self.title} ({self.subdomain}.clinicrise.com)"

    @property
    def public_url(self):
        primary_domain = self.custom_domains.filter(status=CustomDomain.STATUS_ACTIVE, is_primary=True).first()
        if primary_domain:
            return f"https://{primary_domain.domain}"
        return f"https://{self.subdomain}.clinicrise.com"

    def publish_all(self):
        """1-Click publish of the website and all its draft pages."""
        for page in self.pages.all():
            page.publish()
        self.is_published = True
        self.has_unpublished_changes = False
        self.published_at = timezone.now()
        self.save(update_fields=['is_published', 'has_unpublished_changes', 'published_at', 'updated_at'])


class CustomDomain(models.Model):
    """
    Custom domain mapping for a clinic website (e.g. www.citydentalcare.com).
    Handles DNS verification tokens, SSL status, and routing.
    """
    STATUS_PENDING = 'pending_verification'
    STATUS_VERIFIED = 'verified'
    STATUS_ACTIVE = 'active'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending DNS Verification'),
        (STATUS_VERIFIED, 'DNS Verified (Provisioning SSL)'),
        (STATUS_ACTIVE, 'Active & Secured (Live)'),
        (STATUS_FAILED, 'Verification Failed'),
    ]

    SSL_PENDING = 'pending'
    SSL_ISSUED = 'issued'
    SSL_FAILED = 'failed'

    SSL_CHOICES = [
        (SSL_PENDING, 'Pending SSL Certificate'),
        (SSL_ISSUED, 'SSL Active (HTTPS Secured)'),
        (SSL_FAILED, 'SSL Certificate Error'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    website = models.ForeignKey(ClinicWebsite, on_delete=models.CASCADE, related_name='custom_domains')
    domain = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Custom domain, e.g. www.cityhealthclinic.com or drrajesh.com"
    )
    is_primary = models.BooleanField(default=False)

    # Verification & DNS Records
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_PENDING)
    ssl_status = models.CharField(max_length=30, choices=SSL_CHOICES, default=SSL_PENDING)
    verification_token = models.CharField(max_length=64, editable=False)
    cname_target = models.CharField(max_length=100, default='sites.clinicrise.com')

    last_verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_primary', '-created_at']
        verbose_name = 'Custom Domain'
        verbose_name_plural = 'Custom Domains'

    def __str__(self):
        return f"{self.domain} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.verification_token:
            self.verification_token = f"clinicrise-verify-{secrets.token_hex(16)}"
        if self.is_primary:
            # Set all other domains of this website to non-primary
            CustomDomain.objects.filter(website=self.website).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


class WebsitePage(models.Model):
    """
    Page on the clinic website. Supports multi-page navigation,
    draft editing, publishing, and revision tracking.
    """
    PAGE_TYPE_HOME = 'home'
    PAGE_TYPE_ABOUT = 'about'
    PAGE_TYPE_SERVICES = 'services'
    PAGE_TYPE_DOCTORS = 'doctors'
    PAGE_TYPE_TESTIMONIALS = 'testimonials'
    PAGE_TYPE_CONTACT = 'contact'
    PAGE_TYPE_CUSTOM = 'custom'
    PAGE_TYPE_POLICY = 'policy'

    PAGE_TYPE_CHOICES = [
        (PAGE_TYPE_HOME, 'Home Page'),
        (PAGE_TYPE_ABOUT, 'About Clinic & Doctors'),
        (PAGE_TYPE_SERVICES, 'Treatments & Services'),
        (PAGE_TYPE_DOCTORS, 'Our Medical Team'),
        (PAGE_TYPE_TESTIMONIALS, 'Patient Reviews & Testimonials'),
        (PAGE_TYPE_CONTACT, 'Contact & Clinic Hours'),
        (PAGE_TYPE_CUSTOM, 'Custom Content Page'),
        (PAGE_TYPE_POLICY, 'Terms & Privacy Policy'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    website = models.ForeignKey(ClinicWebsite, on_delete=models.CASCADE, related_name='pages')
    title = models.CharField(max_length=200, help_text="Page title, e.g. Home, About Us, Treatments")
    slug = models.SlugField(max_length=200, db_index=True, help_text="URL slug (e.g. 'home', 'about', 'services')")
    is_homepage = models.BooleanField(default=False)
    page_type = models.CharField(max_length=30, choices=PAGE_TYPE_CHOICES, default=PAGE_TYPE_CUSTOM)

    # Navigation
    is_in_navigation = models.BooleanField(default=True)
    is_in_footer = models.BooleanField(default=True)
    nav_order = models.PositiveSmallIntegerField(default=0)

    # SEO
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)

    # Content payloads (Draft vs Published)
    draft_content = models.JSONField(
        default=dict,
        blank=True,
        help_text="Active editing payload containing modular page sections"
    )
    published_content = models.JSONField(
        default=dict,
        blank=True,
        help_text="Currently live published snapshot visible to visitors"
    )

    is_published = models.BooleanField(default=False)
    has_unpublished_changes = models.BooleanField(default=True)
    published_version = models.PositiveIntegerField(default=0)
    published_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('website', 'slug')
        ordering = ['nav_order', 'created_at']
        verbose_name = 'Website Page'
        verbose_name_plural = 'Website Pages'

    def __str__(self):
        return f"{self.title} (/{self.slug}) - {self.website.title}"

    def publish(self, user=None):
        """Publish draft content to live site, incrementing version."""
        self.published_content = dict(self.draft_content)
        self.is_published = True
        self.has_unpublished_changes = False
        self.published_version += 1
        self.published_at = timezone.now()
        self.save(update_fields=[
            'published_content',
            'is_published',
            'has_unpublished_changes',
            'published_version',
            'published_at',
            'updated_at'
        ])

        WebsitePageRevision.objects.create(
            page=self,
            version=self.published_version,
            content=self.published_content,
            published_by=user
        )

    def revert_to_version(self, version_number):
        """Rollback draft content to a previous historical version."""
        rev = self.revisions.filter(version=version_number).first()
        if rev:
            self.draft_content = dict(rev.content)
            self.has_unpublished_changes = True
            self.save(update_fields=['draft_content', 'has_unpublished_changes', 'updated_at'])
            return True
        return False


class WebsitePageRevision(models.Model):
    """
    Historical immutable revision snapshots of published pages.
    Allows rollbacks and audit trail of website content changes.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    page = models.ForeignKey(WebsitePage, on_delete=models.CASCADE, related_name='revisions')
    version = models.PositiveIntegerField()
    content = models.JSONField()
    published_at = models.DateTimeField(auto_now_add=True)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-version']
        unique_together = ('page', 'version')
        verbose_name = 'Page Revision'
        verbose_name_plural = 'Page Revisions'

    def __str__(self):
        return f"{self.page.title} - v{self.version} ({self.published_at.strftime('%Y-%m-%d %H:%M')})"


class WebsiteInquiry(models.Model):
    """
    Inquiries submitted by patients through the contact or booking form on the clinic website.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    website = models.ForeignKey(ClinicWebsite, on_delete=models.CASCADE, related_name='inquiries')
    patient_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    preferred_service = models.CharField(max_length=255, blank=True)
    preferred_date = models.DateField(null=True, blank=True)
    message = models.TextField(blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Website Inquiry'
        verbose_name_plural = 'Website Inquiries'

    def __str__(self):
        return f"Inquiry from {self.patient_name} - {self.phone_number}"

import uuid
from django.db import models
from practices.models import TenantAwareModel


class WebsiteVisit(TenantAwareModel):
    """
    Records an individual website visit / pageview on a clinic's website.
    Supports traffic source attribution (Organic, Direct, Social, Paid, WhatsApp, Referral)
    and UTM marketing campaign tracking.
    """
    # Traffic Acquisition Channels
    CHANNEL_ORGANIC_SEARCH = 'organic_search'
    CHANNEL_DIRECT = 'direct'
    CHANNEL_SOCIAL = 'social'
    CHANNEL_PAID_AD = 'paid_ad'
    CHANNEL_WHATSAPP = 'whatsapp'
    CHANNEL_REFERRAL = 'referral'
    CHANNEL_EMAIL = 'email'
    CHANNEL_CAMPAIGN = 'campaign'

    CHANNEL_CHOICES = [
        (CHANNEL_ORGANIC_SEARCH, 'Organic Search (Google, Bing, Yahoo)'),
        (CHANNEL_DIRECT, 'Direct / Typed URL'),
        (CHANNEL_SOCIAL, 'Social Media (Instagram, Facebook, LinkedIn, YouTube)'),
        (CHANNEL_PAID_AD, 'Paid Ads / Search Ads / PPC'),
        (CHANNEL_WHATSAPP, 'WhatsApp Links & Chats'),
        (CHANNEL_REFERRAL, 'Referral (External Websites)'),
        (CHANNEL_EMAIL, 'Email Newsletter & Links'),
        (CHANNEL_CAMPAIGN, 'Custom Ad Campaign'),
    ]

    # Device Types
    DEVICE_MOBILE = 'mobile'
    DEVICE_DESKTOP = 'desktop'
    DEVICE_TABLET = 'tablet'
    DEVICE_UNKNOWN = 'unknown'

    DEVICE_CHOICES = [
        (DEVICE_MOBILE, 'Mobile Smartphone'),
        (DEVICE_DESKTOP, 'Desktop / Laptop'),
        (DEVICE_TABLET, 'Tablet'),
        (DEVICE_UNKNOWN, 'Unknown Device'),
    ]

    website = models.ForeignKey(
        'websites.ClinicWebsite',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='visits',
        help_text="Clinic website being browsed"
    )

    # Visitor & Session Context
    visitor_id = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Anonymous visitor session/cookie identifier"
    )
    session_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Browser session token"
    )

    # Page Navigation
    page_url = models.TextField(help_text="Full URL of the visited page")
    page_path = models.CharField(max_length=255, blank=True, db_index=True, help_text="Normalized URL path (e.g. /services)")
    page_title = models.CharField(max_length=255, blank=True, help_text="Title tag of the page")

    # Traffic Acquisition & Attribution
    referrer = models.TextField(blank=True, help_text="HTTP Referrer URL")
    referrer_domain = models.CharField(max_length=255, blank=True, db_index=True, help_text="Host/domain from referrer")
    traffic_channel = models.CharField(
        max_length=50,
        choices=CHANNEL_CHOICES,
        default=CHANNEL_DIRECT,
        db_index=True
    )
    traffic_source = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Recognized source (e.g. Google, Instagram, WhatsApp, Direct)"
    )

    # UTM Parameters
    utm_source = models.CharField(max_length=100, blank=True, db_index=True)
    utm_medium = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=150, blank=True, db_index=True)
    utm_term = models.CharField(max_length=150, blank=True)
    utm_content = models.CharField(max_length=150, blank=True)

    # Device & Client Details
    device_type = models.CharField(max_length=30, choices=DEVICE_CHOICES, default=DEVICE_DESKTOP)
    browser = models.CharField(max_length=50, blank=True)
    os = models.CharField(max_length=50, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    # Unique visitor indicator
    is_unique_daily = models.BooleanField(
        default=True,
        help_text="True if this is the first pageview from this visitor_id on this day"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Website Visit'
        verbose_name_plural = 'Website Visits'
        indexes = [
            models.Index(fields=['practice', 'created_at']),
            models.Index(fields=['practice', 'traffic_channel']),
            models.Index(fields=['practice', 'traffic_source']),
            models.Index(fields=['practice', 'visitor_id']),
            models.Index(fields=['website', 'created_at']),
        ]

    def __str__(self):
        return f"{self.page_path or self.page_url} - {self.get_traffic_channel_display()} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"

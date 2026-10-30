import uuid
from django.db import models
from django.utils import timezone
from practices.models import TenantAwareModel


class GBPProfileChecklist(TenantAwareModel):
    """
    Tracks Google Business Profile (GBP) optimization checklist progress,
    verification state, and generated local SEO setup assets for a clinical practice.
    """
    STATUS_UNVERIFIED = 'unverified'
    STATUS_PENDING = 'pending'
    STATUS_VERIFIED = 'verified'
    STATUS_SUSPENDED = 'suspended'

    STATUS_CHOICES = [
        (STATUS_UNVERIFIED, 'Not Verified / Setup Incomplete'),
        (STATUS_PENDING, 'Pending Google Verification (Video / Phone / Postcard)'),
        (STATUS_VERIFIED, 'Verified & Active on Google Maps'),
        (STATUS_SUSPENDED, 'Suspended / Reinstatement Required'),
    ]

    # Google Profile Identifiers & Links
    google_maps_url = models.URLField(max_length=500, blank=True, help_text="Public Google Maps listing URL")
    google_maps_place_id = models.CharField(max_length=150, blank=True, help_text="Google Place ID (e.g. ChIJN1t_tDeuEmsRUsoyG83frY4)")
    google_review_link = models.URLField(max_length=500, blank=True, help_text="Direct patient write-review shortcut link")
    verification_status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_UNVERIFIED, db_index=True)

    # Categories & Overrides
    primary_category = models.CharField(max_length=150, blank=True, help_text="Primary Google Business healthcare category")
    secondary_categories = models.JSONField(default=list, blank=True, help_text="List of secondary category strings")
    custom_description = models.TextField(blank=True, help_text="Customized business description if edited by practice team")

    # Attributes & Accessibility
    has_wheelchair_accessible_entrance = models.BooleanField(default=True)
    has_wheelchair_accessible_restroom = models.BooleanField(default=True)
    requires_appointments = models.BooleanField(default=True)
    accepts_upi_payments = models.BooleanField(default=True)
    accepts_credit_cards = models.BooleanField(default=True)

    # Checklist manual completions
    manual_completed_items = models.JSONField(
        default=list,
        blank=True,
        help_text="Keys of checklist items manually verified by practice staff"
    )
    notes = models.TextField(blank=True, help_text="Internal staff notes regarding GBP setup and verification")

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'GBP Profile & Checklist'
        verbose_name_plural = 'GBP Profiles & Checklists'
        indexes = [
            models.Index(fields=['practice', 'verification_status']),
        ]

    def __str__(self):
        return f"GBP Profile: {self.practice.name} ({self.get_verification_status_display()})"

    def mark_item_completed(self, item_key: str, completed: bool = True):
        """Toggles a manual checklist item state."""
        items = set(self.manual_completed_items or [])
        if completed:
            items.add(item_key)
        else:
            items.discard(item_key)
        self.manual_completed_items = sorted(list(items))
        self.save(update_fields=['manual_completed_items', 'updated_at'])


class GBPConnection(TenantAwareModel):
    """
    OAuth2 credentials and connection parameters for Google Business Profile API
    and Google Search Console API.
    """
    STATUS_IDLE = 'idle'
    STATUS_SYNCING = 'syncing'
    STATUS_SUCCESS = 'success'
    STATUS_ERROR = 'error'

    STATUS_CHOICES = [
        (STATUS_IDLE, 'Idle'),
        (STATUS_SYNCING, 'Sync in Progress'),
        (STATUS_SUCCESS, 'Connected & Synced'),
        (STATUS_ERROR, 'Sync Error / Reauthorization Needed'),
    ]

    google_account_email = models.EmailField(blank=True, help_text="Google Business Profile owner/manager email")
    account_id = models.CharField(max_length=150, blank=True, help_text="e.g. accounts/10982347102")
    location_id = models.CharField(max_length=150, blank=True, help_text="e.g. locations/89234710238")
    api_key = models.CharField(max_length=255, blank=True)
    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)

    is_connected = models.BooleanField(default=True)
    sync_status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_SUCCESS)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_sync_error = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'GBP API Connection'
        verbose_name_plural = 'GBP API Connections'

    def __str__(self):
        return f"GBP Connection: {self.practice.name} ({self.google_account_email or 'Simulated'})"


class GoogleReview(TenantAwareModel):
    """
    Patient reviews synchronized from Google Business Profile.
    Includes reviewer info, 1-5 star ratings, review text, and practice owner replies.
    """
    review_id = models.CharField(max_length=200, unique=True, db_index=True)
    reviewer_name = models.CharField(max_length=200)
    reviewer_photo_url = models.URLField(max_length=500, blank=True)
    star_rating = models.PositiveSmallIntegerField(default=5, help_text="1 to 5 stars")
    comment = models.TextField(blank=True)
    review_timestamp = models.DateTimeField()

    reply_text = models.TextField(blank=True)
    replied_at = models.DateTimeField(null=True, blank=True)
    is_replied = models.BooleanField(default=False, db_index=True)
    ai_suggested_reply = models.TextField(blank=True, help_text="AI suggested response draft compliant with healthcare privacy")

    class Meta:
        ordering = ['-review_timestamp']
        verbose_name = 'Google Review'
        verbose_name_plural = 'Google Reviews'
        indexes = [
            models.Index(fields=['practice', 'star_rating']),
            models.Index(fields=['practice', 'is_replied']),
        ]

    def __str__(self):
        return f"{self.reviewer_name} ({self.star_rating}★) - {self.practice.name}"


class GBPPost(TenantAwareModel):
    """
    Google Business Profile Updates, Clinical Announcements, and Healthcare Offers.
    """
    TYPE_UPDATE = 'update'
    TYPE_OFFER = 'offer'
    TYPE_EVENT = 'event'

    TYPE_CHOICES = [
        (TYPE_UPDATE, 'What\'s New / Clinical Update'),
        (TYPE_OFFER, 'Special Treatment Offer'),
        (TYPE_EVENT, 'Health Camp / Clinic Event'),
    ]

    CTA_BOOK = 'BOOK'
    CTA_CALL = 'CALL'
    CTA_LEARN_MORE = 'LEARN_MORE'
    CTA_SIGN_UP = 'SIGN_UP'
    CTA_NONE = 'NONE'

    CTA_CHOICES = [
        (CTA_BOOK, 'Book Appointment'),
        (CTA_CALL, 'Call Now'),
        (CTA_LEARN_MORE, 'Learn More'),
        (CTA_SIGN_UP, 'Sign Up'),
        (CTA_NONE, 'No Button'),
    ]

    STATUS_DRAFT = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_SCHEDULED = 'scheduled'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_PUBLISHED, 'Published on Google Maps'),
        (STATUS_SCHEDULED, 'Scheduled'),
    ]

    post_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_UPDATE)
    summary = models.TextField(help_text="Post body text / health tip / announcement")
    cta_type = models.CharField(max_length=20, choices=CTA_CHOICES, default=CTA_BOOK)
    cta_url = models.URLField(max_length=500, blank=True)
    image_url = models.URLField(max_length=500, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PUBLISHED)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'GBP Post'
        verbose_name_plural = 'GBP Posts'

    def __str__(self):
        return f"GBP Post ({self.get_post_type_display()}) - {self.practice.name}"


class GBPInsight(TenantAwareModel):
    """
    Daily aggregated performance insights synchronized from Google Business Profile API.
    Tracks search impressions, map views, website clicks, calls, and direction requests.
    """
    date = models.DateField(db_index=True)
    search_impressions_direct = models.PositiveIntegerField(default=0, help_text="Searched clinic name directly")
    search_impressions_discovery = models.PositiveIntegerField(default=0, help_text="Searched category e.g. 'dentist near me'")
    search_impressions_branded = models.PositiveIntegerField(default=0, help_text="Searched related brand")

    maps_impressions = models.PositiveIntegerField(default=0, help_text="Views on Google Maps")
    search_impressions = models.PositiveIntegerField(default=0, help_text="Views on Google Search")

    website_clicks = models.PositiveIntegerField(default=0, help_text="Clicks to clinic website")
    call_clicks = models.PositiveIntegerField(default=0, help_text="Direct phone call clicks from Google profile")
    direction_requests = models.PositiveIntegerField(default=0, help_text="Driving / transit directions requested")
    bookings_clicks = models.PositiveIntegerField(default=0, help_text="Clicks on appointment booking button")

    class Meta:
        ordering = ['-date']
        verbose_name = 'GBP Insight'
        verbose_name_plural = 'GBP Insights'
        unique_together = ('practice', 'date')
        indexes = [
            models.Index(fields=['practice', 'date']),
        ]

    def __str__(self):
        return f"GBP Insights for {self.practice.name} on {self.date}"

    @property
    def total_impressions(self):
        return self.maps_impressions + self.search_impressions

    @property
    def total_actions(self):
        return self.website_clicks + self.call_clicks + self.direction_requests + self.bookings_clicks


class SearchConsoleQuery(TenantAwareModel):
    """
    Google Search Console (GSC) organic search query analytics.
    Tracks patient search queries, organic clicks, impressions, CTR, and average position.
    """
    query = models.CharField(max_length=255, db_index=True, help_text="Medical search query, e.g. 'root canal cost indiranagar'")
    page = models.CharField(max_length=500, blank=True, help_text="Landing page URL path")
    clicks = models.PositiveIntegerField(default=0)
    impressions = models.PositiveIntegerField(default=0)
    ctr = models.DecimalField(max_digits=5, decimal_places=4, default=0.0, help_text="Click-through rate (e.g. 0.0540 = 5.4%)")
    position = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, help_text="Average organic position (e.g. 2.4)")
    date = models.DateField(db_index=True)

    class Meta:
        ordering = ['-clicks', '-impressions']
        verbose_name = 'Search Console Query'
        verbose_name_plural = 'Search Console Queries'
        indexes = [
            models.Index(fields=['practice', 'date']),
            models.Index(fields=['practice', 'query']),
        ]

    def __str__(self):
        return f"'{self.query}' ({self.clicks} clicks | pos {self.position}) - {self.practice.name}"


class LocalRankKeyword(TenantAwareModel):
    """
    Tracked target keyword for Local SEO and Google 3-Pack rank tracking.
    """
    keyword = models.CharField(max_length=200, db_index=True, help_text="e.g. 'dentist near me', 'dental implants bengaluru'")
    target_city = models.CharField(max_length=100, default='Bengaluru')
    target_radius_km = models.PositiveSmallIntegerField(default=10)

    current_pack_rank = models.PositiveSmallIntegerField(null=True, blank=True, help_text="1, 2, 3 in local 3-pack, or null if outside top 20")
    previous_pack_rank = models.PositiveSmallIntegerField(null=True, blank=True)
    organic_rank = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Organic SERP rank position")
    is_in_local_three_pack = models.BooleanField(default=False, db_index=True)

    last_checked_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['current_pack_rank', 'keyword']
        verbose_name = 'Local Rank Keyword'
        verbose_name_plural = 'Local Rank Keywords'
        unique_together = ('practice', 'keyword')

    def __str__(self):
        pack_tag = f"#{self.current_pack_rank} in 3-Pack" if self.current_pack_rank else "Unranked"
        return f"{self.keyword} ({pack_tag}) - {self.practice.name}"


class LocalRankSnapshot(TenantAwareModel):
    """
    Historical rank snapshot for a tracked keyword on a specific check date.
    Records Local 3-Pack position, organic SERP position, and top 3 competitors.
    """
    keyword = models.ForeignKey(LocalRankKeyword, on_delete=models.CASCADE, related_name='snapshots')
    check_date = models.DateField(db_index=True)
    pack_rank_position = models.PositiveSmallIntegerField(null=True, blank=True, help_text="1 to 20 (1-3 = Local 3-Pack)")
    in_three_pack = models.BooleanField(default=False)
    organic_rank_position = models.PositiveSmallIntegerField(null=True, blank=True)
    competitors_in_pack = models.JSONField(default=list, blank=True, help_text="Names of top 3 clinics occupying the local pack")
    rank_change = models.IntegerField(default=0, help_text="Position change (+2 means jumped up 2 spots, -1 dropped)")

    class Meta:
        ordering = ['-check_date']
        verbose_name = 'Local Rank Snapshot'
        verbose_name_plural = 'Local Rank Snapshots'
        indexes = [
            models.Index(fields=['keyword', 'check_date']),
        ]

    def __str__(self):
        return f"{self.keyword.keyword} on {self.check_date}: Rank #{self.pack_rank_position or 'N/A'}"

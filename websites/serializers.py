from rest_framework import serializers
from websites.models import (
    ClinicWebsite,
    CustomDomain,
    WebsiteInquiry,
    WebsitePage,
    WebsitePageRevision,
)
from websites.services.domain_verifier import DomainVerificationService


class CustomDomainSerializer(serializers.ModelSerializer):
    """Serializer for Custom Domains connected to a clinic website."""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    ssl_status_display = serializers.CharField(source='get_ssl_status_display', read_only=True)
    dns_instructions = serializers.SerializerMethodField()

    class Meta:
        model = CustomDomain
        fields = [
            'id',
            'website',
            'domain',
            'is_primary',
            'status',
            'status_display',
            'ssl_status',
            'ssl_status_display',
            'verification_token',
            'cname_target',
            'dns_instructions',
            'last_verified_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'website',
            'status',
            'status_display',
            'ssl_status',
            'ssl_status_display',
            'verification_token',
            'cname_target',
            'dns_instructions',
            'last_verified_at',
            'created_at',
            'updated_at',
        ]

    def get_dns_instructions(self, obj):
        return DomainVerificationService.get_dns_instructions(obj)

    def validate_domain(self, value):
        val = value.strip().lower()
        if '://' in val:
            val = val.split('://')[1]
        val = val.split('/')[0]
        if not ('.' in val) or len(val) < 4:
            raise serializers.ValidationError("Please provide a valid fully qualified domain name (e.g. www.myclinic.com or clinic.org).")
        return val


class WebsitePageSummarySerializer(serializers.ModelSerializer):
    """Compact summary serializer for pages list."""
    page_type_display = serializers.CharField(source='get_page_type_display', read_only=True)

    class Meta:
        model = WebsitePage
        fields = [
            'id',
            'title',
            'slug',
            'is_homepage',
            'page_type',
            'page_type_display',
            'is_in_navigation',
            'is_in_footer',
            'nav_order',
            'is_published',
            'has_unpublished_changes',
            'published_version',
            'published_at',
            'updated_at',
        ]


class WebsitePageSerializer(serializers.ModelSerializer):
    """Detailed page serializer including draft and published content."""
    page_type_display = serializers.CharField(source='get_page_type_display', read_only=True)
    revisions_count = serializers.SerializerMethodField()
    approval = serializers.SerializerMethodField()

    class Meta:
        model = WebsitePage
        fields = [
            'id',
            'website',
            'title',
            'slug',
            'is_homepage',
            'page_type',
            'page_type_display',
            'is_in_navigation',
            'is_in_footer',
            'nav_order',
            'meta_title',
            'meta_description',
            'draft_content',
            'published_content',
            'is_published',
            'has_unpublished_changes',
            'published_version',
            'revisions_count',
            'approval',
            'published_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'website',
            'published_content',
            'is_published',
            'has_unpublished_changes',
            'published_version',
            'revisions_count',
            'approval',
            'published_at',
            'created_at',
            'updated_at',
        ]

    def get_revisions_count(self, obj):
        return obj.revisions.count()

    def get_approval(self, obj):
        from websites.services.approval_service import ContentApprovalService
        return ContentApprovalService.get_approval_data(obj)


class WebsitePageEditSerializer(serializers.ModelSerializer):
    """Serializer for modifying page settings and draft content blocks."""
    class Meta:
        model = WebsitePage
        fields = [
            'title',
            'slug',
            'meta_title',
            'meta_description',
            'is_in_navigation',
            'is_in_footer',
            'nav_order',
            'draft_content',
        ]

    def update(self, instance, validated_data):
        # When draft_content or settings change, mark has_unpublished_changes = True
        instance.has_unpublished_changes = True
        return super().update(instance, validated_data)


class WebsitePageRevisionSerializer(serializers.ModelSerializer):
    """Serializer for historical page revisions."""
    published_by_name = serializers.CharField(source='published_by.full_name', read_only=True)

    class Meta:
        model = WebsitePageRevision
        fields = [
            'id',
            'page',
            'version',
            'content',
            'published_at',
            'published_by_name',
        ]
        read_only_fields = ['id', 'page', 'version', 'published_at', 'published_by_name']


class ClinicWebsiteSerializer(serializers.ModelSerializer):
    """Complete serializer for Clinic Website."""
    template_style_display = serializers.CharField(source='get_template_style_display', read_only=True)
    public_url = serializers.CharField(read_only=True)
    pages_count = serializers.SerializerMethodField()
    custom_domains = CustomDomainSerializer(many=True, read_only=True)
    pages = WebsitePageSummarySerializer(many=True, read_only=True)

    class Meta:
        model = ClinicWebsite
        fields = [
            'id',
            'practice',
            'title',
            'tagline',
            'subdomain',
            'public_url',
            'template_style',
            'template_style_display',
            'primary_color',
            'secondary_color',
            'font_family',
            'logo_url',
            'favicon_url',
            'header_cta_text',
            'header_cta_link',
            'footer_text',
            'contact_phone',
            'contact_email',
            'whatsapp_number',
            'emergency_contact',
            'google_maps_url',
            'facebook_url',
            'instagram_url',
            'linkedin_url',
            'meta_title',
            'meta_description',
            'meta_keywords',
            'og_image_url',
            'google_analytics_id',
            'is_published',
            'is_maintenance',
            'has_unpublished_changes',
            'published_at',
            'pages_count',
            'pages',
            'custom_domains',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'practice',
            'public_url',
            'template_style_display',
            'is_published',
            'has_unpublished_changes',
            'published_at',
            'pages_count',
            'created_at',
            'updated_at',
        ]

    def get_pages_count(self, obj):
        return obj.pages.count()


class ClinicWebsiteUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating branding, theme, colors, and global settings."""
    class Meta:
        model = ClinicWebsite
        fields = [
            'title',
            'tagline',
            'template_style',
            'primary_color',
            'secondary_color',
            'font_family',
            'logo_url',
            'favicon_url',
            'header_cta_text',
            'header_cta_link',
            'footer_text',
            'contact_phone',
            'contact_email',
            'whatsapp_number',
            'emergency_contact',
            'google_maps_url',
            'facebook_url',
            'instagram_url',
            'linkedin_url',
            'meta_title',
            'meta_description',
            'meta_keywords',
            'og_image_url',
            'google_analytics_id',
            'is_maintenance',
        ]


class WebsiteGenerateInputSerializer(serializers.Serializer):
    """Input serializer for auto-generating a clinic website."""
    practice_id = serializers.UUIDField(required=False, allow_null=True)
    template_style = serializers.ChoiceField(
        choices=ClinicWebsite.TEMPLATE_CHOICES,
        required=False,
        default=ClinicWebsite.TEMPLATE_MODERN_MINIMAL
    )
    subdomain = serializers.SlugField(required=False, allow_blank=True)
    auto_publish = serializers.BooleanField(default=True)


class WebsiteInquirySerializer(serializers.ModelSerializer):
    """Serializer for patient inquiries submitted through the website."""
    class Meta:
        model = WebsiteInquiry
        fields = [
            'id',
            'website',
            'patient_name',
            'phone_number',
            'email',
            'preferred_service',
            'preferred_date',
            'message',
            'is_read',
            'created_at',
        ]
        read_only_fields = ['id', 'website', 'is_read', 'created_at']


# =====================================================================
# Content Approval & Doctor Clinical Review Serializers
# =====================================================================

class SubmitReviewRequestSerializer(serializers.Serializer):
    """Input serializer when submitting content for doctor review."""
    submission_notes = serializers.CharField(
        required=False,
        allow_blank=True,
        default='',
        help_text="Optional summary of changes, medical additions, or notes for the doctor."
    )


class DoctorReviewActionSerializer(serializers.Serializer):
    """Input serializer for doctor clinical review action."""
    action = serializers.ChoiceField(
        choices=['approve', 'request_changes'],
        help_text="'approve' to sign-off and allow publishing; 'request_changes' to return with feedback."
    )
    review_notes = serializers.CharField(
        required=False,
        allow_blank=True,
        default='',
        help_text="Doctor clinical notes, corrections, or approval remarks."
    )


class BlogPostCreateUpdateSerializer(serializers.Serializer):
    """Input serializer for creating or editing blog post drafts."""
    title = serializers.CharField(max_length=200, required=True)
    slug = serializers.CharField(max_length=200, required=False, allow_blank=True)
    category = serializers.CharField(max_length=100, required=False, default='General Healthcare')
    excerpt = serializers.CharField(max_length=500, required=False, allow_blank=True, default='')
    body_html = serializers.CharField(required=False, allow_blank=True, default='')
    cover_image_url = serializers.URLField(max_length=500, required=False, allow_blank=True, default='')
    author_doctor_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default='')
    tags = serializers.ListField(child=serializers.CharField(max_length=50), required=False, default=list)
    read_time_minutes = serializers.IntegerField(required=False, default=4, min_value=1)

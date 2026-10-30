from rest_framework import serializers
from gbp.models import (
    GBPConnection,
    GBPInsight,
    GBPPost,
    GBPProfileChecklist,
    GoogleReview,
    LocalRankKeyword,
    LocalRankSnapshot,
    SearchConsoleQuery,
)


class GBPProfileChecklistSerializer(serializers.ModelSerializer):
    """Serializes the persistent GBP profile settings."""
    verification_status_display = serializers.CharField(source='get_verification_status_display', read_only=True)

    class Meta:
        model = GBPProfileChecklist
        fields = [
            'id',
            'practice',
            'google_maps_url',
            'google_maps_place_id',
            'google_review_link',
            'verification_status',
            'verification_status_display',
            'primary_category',
            'secondary_categories',
            'custom_description',
            'has_wheelchair_accessible_entrance',
            'has_wheelchair_accessible_restroom',
            'requires_appointments',
            'accepts_upi_payments',
            'accepts_credit_cards',
            'manual_completed_items',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'practice', 'created_at', 'updated_at']


class GBPChecklistUpdateSerializer(serializers.ModelSerializer):
    """Validates updates to practice Google Business Profile configurations."""
    class Meta:
        model = GBPProfileChecklist
        fields = [
            'google_maps_url',
            'google_maps_place_id',
            'google_review_link',
            'verification_status',
            'primary_category',
            'secondary_categories',
            'custom_description',
            'has_wheelchair_accessible_entrance',
            'has_wheelchair_accessible_restroom',
            'requires_appointments',
            'accepts_upi_payments',
            'accepts_credit_cards',
            'notes',
        ]


class GBPItemToggleSerializer(serializers.Serializer):
    """Validates manual checklist item completion toggles."""
    item_key = serializers.CharField(max_length=100, required=True)
    is_completed = serializers.BooleanField(required=True)


class GBPConnectionSerializer(serializers.ModelSerializer):
    """Serializer for GBP API connection settings."""
    sync_status_display = serializers.CharField(source='get_sync_status_display', read_only=True)

    class Meta:
        model = GBPConnection
        fields = [
            'id',
            'practice',
            'google_account_email',
            'account_id',
            'location_id',
            'api_key',
            'is_connected',
            'sync_status',
            'sync_status_display',
            'last_synced_at',
            'last_sync_error',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'practice', 'created_at', 'updated_at']


class GoogleReviewSerializer(serializers.ModelSerializer):
    """Serializer for Google patient reviews."""
    class Meta:
        model = GoogleReview
        fields = [
            'id',
            'review_id',
            'reviewer_name',
            'reviewer_photo_url',
            'star_rating',
            'comment',
            'review_timestamp',
            'reply_text',
            'replied_at',
            'is_replied',
            'ai_suggested_reply',
            'created_at',
        ]
        read_only_fields = ['id', 'review_id', 'created_at']


class ReplyReviewSerializer(serializers.Serializer):
    """Serializer for posting a reply to a Google review."""
    reply_text = serializers.CharField(required=True, allow_blank=False)


class GBPPostSerializer(serializers.ModelSerializer):
    """Serializer for GBP Posts and Updates."""
    post_type_display = serializers.CharField(source='get_post_type_display', read_only=True)
    cta_type_display = serializers.CharField(source='get_cta_type_display', read_only=True)

    class Meta:
        model = GBPPost
        fields = [
            'id',
            'post_type',
            'post_type_display',
            'summary',
            'cta_type',
            'cta_type_display',
            'cta_url',
            'image_url',
            'status',
            'published_at',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class GBPInsightSerializer(serializers.ModelSerializer):
    """Serializer for daily GBP performance insights."""
    total_impressions = serializers.IntegerField(read_only=True)
    total_actions = serializers.IntegerField(read_only=True)

    class Meta:
        model = GBPInsight
        fields = [
            'id',
            'date',
            'search_impressions_direct',
            'search_impressions_discovery',
            'search_impressions_branded',
            'maps_impressions',
            'search_impressions',
            'total_impressions',
            'website_clicks',
            'call_clicks',
            'direction_requests',
            'bookings_clicks',
            'total_actions',
        ]
        read_only_fields = ['id']


class SearchConsoleQuerySerializer(serializers.ModelSerializer):
    """Serializer for Google Search Console query analytics."""
    class Meta:
        model = SearchConsoleQuery
        fields = [
            'id',
            'query',
            'page',
            'clicks',
            'impressions',
            'ctr',
            'position',
            'date',
        ]
        read_only_fields = ['id']


class LocalRankKeywordSerializer(serializers.ModelSerializer):
    """Serializer for local SEO tracked keywords."""
    class Meta:
        model = LocalRankKeyword
        fields = [
            'id',
            'keyword',
            'target_city',
            'target_radius_km',
            'current_pack_rank',
            'previous_pack_rank',
            'organic_rank',
            'is_in_local_three_pack',
            'last_checked_at',
            'is_active',
            'created_at',
        ]
        read_only_fields = ['id', 'current_pack_rank', 'previous_pack_rank', 'organic_rank', 'is_in_local_three_pack', 'last_checked_at', 'created_at']


class LocalRankSnapshotSerializer(serializers.ModelSerializer):
    """Serializer for keyword rank check snapshots."""
    keyword_text = serializers.CharField(source='keyword.keyword', read_only=True)

    class Meta:
        model = LocalRankSnapshot
        fields = [
            'id',
            'keyword',
            'keyword_text',
            'check_date',
            'pack_rank_position',
            'in_three_pack',
            'organic_rank_position',
            'competitors_in_pack',
            'rank_change',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

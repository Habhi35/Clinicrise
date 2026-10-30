from rest_framework import serializers
from analytics.models import WebsiteVisit


class PublicVisitTrackSerializer(serializers.Serializer):
    """
    Validates pageview tracking payloads sent from public clinic websites.
    """
    page_url = serializers.CharField(max_length=1000, required=True)
    page_path = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    page_title = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    referrer = serializers.CharField(required=False, allow_blank=True, default="")
    utm_source = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    utm_medium = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    utm_campaign = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    utm_term = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    utm_content = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    visitor_id = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    session_id = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    device_type = serializers.CharField(max_length=30, required=False, allow_blank=True, default="unknown")


class WebsiteVisitSerializer(serializers.ModelSerializer):
    """
    Serializes a single website visit record for logs / inspection.
    """
    traffic_channel_display = serializers.CharField(source='get_traffic_channel_display', read_only=True)
    device_type_display = serializers.CharField(source='get_device_type_display', read_only=True)

    class Meta:
        model = WebsiteVisit
        fields = [
            'id',
            'website',
            'visitor_id',
            'session_id',
            'page_url',
            'page_path',
            'page_title',
            'referrer',
            'referrer_domain',
            'traffic_channel',
            'traffic_channel_display',
            'traffic_source',
            'utm_source',
            'utm_medium',
            'utm_campaign',
            'device_type',
            'device_type_display',
            'browser',
            'os',
            'is_unique_daily',
            'created_at',
        ]
        read_only_fields = fields


class AnalyticsQueryParamSerializer(serializers.Serializer):
    """
    Validates date filtering and preset parameters for analytics endpoints.
    """
    preset = serializers.ChoiceField(
        choices=['today', 'yesterday', '7d', '30d', 'this_month', 'this_year', 'custom'],
        default='30d',
        required=False
    )
    date_from = serializers.DateField(required=False, allow_null=True)
    date_to = serializers.DateField(required=False, allow_null=True)
    website_id = serializers.UUIDField(required=False, allow_null=True)

from django.contrib import admin
from analytics.models import WebsiteVisit


@admin.register(WebsiteVisit)
class WebsiteVisitAdmin(admin.ModelAdmin):
    list_display = [
        'page_path',
        'practice',
        'traffic_channel',
        'traffic_source',
        'device_type',
        'visitor_id',
        'is_unique_daily',
        'created_at',
    ]
    list_filter = [
        'traffic_channel',
        'device_type',
        'is_unique_daily',
        'created_at',
        'practice',
    ]
    search_fields = [
        'page_url',
        'page_path',
        'referrer',
        'traffic_source',
        'utm_campaign',
        'utm_source',
        'visitor_id',
        'ip_address',
    ]
    readonly_fields = ['created_at', 'updated_at']

from django.contrib import admin
from gbp.models import GBPProfileChecklist


@admin.register(GBPProfileChecklist)
class GBPProfileChecklistAdmin(admin.ModelAdmin):
    list_display = [
        'practice',
        'primary_category',
        'verification_status',
        'has_wheelchair_accessible_entrance',
        'requires_appointments',
        'created_at',
    ]
    list_filter = ['verification_status', 'created_at', 'practice']
    search_fields = ['practice__name', 'primary_category', 'google_maps_place_id', 'custom_description']
    readonly_fields = ['created_at', 'updated_at']

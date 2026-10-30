from django.contrib import admin
from reports.models import MonthlyGrowthReport


@admin.register(MonthlyGrowthReport)
class MonthlyGrowthReportAdmin(admin.ModelAdmin):
    list_display = ['title', 'practice', 'year', 'month', 'status', 'generated_at']
    list_filter = ['practice', 'year', 'month', 'status', 'generated_at']
    search_fields = ['title', 'practice__name', 'executive_summary']

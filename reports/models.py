import uuid
from django.db import models
from django.utils import timezone
from practices.models import TenantAwareModel


class MonthlyGrowthReport(TenantAwareModel):
    """
    Consolidated Monthly Clinical Performance & Growth Report.
    Combines patient acquisition, Google Business Profile performance,
    Search Console organic traffic, Local 3-Pack rank tracking, and actionable growth insights.
    """
    STATUS_GENERATED = 'generated'
    STATUS_PUBLISHED = 'published'

    STATUS_CHOICES = [
        (STATUS_GENERATED, 'Generated / Internal Review'),
        (STATUS_PUBLISHED, 'Published / Shared with Doctor'),
    ]

    year = models.PositiveSmallIntegerField(default=2026, db_index=True)
    month = models.PositiveSmallIntegerField(default=10, db_index=True, help_text="Month number 1 to 12")
    title = models.CharField(max_length=255)
    period_start = models.DateField()
    period_end = models.DateField()

    # Aggregated performance metric payloads
    patient_metrics = models.JSONField(
        default=dict,
        blank=True,
        help_text="Consultations, new patients, online vs walk-ins, attendance rate"
    )
    gbp_metrics = models.JSONField(
        default=dict,
        blank=True,
        help_text="Search views, map views, calls, directions, website clicks, reviews gained"
    )
    gsc_metrics = models.JSONField(
        default=dict,
        blank=True,
        help_text="Organic clicks, impressions, CTR, average position, top search queries"
    )
    rank_metrics = models.JSONField(
        default=dict,
        blank=True,
        help_text="Keywords in Top 3 local pack, keywords in Top 10, average rank"
    )

    executive_summary = models.TextField(blank=True, help_text="Doctor-focused executive performance summary")
    recommendations = models.JSONField(default=list, blank=True, help_text="List of prioritized growth recommendations")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_GENERATED)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-year', '-month']
        verbose_name = 'Monthly Growth Report'
        verbose_name_plural = 'Monthly Growth Reports'
        unique_together = ('practice', 'year', 'month')
        indexes = [
            models.Index(fields=['practice', 'year', 'month']),
        ]

    def __str__(self):
        return f"{self.title} - {self.practice.name} ({self.get_status_display()})"

from rest_framework import serializers
from reports.models import MonthlyGrowthReport


class MonthlyGrowthReportSerializer(serializers.ModelSerializer):
    """Serializer for Monthly Clinical Growth & Performance Reports."""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    pdf_download_url = serializers.SerializerMethodField()

    class Meta:
        model = MonthlyGrowthReport
        fields = [
            'id',
            'practice',
            'year',
            'month',
            'title',
            'period_start',
            'period_end',
            'patient_metrics',
            'gbp_metrics',
            'gsc_metrics',
            'rank_metrics',
            'executive_summary',
            'recommendations',
            'status',
            'status_display',
            'pdf_download_url',
            'generated_at',
        ]
        read_only_fields = ['id', 'practice', 'title', 'period_start', 'period_end', 'generated_at']

    def get_pdf_download_url(self, obj) -> str:
        return f"/api/reports/monthly/{obj.id}/pdf/"


class GenerateReportInputSerializer(serializers.Serializer):
    """Input serializer for triggering report generation."""
    year = serializers.IntegerField(required=False, min_value=2020, max_value=2030)
    month = serializers.IntegerField(required=False, min_value=1, max_value=12)

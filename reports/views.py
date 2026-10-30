import uuid
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from practices.models import Practice, PracticeMembership
from reports.models import MonthlyGrowthReport
from reports.serializers import (
    GenerateReportInputSerializer,
    MonthlyGrowthReportSerializer,
)
from reports.services.report_generator_service import ReportGeneratorService
from reports.services.report_pdf_service import ReportPDFService


def _get_active_practice(request, practice_id=None):
    """Resolves active Practice tenant from middleware, header, or single membership."""
    if getattr(request, 'practice', None):
        return request.practice

    target_id = practice_id or request.headers.get('X-Practice-ID') or request.META.get('HTTP_X_PRACTICE_ID')
    if target_id:
        try:
            p_uuid = uuid.UUID(str(target_id).strip())
            membership = PracticeMembership.objects.filter(
                practice_id=p_uuid,
                user=request.user,
                is_active=True,
                practice__is_active=True
            ).select_related('practice').first()
            if membership:
                return membership.practice
        except (ValueError, TypeError):
            pass

    memberships = list(
        PracticeMembership.objects.filter(
            user=request.user,
            is_active=True,
            practice__is_active=True
        ).select_related('practice')[:2]
    )
    if len(memberships) == 1:
        return memberships[0].practice

    return None


class MonthlyGrowthReportListView(APIView):
    """
    List historical monthly performance and growth reports for the practice.
    GET /api/reports/monthly/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Practice context not found. Provide X-Practice-ID header."}, status=status.HTTP_400_BAD_REQUEST)

        reports = MonthlyGrowthReport.objects.filter(practice=practice).order_by('-year', '-month')
        if not reports.exists():
            # Auto-generate current month report
            ReportGeneratorService.generate_monthly_report(practice)
            reports = MonthlyGrowthReport.objects.filter(practice=practice).order_by('-year', '-month')

        serializer = MonthlyGrowthReportSerializer(reports, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MonthlyGrowthReportGenerateView(APIView):
    """
    Triggers synthesis and generation of a monthly performance report.
    POST /api/reports/monthly/generate/
    Payload: {"year": 2026, "month": 10}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Practice context not found. Provide X-Practice-ID header."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = GenerateReportInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        year = serializer.validated_data.get('year')
        month = serializer.validated_data.get('month')

        report = ReportGeneratorService.generate_monthly_report(practice, year=year, month=month)
        return Response(MonthlyGrowthReportSerializer(report).data, status=status.HTTP_201_CREATED)


class MonthlyGrowthReportDetailView(APIView):
    """
    Detailed JSON metrics and summary for a specific monthly growth report.
    GET /api/reports/monthly/<pk>/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Practice context not found."}, status=status.HTTP_400_BAD_REQUEST)

        report = get_object_or_404(MonthlyGrowthReport, id=pk, practice=practice)
        return Response(MonthlyGrowthReportSerializer(report).data, status=status.HTTP_200_OK)


class MonthlyGrowthReportPDFDownloadView(APIView):
    """
    Generates and serves the publication-ready PDF document for a specific monthly report.
    GET /api/reports/monthly/<pk>/pdf/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Practice context not found."}, status=status.HTTP_400_BAD_REQUEST)

        report = get_object_or_404(MonthlyGrowthReport, id=pk, practice=practice)
        pdf_bytes = ReportPDFService.generate_pdf(report)

        filename = f"ClinicRise_Report_{practice.name.replace(' ', '_')}_{report.year}_{report.month:02d}.pdf"
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Content-Length'] = len(pdf_bytes)
        return response


class MonthlyGrowthReportLatestPDFView(APIView):
    """
    Convenient 1-click endpoint to download the latest/current month's PDF report.
    GET /api/reports/monthly/latest/pdf/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Practice context not found."}, status=status.HTTP_400_BAD_REQUEST)

        latest_report = MonthlyGrowthReport.objects.filter(practice=practice).order_by('-year', '-month').first()
        if not latest_report:
            latest_report = ReportGeneratorService.generate_monthly_report(practice)

        pdf_bytes = ReportPDFService.generate_pdf(latest_report)

        filename = f"ClinicRise_Report_{practice.name.replace(' ', '_')}_{latest_report.year}_{latest_report.month:02d}.pdf"
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Content-Length'] = len(pdf_bytes)
        return response

import uuid
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from practices.models import Practice, PracticeMembership
from websites.models import ClinicWebsite
from leads.services.lead_service import LeadService
from analytics.models import WebsiteVisit
from analytics.serializers import (
    AnalyticsQueryParamSerializer,
    PublicVisitTrackSerializer,
    WebsiteVisitSerializer,
)
from analytics.services.analytics_service import AnalyticsService


def _get_active_practice(request, practice_id=None):
    """
    Retrieves and validates the active Practice tenant for the authenticated user.
    """
    if getattr(request, 'practice', None):
        return request.practice

    target_id = practice_id or request.headers.get('X-Practice-ID') or request.META.get('HTTP_X_PRACTICE_ID')
    if target_id:
        try:
            p_uuid = uuid.UUID(str(target_id).strip())
            practice = Practice.objects.filter(id=p_uuid, is_active=True).first()
            if practice:
                return practice
        except (ValueError, TypeError):
            pass

    if request.user and request.user.is_authenticated:
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


def _check_analytics_permission(request, practice):
    """Verifies that the user has an active membership in the practice."""
    if not request.user or not request.user.is_authenticated:
        return False
    return PracticeMembership.objects.filter(
        practice=practice,
        user=request.user,
        is_active=True
    ).exists()


# =====================================================================
# 1. PUBLIC WEBSITE VISIT TRACKING
# =====================================================================

class PublicVisitTrackView(APIView):
    """
    Public beacon / tracking endpoint for logging pageviews from clinic websites.
    POST /api/analytics/public/<practice_slug_or_domain>/visit/
    """
    permission_classes = [AllowAny]

    def post(self, request, practice_slug_or_domain):
        practice, website = LeadService.resolve_practice_and_website(practice_slug_or_domain)
        if not practice:
            return Response(
                {"error": f"Clinic not found for identifier '{practice_slug_or_domain}'."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = PublicVisitTrackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        visit = AnalyticsService.record_visit(
            practice=practice,
            raw_data=serializer.validated_data,
            request=request,
            website=website
        )

        return Response(
            {
                "success": True,
                "visit_id": str(visit.id),
                "traffic_channel": visit.traffic_channel,
                "traffic_source": visit.traffic_source,
                "is_unique_daily": visit.is_unique_daily,
                "message": "Website visit tracked successfully."
            },
            status=status.HTTP_201_CREATED
        )


# =====================================================================
# 2. AUTHENTICATED BASIC ANALYTICS DASHBOARD
# =====================================================================

class AnalyticsDashboardView(APIView):
    """
    Unified Basic Analytics Dashboard:
    - Website visits & unique visitors
    - Traffic sources & UTM campaigns
    - Calls & WhatsApp clicks
    - Enquiries & booking conversion
    - Funnel analysis
    - Daily trend timeseries

    GET /api/analytics/dashboard/
    GET /api/analytics/overview/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response(
                {"error": "Active practice could not be resolved. Provide 'X-Practice-ID' header."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not _check_analytics_permission(request, practice):
            return Response(
                {"error": "You do not have permission to view analytics for this practice."},
                status=status.HTTP_403_FORBIDDEN
            )

        param_serializer = AnalyticsQueryParamSerializer(data=request.query_params)
        param_serializer.is_valid(raise_exception=True)
        validated = param_serializer.validated_data

        website = None
        website_id = validated.get('website_id')
        if website_id:
            website = get_object_or_404(ClinicWebsite, id=website_id, practice=practice)

        overview = AnalyticsService.get_analytics_overview(
            practice=practice,
            website=website,
            preset=validated.get('preset', '30d'),
            date_from=str(validated['date_from']) if validated.get('date_from') else None,
            date_to=str(validated['date_to']) if validated.get('date_to') else None,
        )

        return Response(overview, status=status.HTTP_200_OK)


# =====================================================================
# 3. GRANULAR TRAFFIC SOURCES
# =====================================================================

class AnalyticsTrafficSourcesView(APIView):
    """
    Detailed traffic source attribution:
    Breakdown by channel (Organic, Direct, Social, Paid, WhatsApp, Referral)
    plus top campaigns and referring domains.

    GET /api/analytics/traffic-sources/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Provide 'X-Practice-ID' header."}, status=status.HTTP_400_BAD_REQUEST)
        if not _check_analytics_permission(request, practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        param_serializer = AnalyticsQueryParamSerializer(data=request.query_params)
        param_serializer.is_valid(raise_exception=True)
        validated = param_serializer.validated_data

        overview = AnalyticsService.get_analytics_overview(
            practice=practice,
            preset=validated.get('preset', '30d'),
            date_from=str(validated['date_from']) if validated.get('date_from') else None,
            date_to=str(validated['date_to']) if validated.get('date_to') else None,
        )

        return Response(
            {
                "period": overview["period"],
                "traffic_sources": overview["traffic_sources"],
                "device_breakdown": overview["device_breakdown"],
            },
            status=status.HTTP_200_OK
        )


# =====================================================================
# 4. RECENT VISITS & TOP PAGES LOG
# =====================================================================

class AnalyticsVisitsListView(APIView):
    """
    Recent pageview log and top visited pages.
    GET /api/analytics/visits/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Provide 'X-Practice-ID' header."}, status=status.HTTP_400_BAD_REQUEST)
        if not _check_analytics_permission(request, practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        qs = WebsiteVisit.objects.filter(practice=practice)

        channel_filter = request.query_params.get('channel')
        if channel_filter:
            qs = qs.filter(traffic_channel=channel_filter.strip())

        device_filter = request.query_params.get('device')
        if device_filter:
            qs = qs.filter(device_type=device_filter.strip())

        path_filter = request.query_params.get('path')
        if path_filter:
            qs = qs.filter(page_path__icontains=path_filter.strip())

        limit = min(int(request.query_params.get('limit', 50)), 100)
        recent_visits = qs.order_by('-created_at')[:limit]
        serializer = WebsiteVisitSerializer(recent_visits, many=True)

        return Response(
            {
                "total_count": qs.count(),
                "results": serializer.data
            },
            status=status.HTTP_200_OK
        )


# =====================================================================
# 5. PATIENT ACQUISITION CONVERSION FUNNEL
# =====================================================================

class AnalyticsFunnelView(APIView):
    """
    4-Stage Conversion Funnel:
    Website Visits -> High-Intent Actions (Calls & WhatsApp) -> Enquiries & Bookings -> Confirmed Patients

    GET /api/analytics/funnel/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Provide 'X-Practice-ID' header."}, status=status.HTTP_400_BAD_REQUEST)
        if not _check_analytics_permission(request, practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        param_serializer = AnalyticsQueryParamSerializer(data=request.query_params)
        param_serializer.is_valid(raise_exception=True)
        validated = param_serializer.validated_data

        overview = AnalyticsService.get_analytics_overview(
            practice=practice,
            preset=validated.get('preset', '30d'),
            date_from=str(validated['date_from']) if validated.get('date_from') else None,
            date_to=str(validated['date_to']) if validated.get('date_to') else None,
        )

        return Response(
            {
                "period": overview["period"],
                "conversion_funnel": overview["conversion_funnel"],
            },
            status=status.HTTP_200_OK
        )

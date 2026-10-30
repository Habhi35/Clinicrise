import uuid
from datetime import timedelta
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from practices.models import Practice, PracticeMembership
from practices.permissions import IsPracticeMember
from security.permissions import RoleChecker
from security.services.audit_service import AuditService
from security.models import AuditLog
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
from gbp.serializers import (
    GBPChecklistUpdateSerializer,
    GBPConnectionSerializer,
    GBPInsightSerializer,
    GBPItemToggleSerializer,
    GBPPostSerializer,
    GBPProfileChecklistSerializer,
    GoogleReviewSerializer,
    LocalRankKeywordSerializer,
    LocalRankSnapshotSerializer,
    ReplyReviewSerializer,
    SearchConsoleQuerySerializer,
)
from gbp.services.gbp_service import GBPService
from gbp.services.google_integration_service import GoogleIntegrationService
from gbp.services.local_rank_service import LocalRankService


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
                request.practice = membership.practice
                return membership.practice
        except (ValueError, TypeError):
            pass
        return None

    memberships = list(
        PracticeMembership.objects.filter(
            user=request.user,
            is_active=True,
            practice__is_active=True
        ).select_related('practice')[:2]
    )
    if len(memberships) == 1:
        request.practice = memberships[0].practice
        return memberships[0].practice

    return None


# =====================================================================
# 1. GBP CHECKLIST & SETUP VIEWS
# =====================================================================

class GBPChecklistView(APIView):
    """
    Evaluates Google Business Profile checklist progress and updates profile settings.
    GET /api/gbp/checklist/
    PATCH /api/gbp/checklist/
    """
    permission_classes = [IsAuthenticated, IsPracticeMember]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Practice context not found. Provide X-Practice-ID header."}, status=status.HTTP_400_BAD_REQUEST)

        evaluation = GBPService.evaluate_checklist(practice)
        return Response(evaluation, status=status.HTTP_200_OK)

    def patch(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Practice context not found. Provide X-Practice-ID header."}, status=status.HTTP_400_BAD_REQUEST)

        profile = GBPService.get_or_create_profile(practice)
        serializer = GBPChecklistUpdateSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_profile = serializer.save()

        AuditService.log(
            practice=practice,
            action="gbp.update",
            category=AuditLog.CATEGORY_CLINICAL,
            description=f"Updated Google Business Profile configuration for {practice.name}",
            actor=request.user,
            request=request
        )

        return Response(GBPProfileChecklistSerializer(updated_profile).data, status=status.HTTP_200_OK)


class GBPItemToggleView(APIView):
    """
    Toggles a manual checklist item state.
    POST /api/gbp/checklist/toggle/
    """
    permission_classes = [IsAuthenticated, IsPracticeMember]

    def post(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Practice context not found."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = GBPItemToggleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        item_key = serializer.validated_data['item_key']
        is_completed = serializer.validated_data['is_completed']

        profile = GBPService.get_or_create_profile(practice)
        profile.mark_item_completed(item_key, is_completed)

        eval_data = GBPService.evaluate_checklist(practice)
        return Response({
            "success": True,
            "item_key": item_key,
            "is_completed": is_completed,
            "progress": eval_data.get('progress'),
            "checklist": eval_data.get('checklist'),
        }, status=status.HTTP_200_OK)


class GBPSetupInformationView(APIView):
    """
    Generates structured local SEO copy, business hours, and healthcare attributes.
    GET /api/gbp/setup-info/
    """
    permission_classes = [IsAuthenticated, IsPracticeMember]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Practice context not found."}, status=status.HTTP_400_BAD_REQUEST)

        setup_data = GBPService.generate_setup_information(practice)
        return Response(setup_data, status=status.HTTP_200_OK)


class GBPReviewShortcutView(APIView):
    """
    Retrieves the direct Google Review URL for the clinic.
    GET /api/gbp/review-link/
    """
    permission_classes = [IsAuthenticated, IsPracticeMember]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Practice context not found."}, status=status.HTTP_400_BAD_REQUEST)

        setup_data = GBPService.generate_setup_information(practice)
        strategy = setup_data.get('review_strategy', {})
        review_url = strategy.get('review_url') or GBPService.get_or_create_review_link(practice)

        return Response({
            "practice_name": practice.name,
            "review_url": review_url,
            "google_review_link": review_url,
            "whatsapp_template": strategy.get('whatsapp_template', ''),
            "sms_template": strategy.get('sms_template', ''),
            "instructions": "Send this link via WhatsApp or SMS to patients after their consultation to collect 5-star Google reviews."
        }, status=status.HTTP_200_OK)


# =====================================================================
# 2. GBP API CONNECTION & SYNCHRONIZATION
# =====================================================================

class GBPConnectionView(APIView):
    """
    View or update Google Business Profile API connection credentials.
    GET /api/gbp/connection/
    POST /api/gbp/connection/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Practice context not found."}, status=status.HTTP_400_BAD_REQUEST)

        conn = GoogleIntegrationService.get_or_create_connection(practice)
        return Response(GBPConnectionSerializer(conn).data, status=status.HTTP_200_OK)

    def post(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Practice context not found."}, status=status.HTTP_400_BAD_REQUEST)

        conn = GoogleIntegrationService.get_or_create_connection(practice)
        serializer = GBPConnectionSerializer(conn, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(GBPConnectionSerializer(updated).data, status=status.HTTP_200_OK)


class GBPSyncView(APIView):
    """
    Triggers an on-demand sync of GBP insights, reviews, and Search Console data.
    POST /api/gbp/sync/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Practice context not found."}, status=status.HTTP_400_BAD_REQUEST)

        result = GoogleIntegrationService.sync_gbp_data(practice)
        return Response(result, status=status.HTTP_200_OK)


class GBPInsightsListView(APIView):
    """
    Retrieves historical daily performance insights (Search, Maps, Clicks, Calls, Directions).
    GET /api/gbp/insights/?days=30
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Practice context not found."}, status=status.HTTP_400_BAD_REQUEST)

        days = int(request.query_params.get('days', 30))
        start_date = timezone.now().date() - timedelta(days=days)

        insights = GBPInsight.objects.filter(practice=practice, date__gte=start_date).order_by('date')
        if not insights.exists():
            GoogleIntegrationService.sync_gbp_data(practice)
            insights = GBPInsight.objects.filter(practice=practice, date__gte=start_date).order_by('date')

        totals = insights.aggregate(
            total_maps=Sum('maps_impressions'),
            total_search=Sum('search_impressions'),
            total_calls=Sum('call_clicks'),
            total_directions=Sum('direction_requests'),
            total_website=Sum('website_clicks'),
            total_bookings=Sum('bookings_clicks'),
        )

        return Response({
            "summary": {
                "total_maps_views": totals['total_maps'] or 0,
                "total_search_views": totals['total_search'] or 0,
                "total_phone_calls": totals['total_calls'] or 0,
                "total_direction_requests": totals['total_directions'] or 0,
                "total_website_clicks": totals['total_website'] or 0,
                "total_bookings_clicks": totals['total_bookings'] or 0,
            },
            "daily_insights": GBPInsightSerializer(insights, many=True).data,
        }, status=status.HTTP_200_OK)


# =====================================================================
# 3. GOOGLE REVIEWS & AI REPLY ENGINE
# =====================================================================

class GoogleReviewListView(APIView):
    """
    Lists patient reviews synchronized from Google Business Profile.
    GET /api/gbp/reviews/
    Query Params: ?rating=5 | ?is_replied=false
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Practice context not found."}, status=status.HTTP_400_BAD_REQUEST)

        queryset = GoogleReview.objects.filter(practice=practice).order_by('-review_timestamp')
        if not queryset.exists():
            GoogleIntegrationService.sync_gbp_data(practice)
            queryset = GoogleReview.objects.filter(practice=practice).order_by('-review_timestamp')

        rating = request.query_params.get('rating')
        if rating:
            queryset = queryset.filter(star_rating=int(rating))

        replied = request.query_params.get('is_replied')
        if replied == 'true':
            queryset = queryset.filter(is_replied=True)
        elif replied == 'false':
            queryset = queryset.filter(is_replied=False)

        avg_rating = GoogleReview.objects.filter(practice=practice).aggregate(Avg('star_rating'))['star_rating__avg'] or 5.0

        return Response({
            "total_reviews": GoogleReview.objects.filter(practice=practice).count(),
            "average_rating": round(avg_rating, 2),
            "reviews": GoogleReviewSerializer(queryset[:50], many=True).data,
        }, status=status.HTTP_200_OK)


class GoogleReviewReplyView(APIView):
    """
    Publishes a response to a patient's Google review.
    POST /api/gbp/reviews/<pk>/reply/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Practice context not found."}, status=status.HTTP_400_BAD_REQUEST)

        review = get_object_or_404(GoogleReview, id=pk, practice=practice)
        serializer = ReplyReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updated = GoogleIntegrationService.post_review_reply(
            review=review,
            reply_text=serializer.validated_data['reply_text']
        )
        return Response(GoogleReviewSerializer(updated).data, status=status.HTTP_200_OK)


class GoogleReviewAIReplyView(APIView):
    """
    Generates a HIPAA/privacy-compliant, empathetic AI response draft for a Google review.
    POST /api/gbp/reviews/<pk>/generate-reply/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Practice context not found."}, status=status.HTTP_400_BAD_REQUEST)

        review = get_object_or_404(GoogleReview, id=pk, practice=practice)
        ai_reply = GoogleIntegrationService.generate_ai_review_reply(review)

        return Response({
            "review_id": str(review.id),
            "reviewer_name": review.reviewer_name,
            "star_rating": review.star_rating,
            "ai_suggested_reply": ai_reply,
            "compliance_note": "HIPAA & privacy compliant draft. Do not include specific diagnosis or treatment details.",
        }, status=status.HTTP_200_OK)


# =====================================================================
# 4. GOOGLE POSTS / UPDATES PUBLISHER
# =====================================================================

class GBPPostListCreateView(APIView):
    """
    List and publish updates, health tips, and offers to Google Business Profile.
    GET /api/gbp/posts/
    POST /api/gbp/posts/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Practice context not found."}, status=status.HTTP_400_BAD_REQUEST)

        posts = GBPPost.objects.filter(practice=practice).order_by('-created_at')
        return Response(GBPPostSerializer(posts, many=True).data, status=status.HTTP_200_OK)

    def post(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Practice context not found."}, status=status.HTTP_400_BAD_REQUEST)

        post = GoogleIntegrationService.publish_gbp_post(practice, request.data)
        return Response(GBPPostSerializer(post).data, status=status.HTTP_201_CREATED)


# =====================================================================
# 5. GOOGLE SEARCH CONSOLE ANALYTICS
# =====================================================================

class SearchConsoleOverviewView(APIView):
    """
    Google Search Console summary: organic clicks, impressions, CTR, and average position.
    GET /api/gbp/search-console/overview/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Practice context not found."}, status=status.HTTP_400_BAD_REQUEST)

        queries = SearchConsoleQuery.objects.filter(practice=practice)
        if not queries.exists():
            GoogleIntegrationService.sync_search_console(practice)
            queries = SearchConsoleQuery.objects.filter(practice=practice)

        totals = queries.aggregate(
            total_clicks=Sum('clicks'),
            total_impressions=Sum('impressions'),
            avg_position=Avg('position')
        )
        total_clicks = totals['total_clicks'] or 0
        total_imps = totals['total_impressions'] or 0
        avg_pos = round(totals['avg_position'] or 0.0, 1)
        avg_ctr = round((total_clicks / total_imps * 100), 2) if total_imps else 0.0

        top_queries = queries.order_by('-clicks')[:5]

        return Response({
            "total_organic_clicks": total_clicks,
            "total_impressions": total_imps,
            "average_ctr_percentage": avg_ctr,
            "average_position": avg_pos,
            "top_queries": SearchConsoleQuerySerializer(top_queries, many=True).data,
        }, status=status.HTTP_200_OK)


class SearchConsoleQueriesListView(APIView):
    """
    Detailed breakdown of organic medical search queries from Google Search Console.
    GET /api/gbp/search-console/queries/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Practice context not found."}, status=status.HTTP_400_BAD_REQUEST)

        queries = SearchConsoleQuery.objects.filter(practice=practice).order_by('-clicks')
        if not queries.exists():
            GoogleIntegrationService.sync_search_console(practice)
            queries = SearchConsoleQuery.objects.filter(practice=practice).order_by('-clicks')

        return Response(SearchConsoleQuerySerializer(queries, many=True).data, status=status.HTTP_200_OK)


# =====================================================================
# 6. LOCAL 3-PACK RANK TRACKING ENGINE
# =====================================================================

class LocalRankKeywordListCreateView(APIView):
    """
    List and add target local SEO search keywords for Google 3-Pack rank tracking.
    GET /api/gbp/rank-tracking/keywords/
    POST /api/gbp/rank-tracking/keywords/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Practice context not found."}, status=status.HTTP_400_BAD_REQUEST)

        keywords = LocalRankKeyword.objects.filter(practice=practice, is_active=True).order_by('current_pack_rank')
        if not keywords.exists():
            LocalRankService.seed_default_keywords(practice)
            keywords = LocalRankKeyword.objects.filter(practice=practice, is_active=True).order_by('current_pack_rank')

        return Response(LocalRankKeywordSerializer(keywords, many=True).data, status=status.HTTP_200_OK)

    def post(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Practice context not found."}, status=status.HTTP_400_BAD_REQUEST)

        kw_text = request.data.get('keyword', '').strip()
        if not kw_text:
            return Response({"error": "keyword text is required."}, status=status.HTTP_400_BAD_REQUEST)

        target_city = request.data.get('target_city', practice.city or 'Bengaluru')
        radius = int(request.data.get('target_radius_km', 10))

        keyword = LocalRankService.add_keyword(
            practice=practice,
            keyword=kw_text,
            target_city=target_city,
            target_radius_km=radius
        )
        return Response(LocalRankKeywordSerializer(keyword).data, status=status.HTTP_201_CREATED)


class LocalRankKeywordDetailView(APIView):
    """
    Delete / untrack a local SEO keyword.
    DELETE /api/gbp/rank-tracking/keywords/<pk>/
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Practice context not found."}, status=status.HTTP_400_BAD_REQUEST)

        kw = get_object_or_404(LocalRankKeyword, id=pk, practice=practice)
        kw.is_active = False
        kw.save(update_fields=['is_active'])
        return Response({"message": f"Keyword '{kw.keyword}' removed from tracking."}, status=status.HTTP_200_OK)


class LocalRankCheckRunView(APIView):
    """
    Executes an on-demand rank tracking check across all active keywords.
    POST /api/gbp/rank-tracking/check/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Practice context not found."}, status=status.HTTP_400_BAD_REQUEST)

        snapshots = LocalRankService.run_local_rank_check(practice)
        return Response({
            "success": True,
            "status": "success",
            "keywords_checked": len(snapshots),
            "snapshots": LocalRankSnapshotSerializer(snapshots, many=True).data,
        }, status=status.HTTP_200_OK)


class LocalRankOverviewView(APIView):
    """
    Local SEO 3-Pack overview dashboard (top 3 count, average rank, competitor pack).
    GET /api/gbp/rank-tracking/overview/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Practice context not found."}, status=status.HTTP_400_BAD_REQUEST)

        overview = LocalRankService.get_local_rank_overview(practice)
        return Response(overview, status=status.HTTP_200_OK)

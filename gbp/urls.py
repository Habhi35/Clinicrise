from django.urls import path
from gbp.views import (
    GBPChecklistView,
    GBPConnectionView,
    GBPInsightsListView,
    GBPItemToggleView,
    GBPPostListCreateView,
    GBPReviewShortcutView,
    GBPSetupInformationView,
    GBPSyncView,
    GoogleReviewAIReplyView,
    GoogleReviewListView,
    GoogleReviewReplyView,
    LocalRankCheckRunView,
    LocalRankKeywordDetailView,
    LocalRankKeywordListCreateView,
    LocalRankOverviewView,
    SearchConsoleOverviewView,
    SearchConsoleQueriesListView,
)

app_name = 'gbp'

urlpatterns = [
    # ---------------------------------------------------------
    # 1. Google Business Profile Checklist & Setup
    # ---------------------------------------------------------
    path('checklist/', GBPChecklistView.as_view(), name='checklist'),
    path('checklist/toggle/', GBPItemToggleView.as_view(), name='checklist_toggle'),
    path('setup-info/', GBPSetupInformationView.as_view(), name='setup_info'),
    path('review-link/', GBPReviewShortcutView.as_view(), name='review_link'),

    # ---------------------------------------------------------
    # 2. GBP API Connection & Synchronization
    # ---------------------------------------------------------
    path('connection/', GBPConnectionView.as_view(), name='connection'),
    path('sync/', GBPSyncView.as_view(), name='sync'),
    path('insights/', GBPInsightsListView.as_view(), name='insights'),

    # ---------------------------------------------------------
    # 3. Google Patient Reviews & AI Replies
    # ---------------------------------------------------------
    path('reviews/', GoogleReviewListView.as_view(), name='reviews'),
    path('reviews/<uuid:pk>/reply/', GoogleReviewReplyView.as_view(), name='review_reply'),
    path('reviews/<uuid:pk>/generate-reply/', GoogleReviewAIReplyView.as_view(), name='review_generate_reply'),

    # ---------------------------------------------------------
    # 4. Google Posts & Clinical Updates
    # ---------------------------------------------------------
    path('posts/', GBPPostListCreateView.as_view(), name='posts'),

    # ---------------------------------------------------------
    # 5. Google Search Console Analytics
    # ---------------------------------------------------------
    path('search-console/overview/', SearchConsoleOverviewView.as_view(), name='search_console_overview'),
    path('search-console/queries/', SearchConsoleQueriesListView.as_view(), name='search_console_queries'),

    # ---------------------------------------------------------
    # 6. Local SEO 3-Pack Rank Tracking
    # ---------------------------------------------------------
    path('rank-tracking/keywords/', LocalRankKeywordListCreateView.as_view(), name='rank_keywords'),
    path('rank-tracking/keywords/<uuid:pk>/', LocalRankKeywordDetailView.as_view(), name='rank_keyword_detail'),
    path('rank-tracking/check/', LocalRankCheckRunView.as_view(), name='rank_check'),
    path('rank-tracking/overview/', LocalRankOverviewView.as_view(), name='rank_overview'),
]

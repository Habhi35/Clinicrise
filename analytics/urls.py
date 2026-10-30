from django.urls import path
from analytics.views import (
    AnalyticsDashboardView,
    AnalyticsFunnelView,
    AnalyticsTrafficSourcesView,
    AnalyticsVisitsListView,
    PublicVisitTrackView,
)

app_name = 'analytics'

urlpatterns = [
    # ---------------------------------------------------------
    # Public Website Pageview & Visit Tracking
    # ---------------------------------------------------------
    path('public/<str:practice_slug_or_domain>/visit/', PublicVisitTrackView.as_view(), name='public_visit_track'),

    # ---------------------------------------------------------
    # Authenticated Basic Analytics Cockpit & Metrics
    # ---------------------------------------------------------
    path('dashboard/', AnalyticsDashboardView.as_view(), name='dashboard'),
    path('overview/', AnalyticsDashboardView.as_view(), name='overview'),
    path('traffic-sources/', AnalyticsTrafficSourcesView.as_view(), name='traffic_sources'),
    path('visits/', AnalyticsVisitsListView.as_view(), name='visits_list'),
    path('funnel/', AnalyticsFunnelView.as_view(), name='funnel'),
]

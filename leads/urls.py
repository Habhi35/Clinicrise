from django.urls import path
from leads.views import (
    LeadActivityListCreateView,
    LeadClickEventListView,
    LeadConsentUpdateView,
    LeadDetailView,
    LeadInboxView,
    LeadStatsView,
    LeadStatusUpdateView,
    PublicClickEventTrackView,
    PublicConsentOptOutView,
    PublicEnquirySubmitView,
)

app_name = 'leads'

urlpatterns = [
    # ---------------------------------------------------------
    # Public Patient Lead Capture, Click Tracking & Opt-Out
    # ---------------------------------------------------------
    path('public/<str:practice_slug_or_domain>/inquire/', PublicEnquirySubmitView.as_view(), name='public_inquire'),
    path('public/<str:practice_slug_or_domain>/click-event/', PublicClickEventTrackView.as_view(), name='public_click_event'),
    path('public/<str:practice_slug_or_domain>/opt-out/', PublicConsentOptOutView.as_view(), name='public_opt_out'),

    # ---------------------------------------------------------
    # Authenticated Lead Inbox & CRM Cockpit
    # ---------------------------------------------------------
    path('inbox/', LeadInboxView.as_view(), name='lead_inbox'),
    path('', LeadInboxView.as_view(), name='lead_list_create'),
    path('stats/', LeadStatsView.as_view(), name='lead_stats'),
    path('events/', LeadClickEventListView.as_view(), name='lead_events'),

    # ---------------------------------------------------------
    # Lead Actions, Status Transitions & Timeline
    # ---------------------------------------------------------
    path('<uuid:pk>/', LeadDetailView.as_view(), name='lead_detail'),
    path('<uuid:pk>/status/', LeadStatusUpdateView.as_view(), name='lead_status_update'),
    path('<uuid:pk>/consent/', LeadConsentUpdateView.as_view(), name='lead_consent_update'),
    path('<uuid:lead_id>/activities/', LeadActivityListCreateView.as_view(), name='lead_activities'),
]

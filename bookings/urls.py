from django.urls import path
from bookings.views import (
    BookingCancelView,
    BookingConfirmView,
    BookingRejectView,
    BookingRequestDetailView,
    BookingRequestListView,
    BookingRescheduleView,
    BookingStatsView,
    BookingVisitStatusView,
    CapacityCheckView,
    DoctorSessionCapacityDetailView,
    DoctorSessionCapacityListCreateView,
    PracticeLocationDetailView,
    PracticeLocationListCreateView,
    PublicAvailabilityOverviewView,
    PublicBookingRequestView,
    PublicBookingTrackView,
)

app_name = 'bookings'

urlpatterns = [
    # ---------------------------------------------------------
    # Public Patient Booking, Availability & Tracking
    # ---------------------------------------------------------
    path('public/<str:practice_slug_or_domain>/request/', PublicBookingRequestView.as_view(), name='public_request'),
    path('public/<str:practice_slug_or_domain>/availability/', PublicAvailabilityOverviewView.as_view(), name='public_availability'),
    path('public/<str:practice_slug_or_domain>/track/<str:booking_reference>/', PublicBookingTrackView.as_view(), name='public_track'),

    # ---------------------------------------------------------
    # Practice Locations & Branches
    # ---------------------------------------------------------
    path('locations/', PracticeLocationListCreateView.as_view(), name='location_list_create'),
    path('locations/<uuid:pk>/', PracticeLocationDetailView.as_view(), name='location_detail'),

    # ---------------------------------------------------------
    # Doctor Session Capacities & Mode Configuration
    # ---------------------------------------------------------
    path('capacities/', DoctorSessionCapacityListCreateView.as_view(), name='capacity_list_create'),
    path('capacities/<uuid:pk>/', DoctorSessionCapacityDetailView.as_view(), name='capacity_detail'),

    # ---------------------------------------------------------
    # Appointment Management & Clinic Confirmation Workflow
    # ---------------------------------------------------------
    path('', BookingRequestListView.as_view(), name='booking_list_create'),
    path('stats/', BookingStatsView.as_view(), name='booking_stats'),
    path('capacity-check/', CapacityCheckView.as_view(), name='capacity_check'),
    path('<uuid:pk>/', BookingRequestDetailView.as_view(), name='booking_detail'),
    path('<uuid:pk>/confirm/', BookingConfirmView.as_view(), name='booking_confirm'),
    path('<uuid:pk>/reschedule/', BookingRescheduleView.as_view(), name='booking_reschedule'),
    path('<uuid:pk>/cancel/', BookingCancelView.as_view(), name='booking_cancel'),
    path('<uuid:pk>/reject/', BookingRejectView.as_view(), name='booking_reject'),
    path('<uuid:pk>/visit-status/', BookingVisitStatusView.as_view(), name='booking_visit_status'),
]

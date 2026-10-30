import datetime
import uuid
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from practices.models import DoctorProfile, Practice, PracticeMembership, PracticeService
from leads.services.lead_service import LeadService
from bookings.models import (
    BookingRequest,
    BookingTimeline,
    DoctorSessionCapacity,
    PracticeLocation,
)
from bookings.serializers import (
    BookingActionReasonSerializer,
    BookingConfirmSerializer,
    BookingRequestDetailSerializer,
    BookingRequestSerializer,
    BookingRescheduleSerializer,
    DoctorSessionCapacitySerializer,
    PracticeLocationSerializer,
    PublicBookingRequestSerializer,
)
from bookings.services.booking_service import BookingService
from bookings.services.capacity_service import CapacityService


def _get_active_practice(request, practice_id=None):
    """Retrieves and validates active Practice tenant for the request."""
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


def _check_booking_permission(request, practice):
    """Checks user membership in practice."""
    if not request.user or not request.user.is_authenticated:
        return False
    return PracticeMembership.objects.filter(
        practice=practice,
        user=request.user,
        is_active=True
    ).exists()


def _is_practice_admin(request, practice):
    """Checks if user is Owner or Admin in the practice."""
    if not request.user or not request.user.is_authenticated:
        return False
    return PracticeMembership.objects.filter(
        practice=practice,
        user=request.user,
        is_active=True,
        role__in=[PracticeMembership.ROLE_OWNER, PracticeMembership.ROLE_ADMIN]
    ).exists()


# =====================================================================
# 1. PUBLIC PATIENT BOOKING VIEWS
# =====================================================================

class PublicBookingRequestView(APIView):
    """
    Public endpoint for patients to submit an appointment booking request.
    POST /api/bookings/public/<practice_slug_or_domain>/request/
    """
    permission_classes = [AllowAny]

    def post(self, request, practice_slug_or_domain):
        practice, _ = LeadService.resolve_practice_and_website(practice_slug_or_domain)
        if not practice:
            return Response(
                {"error": f"Clinic not found for identifier '{practice_slug_or_domain}'."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = PublicBookingRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Resolve location, doctor, service if specified
        location = None
        if data.get('location_id'):
            location = PracticeLocation.objects.filter(id=data['location_id'], practice=practice, is_active=True).first()

        doctor = None
        if data.get('doctor_id'):
            doctor = DoctorProfile.objects.filter(
                id=data['doctor_id'],
                user__practice_memberships__practice=practice,
                user__practice_memberships__is_active=True
            ).first()

        service = None
        if data.get('service_id'):
            service = PracticeService.objects.filter(id=data['service_id'], practice=practice, is_active=True).first()

        booking_data = {
            **data,
            'location': location,
            'doctor': doctor,
            'service': service,
        }

        booking = BookingService.create_booking(
            practice=practice,
            data=booking_data,
            source='website'
        )

        return Response(
            {
                "success": True,
                "message": (
                    f"Booking request received! Your reference is {booking.booking_reference}. "
                    f"{'Appointment Confirmed!' if booking.status == BookingRequest.STATUS_CONFIRMED else 'The clinic will confirm your appointment shortly.'}"
                ),
                "booking_reference": booking.booking_reference,
                "status": booking.status,
                "status_display": booking.get_status_display(),
                "booking_mode": booking.booking_mode,
                "appointment_date": str(booking.appointment_date) if booking.appointment_date else None,
                "token_number": booking.token_number,
                "start_time": booking.start_time.strftime('%H:%M') if booking.start_time else None,
                "clinic_name": practice.name,
            },
            status=status.HTTP_201_CREATED
        )


class PublicAvailabilityOverviewView(APIView):
    """
    Public availability inspector: returns time slots and OPD token session status.
    GET /api/bookings/public/<practice_slug_or_domain>/availability/?doctor_id=<uuid>&date=YYYY-MM-DD
    """
    permission_classes = [AllowAny]

    def get(self, request, practice_slug_or_domain):
        practice, _ = LeadService.resolve_practice_and_website(practice_slug_or_domain)
        if not practice:
            return Response(
                {"error": f"Clinic not found for identifier '{practice_slug_or_domain}'."},
                status=status.HTTP_404_NOT_FOUND
            )

        doctor_id = request.query_params.get('doctor_id')
        date_str = request.query_params.get('date')

        if not doctor_id:
            return Response({"error": "doctor_id query parameter is required."}, status=status.HTTP_400_BAD_REQUEST)

        doctor = get_object_or_404(
            DoctorProfile,
            id=doctor_id,
            user__practice_memberships__practice=practice,
            user__practice_memberships__is_active=True
        )

        try:
            target_date = datetime.date.fromisoformat(date_str) if date_str else timezone.now().date()
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        overview = CapacityService.get_availability_overview(practice, doctor, target_date)
        return Response(overview, status=status.HTTP_200_OK)


class PublicBookingTrackView(APIView):
    """
    Patient self-service tracking for confirmation status, token number or assigned slot.
    GET /api/bookings/public/<practice_slug_or_domain>/track/<booking_reference>/
    """
    permission_classes = [AllowAny]

    def get(self, request, practice_slug_or_domain, booking_reference):
        practice, _ = LeadService.resolve_practice_and_website(practice_slug_or_domain)
        if not practice:
            return Response({"error": "Clinic not found."}, status=status.HTTP_404_NOT_FOUND)

        booking = BookingRequest.objects.filter(
            practice=practice,
            booking_reference=booking_reference.strip().upper()
        ).select_related('doctor__user', 'location', 'service').first()

        if not booking:
            return Response({"error": f"Booking reference '{booking_reference}' not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response(BookingRequestSerializer(booking).data, status=status.HTTP_200_OK)


# =====================================================================
# 2. LOCATIONS MANAGEMENT (AUTHENTICATED)
# =====================================================================

class PracticeLocationListCreateView(APIView):
    """
    List and manage clinic locations / branches.
    GET /api/bookings/locations/
    POST /api/bookings/locations/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Provide 'X-Practice-ID' header."}, status=status.HTTP_400_BAD_REQUEST)
        if not _check_booking_permission(request, practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        locations = PracticeLocation.objects.filter(practice=practice)
        serializer = PracticeLocationSerializer(locations, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Provide 'X-Practice-ID' header."}, status=status.HTTP_400_BAD_REQUEST)
        if not _is_practice_admin(request, practice):
            return Response({"error": "Only clinic administrators can create locations."}, status=status.HTTP_403_FORBIDDEN)

        serializer = PracticeLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        location = serializer.save(practice=practice)
        return Response(PracticeLocationSerializer(location).data, status=status.HTTP_201_CREATED)


class PracticeLocationDetailView(APIView):
    """
    Retrieve, update or delete a clinic branch location.
    GET /api/bookings/locations/<pk>/
    PATCH /api/bookings/locations/<pk>/
    DELETE /api/bookings/locations/<pk>/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        location = get_object_or_404(PracticeLocation, id=pk)
        if not _check_booking_permission(request, location.practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        return Response(PracticeLocationSerializer(location).data, status=status.HTTP_200_OK)

    def patch(self, request, pk):
        location = get_object_or_404(PracticeLocation, id=pk)
        if not _is_practice_admin(request, location.practice):
            return Response({"error": "Only administrators can update locations."}, status=status.HTTP_403_FORBIDDEN)

        serializer = PracticeLocationSerializer(location, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        location = get_object_or_404(PracticeLocation, id=pk)
        if not _is_practice_admin(request, location.practice):
            return Response({"error": "Only administrators can delete locations."}, status=status.HTTP_403_FORBIDDEN)

        location.delete()
        return Response({"success": True, "message": "Location removed."}, status=status.HTTP_200_OK)


# =====================================================================
# 3. DOCTOR SESSION CAPACITIES & MODES (AUTHENTICATED)
# =====================================================================

class DoctorSessionCapacityListCreateView(APIView):
    """
    Configure session capacity limits and scheduling mode (slot vs token) per doctor.
    GET /api/bookings/capacities/
    POST /api/bookings/capacities/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Provide 'X-Practice-ID' header."}, status=status.HTTP_400_BAD_REQUEST)
        if not _check_booking_permission(request, practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        capacities = DoctorSessionCapacity.objects.filter(practice=practice).select_related('doctor__user', 'location')
        serializer = DoctorSessionCapacitySerializer(capacities, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Provide 'X-Practice-ID' header."}, status=status.HTTP_400_BAD_REQUEST)
        if not _is_practice_admin(request, practice):
            return Response({"error": "Admin permission required."}, status=status.HTTP_403_FORBIDDEN)

        serializer = DoctorSessionCapacitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        capacity = serializer.save(practice=practice)
        return Response(DoctorSessionCapacitySerializer(capacity).data, status=status.HTTP_201_CREATED)


class DoctorSessionCapacityDetailView(APIView):
    """
    Update or delete capacity rules for a doctor's session.
    PATCH /api/bookings/capacities/<pk>/
    DELETE /api/bookings/capacities/<pk>/
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        capacity = get_object_or_404(DoctorSessionCapacity, id=pk)
        if not _is_practice_admin(request, capacity.practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        serializer = DoctorSessionCapacitySerializer(capacity, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        capacity = get_object_or_404(DoctorSessionCapacity, id=pk)
        if not _is_practice_admin(request, capacity.practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        capacity.delete()
        return Response({"success": True, "message": "Capacity rule removed."}, status=status.HTTP_200_OK)


# =====================================================================
# 4. BOOKING OPERATIONS & CLINIC CONFIRMATION (AUTHENTICATED)
# =====================================================================

class BookingRequestListView(APIView):
    """
    Clinic appointment dashboard: lists and filters booking requests.
    GET /api/bookings/
    POST /api/bookings/ - Frontdesk walk-in or phone-in booking creation
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Provide 'X-Practice-ID' header."}, status=status.HTTP_400_BAD_REQUEST)
        if not _check_booking_permission(request, practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        qs = BookingRequest.objects.filter(practice=practice).select_related('doctor__user', 'location', 'service')

        # Filters
        status_param = request.query_params.get('status')
        if status_param:
            statuses = [s.strip() for s in status_param.split(',') if s.strip()]
            qs = qs.filter(status__in=statuses)

        doctor_param = request.query_params.get('doctor')
        if doctor_param:
            qs = qs.filter(doctor_id=doctor_param.strip())

        location_param = request.query_params.get('location')
        if location_param:
            qs = qs.filter(location_id=location_param.strip())

        date_param = request.query_params.get('date')
        if date_param:
            qs = qs.filter(appointment_date=date_param.strip())

        date_from = request.query_params.get('date_from')
        if date_from:
            qs = qs.filter(appointment_date__gte=date_from.strip())

        date_to = request.query_params.get('date_to')
        if date_to:
            qs = qs.filter(appointment_date__lte=date_to.strip())

        mode_param = request.query_params.get('mode')
        if mode_param:
            qs = qs.filter(booking_mode=mode_param.strip())

        search_query = request.query_params.get('search')
        if search_query:
            q = search_query.strip()
            qs = qs.filter(
                Q(patient_name__icontains=q) |
                Q(phone_number__icontains=q) |
                Q(email__icontains=q) |
                Q(booking_reference__icontains=q) |
                Q(chief_complaint__icontains=q)
            )

        ordering = request.query_params.get('ordering', '-appointment_date')
        if ordering in ['appointment_date', '-appointment_date', 'created_at', '-created_at', 'status', 'token_number']:
            qs = qs.order_by(ordering)

        serializer = BookingRequestSerializer(qs[:100], many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Provide 'X-Practice-ID' header."}, status=status.HTTP_400_BAD_REQUEST)
        if not _check_booking_permission(request, practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        # Resolve relations from payload
        location_id = request.data.get('location') or request.data.get('location_id')
        location = PracticeLocation.objects.filter(id=location_id, practice=practice).first() if location_id else None

        doctor_id = request.data.get('doctor') or request.data.get('doctor_id')
        doctor = DoctorProfile.objects.filter(
            id=doctor_id,
            user__practice_memberships__practice=practice,
            user__practice_memberships__is_active=True
        ).first() if doctor_id else None

        service_id = request.data.get('service') or request.data.get('service_id')
        service = PracticeService.objects.filter(id=service_id, practice=practice).first() if service_id else None

        data = {
            **request.data,
            'location': location,
            'doctor': doctor,
            'service': service,
        }

        booking = BookingService.create_booking(
            practice=practice,
            data=data,
            user=request.user,
            source=request.data.get('source', BookingRequest.SOURCE_FRONTDESK)
        )

        return Response(BookingRequestDetailSerializer(booking).data, status=status.HTTP_201_CREATED)


class BookingRequestDetailView(APIView):
    """
    Detailed booking inspect, edit, or archive.
    GET /api/bookings/<pk>/
    PATCH /api/bookings/<pk>/
    DELETE /api/bookings/<pk>/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        booking = get_object_or_404(BookingRequest, id=pk)
        if not _check_booking_permission(request, booking.practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        return Response(BookingRequestDetailSerializer(booking).data, status=status.HTTP_200_OK)

    def patch(self, request, pk):
        booking = get_object_or_404(BookingRequest, id=pk)
        if not _check_booking_permission(request, booking.practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        allowed_fields = [
            'patient_name', 'phone_number', 'email', 'gender', 'age',
            'chief_complaint', 'patient_notes', 'clinic_notes'
        ]
        for field in allowed_fields:
            if field in request.data:
                setattr(booking, field, request.data[field])

        booking.save()
        return Response(BookingRequestDetailSerializer(booking).data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        booking = get_object_or_404(BookingRequest, id=pk)
        if not _is_practice_admin(request, booking.practice):
            return Response({"error": "Admin permission required."}, status=status.HTTP_403_FORBIDDEN)

        booking.delete()
        return Response({"success": True, "message": "Booking removed."}, status=status.HTTP_200_OK)


class BookingConfirmView(APIView):
    """
    Clinic confirmation endpoint for booking requests.
    Assigns final slot or OPD token number with capacity enforcement.
    POST /api/bookings/<pk>/confirm/
    Payload: {"confirmed_date": "2026-10-25", "start_time": "10:15:00", "end_time": "10:30:00"}
    Or in Token Mode: {"confirmed_date": "2026-10-25", "session_name": "Morning OPD"}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        booking = get_object_or_404(BookingRequest, id=pk)
        if not _check_booking_permission(request, booking.practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        serializer = BookingConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            confirmed_booking = BookingService.confirm_booking(
                booking=booking,
                user=request.user,
                confirmed_date=data.get('confirmed_date'),
                start_time=data.get('start_time'),
                end_time=data.get('end_time'),
                token_number=data.get('token_number'),
                session_name=data.get('session_name'),
                clinic_notes=data.get('clinic_notes', '')
            )
            return Response(BookingRequestDetailSerializer(confirmed_booking).data, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class BookingRescheduleView(APIView):
    """
    Reschedule an appointment with capacity validation.
    POST /api/bookings/<pk>/reschedule/
    Payload: {"new_date": "2026-10-28", "new_start_time": "11:00:00", "reason": "Doctor requested shift"}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        booking = get_object_or_404(BookingRequest, id=pk)
        if not _check_booking_permission(request, booking.practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        serializer = BookingRescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            rescheduled = BookingService.reschedule_booking(
                booking=booking,
                user=request.user,
                new_date=data['new_date'],
                new_start_time=data.get('new_start_time'),
                new_end_time=data.get('new_end_time'),
                new_session=data.get('new_session'),
                reason=data.get('reason', '')
            )
            return Response(BookingRequestDetailSerializer(rescheduled).data, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class BookingCancelView(APIView):
    """
    Cancel an appointment.
    POST /api/bookings/<pk>/cancel/
    Payload: {"reason": "Patient requested cancellation"}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        booking = get_object_or_404(BookingRequest, id=pk)
        if not _check_booking_permission(request, booking.practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        serializer = BookingActionReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cancelled = BookingService.cancel_booking(
            booking=booking,
            user=request.user,
            reason=serializer.validated_data['reason']
        )
        return Response(BookingRequestDetailSerializer(cancelled).data, status=status.HTTP_200_OK)


class BookingRejectView(APIView):
    """
    Decline an unconfirmed booking request.
    POST /api/bookings/<pk>/reject/
    Payload: {"reason": "Doctor unavailable due to emergency surgery"}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        booking = get_object_or_404(BookingRequest, id=pk)
        if not _check_booking_permission(request, booking.practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        serializer = BookingActionReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        rejected = BookingService.reject_booking(
            booking=booking,
            user=request.user,
            reason=serializer.validated_data['reason']
        )
        return Response(BookingRequestDetailSerializer(rejected).data, status=status.HTTP_200_OK)


class BookingVisitStatusView(APIView):
    """
    Update patient visit status: checked_in, in_consultation, or completed.
    POST /api/bookings/<pk>/visit-status/
    Payload: {"status": "checked_in", "notes": "Patient arrived, waiting in lounge"}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        booking = get_object_or_404(BookingRequest, id=pk)
        if not _check_booking_permission(request, booking.practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        new_status = request.data.get('status')
        valid_statuses = [
            BookingRequest.STATUS_CHECKED_IN,
            BookingRequest.STATUS_IN_CONSULTATION,
            BookingRequest.STATUS_COMPLETED,
            BookingRequest.STATUS_NO_SHOW
        ]
        if new_status not in valid_statuses:
            return Response(
                {"error": f"Invalid visit status. Choose from: {valid_statuses}."},
                status=status.HTTP_400_BAD_REQUEST
            )

        updated = BookingService.update_visit_status(
            booking=booking,
            new_status=new_status,
            user=request.user,
            notes=request.data.get('notes', '')
        )
        return Response(BookingRequestDetailSerializer(updated).data, status=status.HTTP_200_OK)


class CapacityCheckView(APIView):
    """
    Staff query tool to check real-time availability and capacity for a doctor/date/slot.
    GET /api/bookings/capacity-check/?doctor_id=<uuid>&date=YYYY-MM-DD&mode=token&session=Morning+OPD
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Provide 'X-Practice-ID' header."}, status=status.HTTP_400_BAD_REQUEST)
        if not _check_booking_permission(request, practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        doctor = get_object_or_404(
            DoctorProfile,
            id=doctor_id,
            user__practice_memberships__practice=practice,
            user__practice_memberships__is_active=True
        ) if doctor_id else None

        date_str = request.query_params.get('date')
        if not date_str:
            return Response({"error": "date parameter is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            target_date = datetime.date.fromisoformat(date_str)
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        booking_mode = request.query_params.get('mode', BookingRequest.SCHEDULING_MODE_SLOT)
        session_name = request.query_params.get('session', '')
        start_time_str = request.query_params.get('start_time')
        start_time = datetime.time.fromisoformat(start_time_str) if start_time_str else None

        result = CapacityService.check_capacity(
            practice=practice,
            doctor=doctor,
            appointment_date=target_date,
            booking_mode=booking_mode,
            session_name=session_name,
            start_time=start_time
        )
        return Response(result, status=status.HTTP_200_OK)


class BookingStatsView(APIView):
    """
    Appointment and token queue statistics.
    GET /api/bookings/stats/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Provide 'X-Practice-ID' header."}, status=status.HTTP_400_BAD_REQUEST)
        if not _check_booking_permission(request, practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        stats = BookingService.get_booking_stats(practice)
        return Response(stats, status=status.HTTP_200_OK)

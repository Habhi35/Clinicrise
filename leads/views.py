import uuid
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from practices.models import Practice, PracticeMembership
from leads.models import ClickEvent, Lead, LeadActivity
from leads.serializers import (
    ClickEventSerializer,
    LeadActivityCreateSerializer,
    LeadActivitySerializer,
    LeadConsentUpdateSerializer,
    LeadCreateSerializer,
    LeadDetailSerializer,
    LeadSerializer,
    LeadStatusUpdateSerializer,
    PublicClickEventSerializer,
    PublicConsentOptOutSerializer,
    PublicEnquirySerializer,
)
from leads.services.event_service import EventTrackingService
from leads.services.lead_service import LeadService


def _get_active_practice(request, practice_id=None):
    """
    Retrieves and validates the active Practice tenant for the authenticated user.
    Uses request.practice injected by TenantIsolationMiddleware or resolves from header/membership.
    """
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

    # Default to single active practice if user only belongs to one
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


def _check_lead_permission(request, practice):
    """Verifies that the user has an active membership in the practice."""
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
# 1. PUBLIC LEAD INTAKE & CLICK EVENT VIEWS
# =====================================================================

class PublicEnquirySubmitView(APIView):
    """
    Public endpoint for prospective patients to submit enquiry / appointment request forms.
    POST /api/leads/public/<practice_slug_or_domain>/inquire/
    """
    permission_classes = [AllowAny]

    def post(self, request, practice_slug_or_domain):
        practice, website = LeadService.resolve_practice_and_website(practice_slug_or_domain)
        if not practice:
            return Response(
                {"error": f"Clinic not found for identifier '{practice_slug_or_domain}'."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = PublicEnquirySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        lead = LeadService.create_lead_from_enquiry(
            practice=practice,
            data=serializer.validated_data,
            request=request,
            website=website
        )

        return Response(
            {
                "success": True,
                "message": f"Thank you! Your enquiry has been received by {practice.name}. A representative will contact you shortly.",
                "lead_id": str(lead.id),
                "clinic_name": practice.name,
                "consent_recorded": lead.consent_given,
            },
            status=status.HTTP_201_CREATED
        )


class PublicClickEventTrackView(APIView):
    """
    Public analytics endpoint for Call and WhatsApp click events from clinic websites & profiles.
    POST /api/leads/public/<practice_slug_or_domain>/click-event/
    """
    permission_classes = [AllowAny]

    def post(self, request, practice_slug_or_domain):
        practice, website = LeadService.resolve_practice_and_website(practice_slug_or_domain)
        if not practice:
            return Response(
                {"error": f"Clinic not found for identifier '{practice_slug_or_domain}'."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = PublicClickEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        event, lead = EventTrackingService.track_click(
            practice=practice,
            data=serializer.validated_data,
            request=request,
            website=website
        )

        return Response(
            {
                "success": True,
                "event_id": str(event.id),
                "event_type": event.event_type,
                "lead_id": str(lead.id) if lead else None,
                "message": "Click event recorded successfully."
            },
            status=status.HTTP_201_CREATED
        )


class PublicConsentOptOutView(APIView):
    """
    Public privacy compliance endpoint allowing patients to withdraw communications consent.
    POST /api/leads/public/<practice_slug_or_domain>/opt-out/
    """
    permission_classes = [AllowAny]

    def post(self, request, practice_slug_or_domain):
        practice, _ = LeadService.resolve_practice_and_website(practice_slug_or_domain)
        if not practice:
            return Response(
                {"error": f"Clinic not found for identifier '{practice_slug_or_domain}'."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = PublicConsentOptOutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data['phone_number'].strip()
        reason = serializer.validated_data.get('reason', 'Public opt-out request')

        leads = Lead.objects.filter(practice=practice, phone_number=phone_number)
        updated_count = 0
        for lead in leads:
            lead.withdraw_consent(reason=reason)
            updated_count += 1

        return Response(
            {
                "success": True,
                "message": f"Consent successfully withdrawn for {phone_number}. You will no longer receive communications from {practice.name}.",
                "records_updated": updated_count
            },
            status=status.HTTP_200_OK
        )


# =====================================================================
# 2. AUTHENTICATED LEAD INBOX & CRM VIEWS
# =====================================================================

class LeadInboxView(APIView):
    """
    Multi-tenant Lead Inbox for practice staff, doctors, and clinic administrators.
    GET /api/leads/inbox/ - List and filter leads
    POST /api/leads/ - Manually log a walk-in / phone-in lead
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response(
                {"error": "Active practice not identified. Provide 'X-Practice-ID' header."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not _check_lead_permission(request, practice):
            return Response({"error": "Permission denied for this practice."}, status=status.HTTP_403_FORBIDDEN)

        qs = Lead.objects.filter(practice=practice).select_related('assigned_to')

        # Filter: Status
        status_param = request.query_params.get('status')
        if status_param:
            statuses = [s.strip() for s in status_param.split(',') if s.strip()]
            qs = qs.filter(status__in=statuses)

        # Filter: Source
        source_param = request.query_params.get('source')
        if source_param:
            sources = [s.strip() for s in source_param.split(',') if s.strip()]
            qs = qs.filter(source__in=sources)

        # Filter: Priority
        priority_param = request.query_params.get('priority')
        if priority_param:
            qs = qs.filter(priority=priority_param.strip())

        # Filter: Is Read
        is_read_param = request.query_params.get('is_read')
        if is_read_param is not None:
            is_read_bool = is_read_param.lower() in ('true', '1')
            qs = qs.filter(is_read=is_read_bool)

        # Filter: Assigned To
        assigned_to_param = request.query_params.get('assigned_to')
        if assigned_to_param:
            qs = qs.filter(assigned_to_id=assigned_to_param.strip())

        # Filter: Search (patient name, phone, email, service, doctor, message)
        search_query = request.query_params.get('search')
        if search_query:
            q = search_query.strip()
            qs = qs.filter(
                Q(patient_name__icontains=q) |
                Q(phone_number__icontains=q) |
                Q(email__icontains=q) |
                Q(service_requested__icontains=q) |
                Q(doctor_requested__icontains=q) |
                Q(message__icontains=q)
            )

        # Filter: Date range
        date_from = request.query_params.get('date_from')
        if date_from:
            qs = qs.filter(created_at__gte=date_from)
        date_to = request.query_params.get('date_to')
        if date_to:
            qs = qs.filter(created_at__lte=date_to)

        # Ordering
        ordering = request.query_params.get('ordering', '-created_at')
        if ordering in ['created_at', '-created_at', 'status', '-status', 'priority', '-priority', 'follow_up_date']:
            qs = qs.order_by(ordering)

        serializer = LeadSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response(
                {"error": "Active practice not identified. Provide 'X-Practice-ID' header."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not _check_lead_permission(request, practice):
            return Response({"error": "Permission denied for this practice."}, status=status.HTTP_403_FORBIDDEN)

        serializer = LeadCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        lead = serializer.save(practice=practice)

        # Create initial activity
        LeadActivity.objects.create(
            practice=practice,
            lead=lead,
            performed_by=request.user,
            activity_type=LeadActivity.TYPE_STATUS_CHANGE,
            previous_status="",
            new_status=lead.status,
            note=f"Lead manually created by {getattr(request.user, 'full_name', str(request.user))}."
        )

        return Response(LeadDetailSerializer(lead).data, status=status.HTTP_201_CREATED)


class LeadDetailView(APIView):
    """
    Retrieve, update or delete a lead record.
    GET /api/leads/<pk>/ - Returns full details and marks as read
    PATCH /api/leads/<pk>/ - Edit contact or clinical details
    DELETE /api/leads/<pk>/ - Delete lead (admin/owner only)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        lead = get_object_or_404(Lead, id=pk)
        if not _check_lead_permission(request, lead.practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        # Automatically mark lead as read
        lead.mark_read()

        serializer = LeadDetailSerializer(lead)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, pk):
        lead = get_object_or_404(Lead, id=pk)
        if not _check_lead_permission(request, lead.practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        allowed_fields = [
            'patient_name', 'phone_number', 'email', 'preferred_date',
            'preferred_time_slot', 'service_requested', 'doctor_requested',
            'message', 'priority', 'assigned_to', 'follow_up_date', 'is_read'
        ]

        updated = False
        for field in allowed_fields:
            if field in request.data:
                setattr(lead, field, request.data[field])
                updated = True

        if updated:
            lead.save()

        return Response(LeadDetailSerializer(lead).data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        lead = get_object_or_404(Lead, id=pk)
        if not _is_practice_admin(request, lead.practice):
            return Response({"error": "Only clinic administrators can delete leads."}, status=status.HTTP_403_FORBIDDEN)

        lead.delete()
        return Response({"success": True, "message": "Lead deleted."}, status=status.HTTP_200_OK)


class LeadStatusUpdateView(APIView):
    """
    Dedicated endpoint for lead pipeline transitions with activity logging.
    POST /api/leads/<pk>/status/
    Payload: {"status": "contacted", "note": "Spoke on phone, scheduled appointment", "follow_up_date": "2026-10-25T10:00:00Z"}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        lead = get_object_or_404(Lead, id=pk)
        if not _check_lead_permission(request, lead.practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        serializer = LeadStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        lead = LeadService.update_lead_status(
            lead=lead,
            new_status=data['status'],
            performed_by=request.user,
            note=data.get('note', ''),
            follow_up_date=data.get('follow_up_date'),
            lost_reason=data.get('lost_reason', '')
        )

        return Response(LeadDetailSerializer(lead).data, status=status.HTTP_200_OK)


class LeadActivityListCreateView(APIView):
    """
    Timeline activities: log a call, note, or WhatsApp message.
    GET /api/leads/<lead_id>/activities/
    POST /api/leads/<lead_id>/activities/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, lead_id):
        lead = get_object_or_404(Lead, id=lead_id)
        if not _check_lead_permission(request, lead.practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        activities = lead.activities.all().order_by('-created_at')
        serializer = LeadActivitySerializer(activities, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, lead_id):
        lead = get_object_or_404(Lead, id=lead_id)
        if not _check_lead_permission(request, lead.practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        serializer = LeadActivityCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        activity = LeadActivity.objects.create(
            practice=lead.practice,
            lead=lead,
            performed_by=request.user,
            activity_type=data['activity_type'],
            note=data['note'],
            metadata=data.get('metadata', {})
        )

        # Update last contacted time if call or message was logged
        if data['activity_type'] in [LeadActivity.TYPE_CALL, LeadActivity.TYPE_WHATSAPP, LeadActivity.TYPE_EMAIL]:
            lead.last_contacted_at = activity.created_at
            if lead.status == Lead.STATUS_NEW:
                lead.status = Lead.STATUS_CONTACTED
            lead.save(update_fields=['last_contacted_at', 'status', 'updated_at'])

        return Response(LeadActivitySerializer(activity).data, status=status.HTTP_201_CREATED)


class LeadConsentUpdateView(APIView):
    """
    Update consent preferences or withdraw consent for a patient.
    POST /api/leads/<pk>/consent/
    Payload: {"consent_withdrawn": true, "consent_withdrawn_reason": "Patient requested no calls"}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        lead = get_object_or_404(Lead, id=pk)
        if not _check_lead_permission(request, lead.practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        serializer = LeadConsentUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        lead = LeadService.update_consent(
            lead=lead,
            data=serializer.validated_data,
            performed_by=request.user
        )

        return Response(LeadDetailSerializer(lead).data, status=status.HTTP_200_OK)


class LeadStatsView(APIView):
    """
    CRM dashboard analytics: counters, pipeline breakdown, conversion rates, and click events.
    GET /api/leads/stats/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response(
                {"error": "Active practice not identified. Provide 'X-Practice-ID' header."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not _check_lead_permission(request, practice):
            return Response({"error": "Permission denied for this practice."}, status=status.HTTP_403_FORBIDDEN)

        metrics = LeadService.get_inbox_metrics(practice)
        return Response(metrics, status=status.HTTP_200_OK)


class LeadClickEventListView(APIView):
    """
    List Call & WhatsApp click events for practice analytics.
    GET /api/leads/events/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response(
                {"error": "Active practice not identified. Provide 'X-Practice-ID' header."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not _check_lead_permission(request, practice):
            return Response({"error": "Permission denied for this practice."}, status=status.HTTP_403_FORBIDDEN)

        qs = ClickEvent.objects.filter(practice=practice)

        event_type = request.query_params.get('event_type')
        if event_type:
            qs = qs.filter(event_type=event_type)

        date_from = request.query_params.get('date_from')
        if date_from:
            qs = qs.filter(created_at__gte=date_from)

        date_to = request.query_params.get('date_to')
        if date_to:
            qs = qs.filter(created_at__lte=date_to)

        serializer = ClickEventSerializer(qs[:100], many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

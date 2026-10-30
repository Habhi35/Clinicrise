import uuid
from datetime import timedelta
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from practices.models import Practice, PracticeMembership
from practices.permissions import IsPracticeMember
from leads.models import Lead
from patients.models import (
    Patient,
    PatientFollowUp,
    PatientNote,
    PatientTimeline,
    PatientVitals,
)
from patients.serializers import (
    CompleteFollowUpSerializer,
    LogCallSerializer,
    PatientCreateUpdateSerializer,
    PatientDetailSerializer,
    PatientFollowUpSerializer,
    PatientListSerializer,
    PatientNoteSerializer,
    PatientTimelineSerializer,
    PatientVitalsSerializer,
)
from patients.services.patient_service import PatientService


def _get_active_practice(request, practice_id=None):
    """Resolves and validates active Practice tenant for the request."""
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


def _get_user_role(request, practice) -> str:
    """Returns the caller's role in the active practice."""
    if not request.user or not request.user.is_authenticated:
        return "system"
    membership = PracticeMembership.objects.filter(
        practice=practice,
        user=request.user,
        is_active=True
    ).first()
    return membership.role if membership else "staff"


class PatientListCreateView(APIView):
    """
    Search, filter, and register patients in the active practice.
    GET /api/patients/
    POST /api/patients/
    """
    permission_classes = [IsAuthenticated, IsPracticeMember]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified. Provide X-Practice-ID header."}, status=status.HTTP_400_BAD_REQUEST)

        queryset = Patient.objects.filter(practice=practice).order_by('-created_at')

        # Search filter
        search = request.query_params.get('search')
        if search:
            s = search.strip()
            queryset = queryset.filter(
                Q(first_name__icontains=s) |
                Q(last_name__icontains=s) |
                Q(phone_number__icontains=s) |
                Q(email__icontains=s) |
                Q(patient_id__icontains=s)
            )

        # Status filter
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Blood group filter
        blood_group = request.query_params.get('blood_group')
        if blood_group:
            queryset = queryset.filter(blood_group=blood_group)

        # Allergies filter
        if request.query_params.get('has_allergies') == 'true':
            queryset = queryset.exclude(allergies='')

        # Doctor filter
        doctor_id = request.query_params.get('doctor_id')
        if doctor_id:
            queryset = queryset.filter(primary_doctor_id=doctor_id)

        serializer = PatientListSerializer(queryset[:100], many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified. Provide X-Practice-ID header."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = PatientCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_role = _get_user_role(request, practice)
        patient = PatientService.register_patient(
            practice=practice,
            data=serializer.validated_data,
            performed_by=request.user,
            role=user_role
        )

        return Response(PatientDetailSerializer(patient).data, status=status.HTTP_201_CREATED)


class PatientDetailView(APIView):
    """
    View, update, or deactivate a specific patient record.
    GET /api/patients/<pk>/
    PATCH /api/patients/<pk>/
    DELETE /api/patients/<pk>/
    """
    permission_classes = [IsAuthenticated, IsPracticeMember]

    def get(self, request, pk):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified."}, status=status.HTTP_400_BAD_REQUEST)

        patient = get_object_or_404(Patient, id=pk, practice=practice)
        return Response(PatientDetailSerializer(patient).data, status=status.HTTP_200_OK)

    def patch(self, request, pk):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified."}, status=status.HTTP_400_BAD_REQUEST)

        patient = get_object_or_404(Patient, id=pk, practice=practice)
        serializer = PatientCreateUpdateSerializer(patient, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_patient = serializer.save()

        user_role = _get_user_role(request, practice)
        PatientService.log_timeline_event(
            patient=updated_patient,
            event_type=PatientTimeline.EVENT_PATIENT_UPDATED,
            title="Patient Profile Updated",
            description=f"Demographics or clinical details updated by {request.user.full_name}.",
            performed_by=request.user,
            performer_role=user_role,
        )

        return Response(PatientDetailSerializer(updated_patient).data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified."}, status=status.HTTP_400_BAD_REQUEST)

        patient = get_object_or_404(Patient, id=pk, practice=practice)
        patient.status = Patient.STATUS_ARCHIVED
        patient.save(update_fields=['status', 'updated_at'])

        user_role = _get_user_role(request, practice)
        PatientService.log_timeline_event(
            patient=patient,
            event_type=PatientTimeline.EVENT_PATIENT_UPDATED,
            title="Patient Archived",
            description=f"Patient record archived by {request.user.full_name}.",
            performed_by=request.user,
            performer_role=user_role,
        )

        return Response({"message": f"Patient {patient.full_name} has been archived."}, status=status.HTTP_200_OK)


class PatientTimelineListView(APIView):
    """
    Chronological activity feed of all touchpoints for a patient.
    GET /api/patients/<pk>/timeline/
    """
    permission_classes = [IsAuthenticated, IsPracticeMember]

    def get(self, request, pk):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified."}, status=status.HTTP_400_BAD_REQUEST)

        patient = get_object_or_404(Patient, id=pk, practice=practice)
        queryset = patient.timeline.all().order_by('-created_at')

        event_type = request.query_params.get('event_type')
        if event_type:
            queryset = queryset.filter(event_type=event_type)

        serializer = PatientTimelineSerializer(queryset[:100], many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PatientNoteListCreateView(APIView):
    """
    List and add notes for a patient.
    GET /api/patients/<pk>/notes/
    POST /api/patients/<pk>/notes/
    """
    permission_classes = [IsAuthenticated, IsPracticeMember]

    def get(self, request, pk):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified."}, status=status.HTTP_400_BAD_REQUEST)

        patient = get_object_or_404(Patient, id=pk, practice=practice)
        queryset = patient.notes.all()

        category = request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)

        if request.query_params.get('pinned') == 'true':
            queryset = queryset.filter(is_pinned=True)

        serializer = PatientNoteSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, pk):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified."}, status=status.HTTP_400_BAD_REQUEST)

        patient = get_object_or_404(Patient, id=pk, practice=practice)
        note_text = request.data.get('note', '').strip()
        if not note_text:
            return Response({"error": "note content is required."}, status=status.HTTP_400_BAD_REQUEST)

        category = request.data.get('category', PatientNote.CATEGORY_GENERAL)
        is_pinned_raw = request.data.get('is_pinned', False)
        if isinstance(is_pinned_raw, str):
            is_pinned = is_pinned_raw.lower() in ('true', '1', 'yes')
        else:
            is_pinned = bool(is_pinned_raw)
        user_role = _get_user_role(request, practice)

        note = PatientService.add_note(
            patient=patient,
            note_text=note_text,
            category=category,
            author=request.user,
            role=user_role,
            is_pinned=is_pinned
        )

        return Response(PatientNoteSerializer(note).data, status=status.HTTP_201_CREATED)


class PatientNotePinToggleView(APIView):
    """
    Pin or unpin a critical clinical alert or frontdesk instruction.
    POST /api/patients/<pk>/notes/<note_id>/pin/
    """
    permission_classes = [IsAuthenticated, IsPracticeMember]

    def post(self, request, pk, note_id):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified."}, status=status.HTTP_400_BAD_REQUEST)

        patient = get_object_or_404(Patient, id=pk, practice=practice)
        note = get_object_or_404(PatientNote, id=note_id, patient=patient, practice=practice)

        note.toggle_pin(user=request.user)
        return Response(PatientNoteSerializer(note).data, status=status.HTTP_200_OK)


class PatientVitalsListCreateView(APIView):
    """
    List and record patient vitals (by clinical assistants or nurses).
    GET /api/patients/<pk>/vitals/
    POST /api/patients/<pk>/vitals/
    """
    permission_classes = [IsAuthenticated, IsPracticeMember]

    def get(self, request, pk):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified."}, status=status.HTTP_400_BAD_REQUEST)

        patient = get_object_or_404(Patient, id=pk, practice=practice)
        vitals = patient.vitals.all().order_by('-created_at')[:20]
        return Response(PatientVitalsSerializer(vitals, many=True).data, status=status.HTTP_200_OK)

    def post(self, request, pk):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified."}, status=status.HTTP_400_BAD_REQUEST)

        patient = get_object_or_404(Patient, id=pk, practice=practice)
        user_role = _get_user_role(request, practice)

        vitals = PatientService.record_vitals(
            patient=patient,
            vitals_data=request.data,
            recorded_by=request.user,
            role=user_role,
            booking=None
        )

        return Response(PatientVitalsSerializer(vitals).data, status=status.HTTP_201_CREATED)


class PatientLogCallView(APIView):
    """
    Receptionists log telephone consultations or check-in calls with outcomes.
    POST /api/patients/<pk>/log-call/
    """
    permission_classes = [IsAuthenticated, IsPracticeMember]

    def post(self, request, pk):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified."}, status=status.HTTP_400_BAD_REQUEST)

        patient = get_object_or_404(Patient, id=pk, practice=practice)
        serializer = LogCallSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_role = _get_user_role(request, practice)
        timeline_entry = PatientService.log_phone_call(
            patient=patient,
            call_type=serializer.validated_data.get('call_type', 'outgoing'),
            outcome=serializer.validated_data.get('outcome', 'answered'),
            notes=serializer.validated_data.get('notes', ''),
            performed_by=request.user,
            role=user_role
        )

        return Response(
            {
                "status": "success",
                "message": "Call logged successfully.",
                "timeline_event": PatientTimelineSerializer(timeline_entry).data,
            },
            status=status.HTTP_201_CREATED
        )


class PatientFollowUpListCreateView(APIView):
    """
    List and schedule follow-ups for a specific patient.
    GET /api/patients/<pk>/follow-ups/
    POST /api/patients/<pk>/follow-ups/
    """
    permission_classes = [IsAuthenticated, IsPracticeMember]

    def get(self, request, pk):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified."}, status=status.HTTP_400_BAD_REQUEST)

        patient = get_object_or_404(Patient, id=pk, practice=practice)
        follow_ups = patient.follow_ups.all().order_by('due_date')
        return Response(PatientFollowUpSerializer(follow_ups, many=True).data, status=status.HTTP_200_OK)

    def post(self, request, pk):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified."}, status=status.HTTP_400_BAD_REQUEST)

        patient = get_object_or_404(Patient, id=pk, practice=practice)
        user_role = _get_user_role(request, practice)

        follow_up = PatientService.schedule_follow_up(
            patient=patient,
            data=request.data,
            created_by=request.user,
            role=user_role
        )

        return Response(PatientFollowUpSerializer(follow_up).data, status=status.HTTP_201_CREATED)


class PracticeFollowUpQueueView(APIView):
    """
    Global practice follow-up queue for receptionists and clinical assistants.
    GET /api/patients/follow-ups/
    Query Params: ?filter=due_today | overdue | upcoming | completed | all
                  ?assigned_to=<user_id> | me
                  ?priority=urgent | high | medium | low
    """
    permission_classes = [IsAuthenticated, IsPracticeMember]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified. Provide X-Practice-ID header."}, status=status.HTTP_400_BAD_REQUEST)

        queryset = PatientFollowUp.objects.filter(practice=practice).select_related('patient', 'assigned_to', 'created_by')

        now = timezone.now()
        start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_today = start_of_today + timedelta(days=1)

        filter_mode = request.query_params.get('filter', 'pending')
        if filter_mode == 'due_today':
            queryset = queryset.filter(
                status__in=[PatientFollowUp.STATUS_PENDING, PatientFollowUp.STATUS_IN_PROGRESS],
                due_date__gte=start_of_today,
                due_date__lt=end_of_today
            )
        elif filter_mode == 'overdue':
            queryset = queryset.filter(
                status__in=[PatientFollowUp.STATUS_PENDING, PatientFollowUp.STATUS_IN_PROGRESS],
                due_date__lt=start_of_today
            )
        elif filter_mode == 'upcoming':
            queryset = queryset.filter(
                status__in=[PatientFollowUp.STATUS_PENDING, PatientFollowUp.STATUS_IN_PROGRESS],
                due_date__gte=end_of_today
            )
        elif filter_mode == 'completed':
            queryset = queryset.filter(status=PatientFollowUp.STATUS_COMPLETED)
        elif filter_mode == 'all':
            pass
        else:  # default pending & in_progress
            queryset = queryset.filter(status__in=[PatientFollowUp.STATUS_PENDING, PatientFollowUp.STATUS_IN_PROGRESS])

        assigned_to = request.query_params.get('assigned_to')
        if assigned_to == 'me':
            queryset = queryset.filter(assigned_to=request.user)
        elif assigned_to:
            queryset = queryset.filter(assigned_to_id=assigned_to)

        priority = request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)

        serializer = PatientFollowUpSerializer(queryset[:100], many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PatientFollowUpCompleteView(APIView):
    """
    Action endpoint to mark a follow-up completed with outcome notes.
    POST /api/patients/follow-ups/<pk>/complete/
    """
    permission_classes = [IsAuthenticated, IsPracticeMember]

    def post(self, request, pk):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified."}, status=status.HTTP_400_BAD_REQUEST)

        follow_up = get_object_or_404(PatientFollowUp, id=pk, practice=practice)
        serializer = CompleteFollowUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_role = _get_user_role(request, practice)
        completed = PatientService.complete_follow_up(
            follow_up=follow_up,
            outcome_notes=serializer.validated_data['outcome_notes'],
            completed_by=request.user,
            role=user_role
        )

        return Response(PatientFollowUpSerializer(completed).data, status=status.HTTP_200_OK)


class ConvertLeadToPatientView(APIView):
    """
    1-Click conversion of prospective lead inquiry into a full registered patient.
    POST /api/patients/convert-lead/<lead_id>/
    """
    permission_classes = [IsAuthenticated, IsPracticeMember]

    def post(self, request, lead_id):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified."}, status=status.HTTP_400_BAD_REQUEST)

        lead = get_object_or_404(Lead, id=lead_id, practice=practice)
        user_role = _get_user_role(request, practice)

        patient = PatientService.convert_lead_to_patient(
            lead=lead,
            performed_by=request.user,
            role=user_role
        )

        return Response(
            {
                "status": "success",
                "message": f"Lead converted into registered patient {patient.full_name} ({patient.patient_id}).",
                "patient": PatientDetailSerializer(patient).data,
            },
            status=status.HTTP_201_CREATED
        )


class PatientCRMOverviewView(APIView):
    """
    Overview statistics and metrics for the practice CRM dashboard.
    GET /api/patients/overview/
    """
    permission_classes = [IsAuthenticated, IsPracticeMember]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified."}, status=status.HTTP_400_BAD_REQUEST)

        overview = PatientService.get_practice_crm_overview(practice)
        return Response(overview, status=status.HTTP_200_OK)

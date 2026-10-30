import os
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.models import User
from practices.models import (
    DoctorOnboarding,
    DoctorProfile,
    DoctorSchedule,
    Practice,
    PracticeImage,
    PracticeInvitation,
    PracticeMembership,
    PracticeService,
)
from practices.permissions import (
    IsPracticeAdmin,
    IsPracticeMember,
    IsPracticeOwner,
)
from practices.serializers import (
    ClinicDetailsStepSerializer,
    DoctorOnboardingSerializer,
    DoctorProfileSerializer,
    DoctorProfileStepSerializer,
    DoctorScheduleSerializer,
    ImagesStepSerializer,
    InviteMemberSerializer,
    PracticeImageSerializer,
    PracticeInvitationSerializer,
    PracticeMembershipSerializer,
    PracticeSerializer,
    PracticeServiceSerializer,
    SaveDraftSerializer,
    ServicesStepSerializer,
    TimingsStepSerializer,
    UpdateMemberSerializer,
)


# =====================================================================
# 1. PRACTICE TENANT & MEMBERSHIP VIEWS
# =====================================================================

class PracticeListCreateView(generics.ListCreateAPIView):
    """
    List practices where current user is a member, or create a new Practice tenant.
    GET /api/practices/
    POST /api/practices/
    """
    serializer_class = PracticeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Practice.objects.filter(
                memberships__user=self.request.user,
                memberships__is_active=True,
                is_active=True
            )
            .distinct()
            .order_by('-created_at')
        )


class PracticeDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or deactivate a specific Practice tenant.
    GET /api/practices/<pk>/ (Requires IsPracticeMember)
    PATCH /api/practices/<pk>/ (Requires IsPracticeAdmin)
    DELETE /api/practices/<pk>/ (Requires IsPracticeOwner)
    """
    serializer_class = PracticeSerializer
    queryset = Practice.objects.filter(is_active=True)

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH']:
            return [IsAuthenticated(), IsPracticeAdmin()]
        elif self.request.method == 'DELETE':
            return [IsAuthenticated(), IsPracticeOwner()]
        return [IsAuthenticated(), IsPracticeMember()]

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active'])


class CurrentPracticeView(APIView):
    """
    Returns the currently active Practice tenant scoped by the 'X-Practice-ID' header
    or automatically resolved for single-tenant users.
    GET /api/practices/current/
    """
    permission_classes = [IsAuthenticated, IsPracticeMember]

    def get(self, request):
        practice = getattr(request, 'practice', None)
        membership = getattr(request, 'membership', None)

        if not practice:
            return Response(
                {
                    "error": "No active practice context found. Please provide 'X-Practice-ID' header.",
                    "code": "TENANT_HEADER_MISSING"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {
                "practice": PracticeSerializer(practice, context={'request': request}).data,
                "membership": PracticeMembershipSerializer(membership).data,
            },
            status=status.HTTP_200_OK
        )


class PracticeMemberListCreateView(APIView):
    """
    Manage team members in a practice.
    GET /api/practices/<practice_id>/members/ (List members - Requires IsPracticeMember)
    Query Params: ?role=receptionist | assistant | doctor | admin | staff
    """
    permission_classes = [IsAuthenticated, IsPracticeMember]

    def get(self, request, practice_id):
        practice = get_object_or_404(Practice, id=practice_id, is_active=True)
        queryset = (
            PracticeMembership.objects.filter(practice=practice, is_active=True)
            .select_related('user', 'user__doctor_profile')
        )
        role_filter = request.query_params.get('role')
        if role_filter:
            queryset = queryset.filter(role=role_filter)

        memberships = queryset.order_by('role', '-joined_at')
        serializer = PracticeMembershipSerializer(memberships, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PracticeRoleMatrixView(APIView):
    """
    Returns role definitions, descriptions, and capabilities for team access control.
    GET /api/practices/roles/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        roles = [
            {
                "code": PracticeMembership.ROLE_OWNER,
                "name": "Practice Owner",
                "description": "Full legal and operational control over clinic practice, billing, and team memberships.",
                "capabilities": ["manage_billing", "invite_team", "remove_team", "manage_clinical", "manage_patients", "view_audit_logs", "publish_content"],
                "category": "leadership",
            },
            {
                "code": PracticeMembership.ROLE_ADMIN,
                "name": "Practice Admin",
                "description": "Clinic manager / practice administrator overseeing team onboarding, clinic settings, and scheduling.",
                "capabilities": ["invite_team", "edit_team", "manage_clinical", "manage_patients", "view_reports", "publish_content"],
                "category": "administration",
            },
            {
                "code": PracticeMembership.ROLE_DOCTOR,
                "name": "Doctor / Practitioner",
                "description": "Licensed healthcare practitioner managing OPD consultations, clinical notes, prescriptions, and review sign-offs.",
                "capabilities": ["consult_patients", "clinical_notes", "prescriptions", "approve_medical_content", "schedule_followups"],
                "category": "clinical",
            },
            {
                "code": PracticeMembership.ROLE_RECEPTIONIST,
                "name": "Frontdesk / Receptionist",
                "description": "Front-of-house staff managing patient intake, walk-in tokens, appointment check-ins, call logs, and routine follow-ups.",
                "capabilities": ["register_patients", "check_in_patients", "manage_bookings", "frontdesk_notes", "log_calls", "execute_followups"],
                "category": "frontdesk",
            },
            {
                "code": PracticeMembership.ROLE_ASSISTANT,
                "name": "Clinical Assistant / Nurse",
                "description": "Healthcare assistant / triage nurse recording patient vitals, intake preparation, clinical notes, and procedure assistance.",
                "capabilities": ["record_vitals", "intake_prep_notes", "view_patient_chart", "assist_consultation", "execute_followups"],
                "category": "clinical_support",
            },
            {
                "code": PracticeMembership.ROLE_STAFF,
                "name": "General Staff",
                "description": "General clinic staff supporting scheduling, basic intake, and coordination.",
                "capabilities": ["view_bookings", "basic_intake", "manage_schedule"],
                "category": "support",
            },
        ]
        return Response({"roles": roles}, status=status.HTTP_200_OK)


class InviteMemberView(APIView):
    """
    Invite a doctor, admin, or staff member into a practice.
    POST /api/practices/<practice_id>/invite/
    Payload: {"identifier": "doctor@example.com", "role": "doctor"}
    """
    permission_classes = [IsAuthenticated, IsPracticeAdmin]

    def post(self, request, practice_id):
        practice = get_object_or_404(Practice, id=practice_id, is_active=True)
        serializer = InviteMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        identifier = serializer.validated_data['identifier']
        role = serializer.validated_data['role']
        is_email = '@' in identifier

        existing_user = (
            User.objects.filter(email=identifier).first()
            if is_email
            else User.objects.filter(phone_number=identifier).first()
        )

        if existing_user:
            existing_membership = PracticeMembership.objects.filter(
                practice=practice,
                user=existing_user
            ).first()

            if existing_membership:
                if existing_membership.is_active:
                    return Response(
                        {"error": f"This user is already an active member with role '{existing_membership.role}'."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                else:
                    existing_membership.role = role
                    existing_membership.is_active = True
                    existing_membership.save(update_fields=['role', 'is_active'])
                    return Response(
                        {
                            "message": "User re-activated in the practice.",
                            "membership": PracticeMembershipSerializer(existing_membership).data
                        },
                        status=status.HTTP_200_OK
                    )

        invite_code = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(days=7)

        invitation = PracticeInvitation.objects.create(
            practice=practice,
            email=identifier if is_email else None,
            phone_number=None if is_email else identifier,
            role=role,
            invite_code=invite_code,
            invited_by=request.user,
            expires_at=expires_at,
        )

        return Response(
            {
                "success": True,
                "message": f"Invitation generated for {identifier} as {role}.",
                "invitation": PracticeInvitationSerializer(invitation).data,
                "invite_code": invite_code,
            },
            status=status.HTTP_201_CREATED
        )


class AcceptInvitationView(APIView):
    """
    Accept an invitation to join a practice.
    POST /api/practices/invitations/accept/
    Payload: {"invite_code": "<invite_code>"}
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        invite_code = request.data.get('invite_code')
        if not invite_code:
            return Response({"error": "invite_code is required."}, status=status.HTTP_400_BAD_REQUEST)

        invitation = PracticeInvitation.objects.filter(
            invite_code=invite_code,
            status=PracticeInvitation.STATUS_PENDING
        ).first()

        if not invitation:
            return Response({"error": "Invalid or expired invitation code."}, status=status.HTTP_404_NOT_FOUND)

        if timezone.now() > invitation.expires_at:
            invitation.status = 'expired'
            invitation.save(update_fields=['status'])
            return Response({"error": "This invitation has expired."}, status=status.HTTP_400_BAD_REQUEST)

        membership, created = PracticeMembership.objects.update_or_create(
            practice=invitation.practice,
            user=request.user,
            defaults={
                'role': invitation.role,
                'is_active': True,
            }
        )

        invitation.status = PracticeInvitation.STATUS_ACCEPTED
        invitation.save(update_fields=['status'])

        return Response(
            {
                "success": True,
                "message": f"Successfully joined {invitation.practice.name} as {membership.get_role_display()}.",
                "practice": PracticeSerializer(invitation.practice, context={'request': request}).data,
                "membership": PracticeMembershipSerializer(membership).data,
            },
            status=status.HTTP_200_OK
        )


class PracticeMemberDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    View, update role, or remove a team member.
    GET /api/practices/<practice_id>/members/<pk>/
    PATCH /api/practices/<practice_id>/members/<pk>/ (Requires IsPracticeAdmin)
    DELETE /api/practices/<practice_id>/members/<pk>/ (Requires IsPracticeAdmin)
    """
    serializer_class = UpdateMemberSerializer
    permission_classes = [IsAuthenticated, IsPracticeAdmin]

    def get_queryset(self):
        practice_id = self.kwargs.get('practice_id')
        return PracticeMembership.objects.filter(practice_id=practice_id)

    def perform_destroy(self, instance):
        if instance.role == PracticeMembership.ROLE_OWNER:
            raise status.HTTP_400_BAD_REQUEST
        instance.is_active = False
        instance.save(update_fields=['is_active'])


class PracticeDoctorListView(APIView):
    """
    Convenient endpoint to list all doctors in a practice.
    GET /api/practices/<practice_id>/doctors/
    """
    permission_classes = [IsAuthenticated, IsPracticeMember]

    def get(self, request, practice_id):
        practice = get_object_or_404(Practice, id=practice_id, is_active=True)
        doctor_memberships = (
            PracticeMembership.objects.filter(
                practice=practice,
                role__in=[
                    PracticeMembership.ROLE_DOCTOR,
                    PracticeMembership.ROLE_ADMIN,
                    PracticeMembership.ROLE_OWNER
                ],
                is_active=True,
                user__doctor_profile__isnull=False
            )
            .select_related('user', 'user__doctor_profile')
        )

        results = []
        for m in doctor_memberships:
            results.append({
                "membership_id": m.id,
                "role": m.role,
                "user_id": m.user.id,
                "doctor_profile": DoctorProfileSerializer(m.user.doctor_profile).data,
            })

        return Response(results, status=status.HTTP_200_OK)


class DoctorProfileView(APIView):
    """
    View and manage current user's Doctor Profile.
    GET /api/practices/doctor/profile/
    POST /api/practices/doctor/profile/
    PATCH /api/practices/doctor/profile/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not hasattr(request.user, 'doctor_profile'):
            return Response(
                {"error": "No doctor profile found for this account."},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = DoctorProfileSerializer(request.user.doctor_profile)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = DoctorProfileSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        profile = serializer.save()
        return Response(DoctorProfileSerializer(profile).data, status=status.HTTP_201_CREATED)

    def patch(self, request):
        if not hasattr(request.user, 'doctor_profile'):
            return Response(
                {"error": "No doctor profile found for this account."},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = DoctorProfileSerializer(
            request.user.doctor_profile,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        profile = serializer.save()
        return Response(DoctorProfileSerializer(profile).data, status=status.HTTP_200_OK)


# =====================================================================
# 2. DOCTOR ONBOARDING WIZARD & SAVED PROGRESS VIEWS
# =====================================================================

def _get_or_create_onboarding(user):
    """Helper to fetch or initialize DoctorOnboarding for the user and sync progress."""
    onboarding, _ = DoctorOnboarding.objects.get_or_create(user=user)

    # Link practice if not already linked
    if not onboarding.practice:
        owned_practice = user.owned_practices.filter(is_active=True).first()
        if not owned_practice:
            first_membership = user.practice_memberships.filter(is_active=True).select_related('practice').first()
            if first_membership:
                owned_practice = first_membership.practice
        if owned_practice:
            onboarding.practice = owned_practice
            onboarding.save(update_fields=['practice'])

    # Synchronize completed steps based on persisted data
    completed = set(onboarding.completed_steps or [])
    if hasattr(user, 'doctor_profile') and user.doctor_profile.medical_license_number:
        completed.add(DoctorOnboarding.STEP_DOCTOR_PROFILE)

    if onboarding.practice:
        completed.add(DoctorOnboarding.STEP_CLINIC_DETAILS)
        if PracticeService.objects.filter(practice=onboarding.practice, is_active=True).exists():
            completed.add(DoctorOnboarding.STEP_SERVICES)
        if DoctorSchedule.objects.filter(practice=onboarding.practice, is_active=True).exists():
            completed.add(DoctorOnboarding.STEP_TIMINGS)
        if PracticeImage.objects.filter(practice=onboarding.practice).exists() or getattr(user, 'doctor_profile', None) and user.doctor_profile.profile_photo_url:
            completed.add(DoctorOnboarding.STEP_IMAGES)

    if set(onboarding.completed_steps or []) != completed:
        onboarding.completed_steps = list(completed)
        onboarding.save(update_fields=['completed_steps'])

    return onboarding


class DoctorOnboardingProgressView(APIView):
    """
    Get current Doctor Onboarding status, saved drafts, active step, and step-by-step progress.
    GET /api/practices/onboarding/progress/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        onboarding = _get_or_create_onboarding(request.user)

        doctor_profile = getattr(request.user, 'doctor_profile', None)
        practice = onboarding.practice

        services_qs = PracticeService.objects.filter(practice=practice) if practice else []
        timings_qs = DoctorSchedule.objects.filter(practice=practice) if practice else []
        images_qs = PracticeImage.objects.filter(practice=practice) if practice else []

        steps_metadata = [
            {
                "key": DoctorOnboarding.STEP_DOCTOR_PROFILE,
                "step_number": 1,
                "title": "Doctor Profile & Registration Number",
                "description": "Doctor credentials, medical registration number, council, and specialization.",
                "is_completed": DoctorOnboarding.STEP_DOCTOR_PROFILE in onboarding.completed_steps,
                "data": DoctorProfileSerializer(doctor_profile).data if doctor_profile else onboarding.draft_data.get('doctor_profile', {}),
            },
            {
                "key": DoctorOnboarding.STEP_CLINIC_DETAILS,
                "step_number": 2,
                "title": "Clinic & Practice Details",
                "description": "Clinic name, address, contact information, location, and currency.",
                "is_completed": DoctorOnboarding.STEP_CLINIC_DETAILS in onboarding.completed_steps,
                "data": PracticeSerializer(practice, context={'request': request}).data if practice else onboarding.draft_data.get('clinic_details', {}),
            },
            {
                "key": DoctorOnboarding.STEP_SERVICES,
                "step_number": 3,
                "title": "Clinical Services & Consultation Fees",
                "description": "Healthcare services offered with duration and consultation fees.",
                "is_completed": DoctorOnboarding.STEP_SERVICES in onboarding.completed_steps,
                "data": PracticeServiceSerializer(services_qs, many=True).data if practice else onboarding.draft_data.get('services', []),
            },
            {
                "key": DoctorOnboarding.STEP_TIMINGS,
                "step_number": 4,
                "title": "Clinic Timings & Working Hours",
                "description": "Weekly consultation schedules, shift hours, and slot durations.",
                "is_completed": DoctorOnboarding.STEP_TIMINGS in onboarding.completed_steps,
                "data": DoctorScheduleSerializer(timings_qs, many=True).data if practice else onboarding.draft_data.get('timings', []),
            },
            {
                "key": DoctorOnboarding.STEP_IMAGES,
                "step_number": 5,
                "title": "Clinic Photos & Verification Documents",
                "description": "Doctor profile photo, registration certificate, and clinic interior/exterior photos.",
                "is_completed": DoctorOnboarding.STEP_IMAGES in onboarding.completed_steps,
                "data": {
                    "clinic_images": PracticeImageSerializer(images_qs, many=True).data if practice else [],
                    "profile_photo_url": doctor_profile.photo_display_url if doctor_profile else None,
                    "registration_certificate_url": doctor_profile.registration_certificate_url if doctor_profile else None,
                } if practice else onboarding.draft_data.get('images', {}),
            },
        ]

        return Response(
            {
                "onboarding": DoctorOnboardingSerializer(onboarding).data,
                "progress_percentage": onboarding.progress_percentage,
                "current_step": onboarding.current_step,
                "completed_steps": onboarding.completed_steps,
                "is_completed": onboarding.is_completed,
                "steps": steps_metadata,
                "draft_data": onboarding.draft_data,
            },
            status=status.HTTP_200_OK
        )


class DoctorOnboardingSaveDraftView(APIView):
    """
    Save in-progress draft data for any onboarding step without strict validation.
    Enables doctors to resume their onboarding anytime.
    POST /api/practices/onboarding/draft/
    Payload: {"step": "doctor_profile", "data": {...}}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = SaveDraftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        step = serializer.validated_data['step']
        step_data = serializer.validated_data['data']

        onboarding = _get_or_create_onboarding(request.user)
        onboarding.save_draft_step(step, step_data)

        return Response(
            {
                "success": True,
                "message": f"Draft saved successfully for step '{step}'.",
                "progress_percentage": onboarding.progress_percentage,
                "current_step": onboarding.current_step,
                "saved_draft": onboarding.draft_data.get(step),
            },
            status=status.HTTP_200_OK
        )


class DoctorOnboardingStepProfileView(APIView):
    """
    Submit Step 1: Doctor Profile & Registration Number.
    POST /api/practices/onboarding/step/doctor-profile/
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = DoctorProfileStepSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = request.user
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        phone_number = data.get('phone_number')

        user_updated = False
        if first_name is not None and first_name != '':
            user.first_name = first_name
            user_updated = True
        if last_name is not None and last_name != '':
            user.last_name = last_name
            user_updated = True
        if phone_number is not None and phone_number != '' and not user.phone_number:
            user.phone_number = phone_number
            user_updated = True
        if user_updated:
            user.save(update_fields=['first_name', 'last_name', 'phone_number'])

        # Check license number uniqueness (excluding current user's profile)
        license_num = data['medical_license_number']
        existing_profile = DoctorProfile.objects.filter(medical_license_number=license_num).exclude(user=user).first()
        if existing_profile:
            return Response(
                {"error": f"Medical registration number '{license_num}' is already registered by another doctor."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create or update DoctorProfile
        profile_fields = {
            'title': data.get('title', 'Dr.'),
            'gender': data.get('gender', DoctorProfile.GENDER_UNSPECIFIED),
            'medical_license_number': license_num,
            'registration_council': data.get('registration_council', ''),
            'registration_year': data.get('registration_year'),
            'specialization': data['specialization'],
            'qualifications': data['qualifications'],
            'experience_years': data.get('experience_years', 0),
            'languages_spoken': data.get('languages_spoken', 'English'),
            'bio': data.get('bio', ''),
            'default_consultation_fee': data.get('default_consultation_fee', 0.00),
            'profile_photo_url': data.get('profile_photo_url') or '',
            'registration_certificate_url': data.get('registration_certificate_url') or '',
        }

        doctor_profile, created = DoctorProfile.objects.update_or_create(
            user=user,
            defaults=profile_fields
        )

        # Save to onboarding state
        onboarding = _get_or_create_onboarding(user)
        onboarding.save_draft_step(DoctorOnboarding.STEP_DOCTOR_PROFILE, data)
        onboarding.mark_step_completed(DoctorOnboarding.STEP_DOCTOR_PROFILE)

        return Response(
            {
                "success": True,
                "message": "Doctor profile & registration number saved successfully.",
                "doctor_profile": DoctorProfileSerializer(doctor_profile).data,
                "progress_percentage": onboarding.progress_percentage,
                "current_step": onboarding.current_step,
            },
            status=status.HTTP_200_OK
        )


class DoctorOnboardingStepClinicView(APIView):
    """
    Submit Step 2: Clinic & Practice Tenant Details.
    POST /api/practices/onboarding/step/clinic-details/
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = ClinicDetailsStepSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = request.user
        onboarding = _get_or_create_onboarding(user)

        practice_fields = {
            'name': data['name'],
            'clinic_type': data.get('clinic_type', Practice.CLINIC_TYPE_SOLO),
            'tagline': data.get('tagline', ''),
            'about': data.get('about', ''),
            'phone_number': data.get('phone_number', user.phone_number or ''),
            'email': data.get('email', user.email or ''),
            'website': data.get('website'),
            'logo_url': data.get('logo_url') or '',
            'address': data.get('address', ''),
            'landmark': data.get('landmark', ''),
            'city': data.get('city', ''),
            'state': data.get('state', ''),
            'postal_code': data.get('postal_code', ''),
            'country': data.get('country', 'India'),
            'gst_number': data.get('gst_number', ''),
            'established_year': data.get('established_year'),
            'currency': data.get('currency', 'INR'),
            'timezone': data.get('timezone', 'Asia/Kolkata'),
            'is_active': True,
        }

        # Update existing practice if linked, or create new
        if onboarding.practice:
            practice = onboarding.practice
            for key, val in practice_fields.items():
                setattr(practice, key, val)
            practice.save()
        else:
            practice = Practice.objects.create(owner=user, **practice_fields)
            onboarding.practice = practice

        # Ensure Owner membership
        PracticeMembership.objects.update_or_create(
            practice=practice,
            user=user,
            defaults={'role': PracticeMembership.ROLE_OWNER, 'is_active': True}
        )

        onboarding.save_draft_step(DoctorOnboarding.STEP_CLINIC_DETAILS, data)
        onboarding.mark_step_completed(DoctorOnboarding.STEP_CLINIC_DETAILS)

        return Response(
            {
                "success": True,
                "message": "Clinic details saved successfully.",
                "practice": PracticeSerializer(practice, context={'request': request}).data,
                "progress_percentage": onboarding.progress_percentage,
                "current_step": onboarding.current_step,
            },
            status=status.HTTP_200_OK
        )


class DoctorOnboardingStepServicesView(APIView):
    """
    Submit Step 3: Clinical Services & Fees.
    POST /api/practices/onboarding/step/services/
    Payload: {"services": [{"name": "OPD Consultation", "category": "consultation", "duration_minutes": 15, "price": 500}]}
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = ServicesStepSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services_data = serializer.validated_data['services']

        user = request.user
        onboarding = _get_or_create_onboarding(user)
        practice = onboarding.practice

        if not practice:
            return Response(
                {"error": "Please complete Step 2 (Clinic Details) first."},
                status=status.HTTP_400_BAD_REQUEST
            )

        doctor_profile = getattr(user, 'doctor_profile', None)

        created_services = []
        for item in services_data:
            service = PracticeService.objects.create(
                practice=practice,
                doctor=doctor_profile,
                name=item['name'],
                category=item.get('category', PracticeService.CATEGORY_CONSULTATION),
                description=item.get('description', ''),
                duration_minutes=item.get('duration_minutes', 15),
                price=item.get('price', 0.00),
                is_teleconsultation=item.get('is_teleconsultation', False),
                is_active=item.get('is_active', True),
            )
            created_services.append(service)

        onboarding.save_draft_step(DoctorOnboarding.STEP_SERVICES, request.data)
        onboarding.mark_step_completed(DoctorOnboarding.STEP_SERVICES)

        return Response(
            {
                "success": True,
                "message": f"Saved {len(created_services)} services successfully.",
                "services": PracticeServiceSerializer(created_services, many=True).data,
                "progress_percentage": onboarding.progress_percentage,
                "current_step": onboarding.current_step,
            },
            status=status.HTTP_200_OK
        )


class DoctorOnboardingStepTimingsView(APIView):
    """
    Submit Step 4: Doctor Timings & Working Hours Schedule.
    POST /api/practices/onboarding/step/timings/
    Payload: {"timings": [{"day_of_week": 0, "session_name": "Morning OPD", "start_time": "09:00", "end_time": "13:00", "slot_duration_minutes": 15}]}
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = TimingsStepSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        timings_data = serializer.validated_data['timings']

        user = request.user
        onboarding = _get_or_create_onboarding(user)
        practice = onboarding.practice

        if not practice:
            return Response(
                {"error": "Please complete Step 2 (Clinic Details) first."},
                status=status.HTTP_400_BAD_REQUEST
            )

        doctor_profile = getattr(user, 'doctor_profile', None)
        if not doctor_profile:
            return Response(
                {"error": "Please complete Step 1 (Doctor Profile) first."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Clear existing schedules for this doctor at this practice to avoid duplicates
        DoctorSchedule.objects.filter(practice=practice, doctor=doctor_profile).delete()

        created_schedules = []
        for item in timings_data:
            schedule = DoctorSchedule.objects.create(
                practice=practice,
                doctor=doctor_profile,
                day_of_week=item['day_of_week'],
                session_name=item.get('session_name', 'General OPD'),
                start_time=item['start_time'],
                end_time=item['end_time'],
                slot_duration_minutes=item.get('slot_duration_minutes', 15),
                is_active=item.get('is_active', True),
            )
            created_schedules.append(schedule)

        onboarding.save_draft_step(DoctorOnboarding.STEP_TIMINGS, request.data)
        onboarding.mark_step_completed(DoctorOnboarding.STEP_TIMINGS)

        return Response(
            {
                "success": True,
                "message": f"Saved {len(created_schedules)} schedule timing slots successfully.",
                "timings": DoctorScheduleSerializer(created_schedules, many=True).data,
                "progress_percentage": onboarding.progress_percentage,
                "current_step": onboarding.current_step,
            },
            status=status.HTTP_200_OK
        )


class DoctorOnboardingStepImagesView(APIView):
    """
    Submit Step 5: Clinic Photos, Doctor Profile Photo, and Certificates.
    POST /api/practices/onboarding/step/images/
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = ImagesStepSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = request.user
        onboarding = _get_or_create_onboarding(user)
        practice = onboarding.practice

        if not practice:
            return Response(
                {"error": "Please complete Step 2 (Clinic Details) first."},
                status=status.HTTP_400_BAD_REQUEST
            )

        doctor_profile = getattr(user, 'doctor_profile', None)

        # Update profile photo and registration certificate URL if provided
        doctor_avatar = data.get('doctor_avatar_url')
        certificate_url = data.get('registration_certificate_url')

        if doctor_profile:
            if doctor_avatar:
                doctor_profile.profile_photo_url = doctor_avatar
            if certificate_url:
                doctor_profile.registration_certificate_url = certificate_url
            doctor_profile.save(update_fields=['profile_photo_url', 'registration_certificate_url'])

        if doctor_avatar and not user.avatar_url:
            user.avatar_url = doctor_avatar
            user.save(update_fields=['avatar_url'])

        # Create clinic photos
        images_data = data.get('images', [])
        created_images = []
        for img in images_data:
            image_obj = PracticeImage.objects.create(
                practice=practice,
                image_url=img['image_url'],
                image_type=img.get('image_type', PracticeImage.IMAGE_TYPE_OTHER),
                caption=img.get('caption', ''),
                is_primary=img.get('is_primary', False),
                order=img.get('order', 0),
            )
            created_images.append(image_obj)

        onboarding.save_draft_step(DoctorOnboarding.STEP_IMAGES, request.data)
        onboarding.mark_step_completed(DoctorOnboarding.STEP_IMAGES)

        return Response(
            {
                "success": True,
                "message": "Images and verification documents saved successfully.",
                "clinic_images": PracticeImageSerializer(
                    PracticeImage.objects.filter(practice=practice),
                    many=True
                ).data,
                "progress_percentage": onboarding.progress_percentage,
                "current_step": onboarding.current_step,
            },
            status=status.HTTP_200_OK
        )


class DoctorOnboardingCompleteView(APIView):
    """
    Finalize Doctor Onboarding.
    Validates that required steps (Doctor Profile, Clinic, Services, Timings) are ready.
    POST /api/practices/onboarding/complete/
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        user = request.user
        onboarding = _get_or_create_onboarding(user)

        # Validate Doctor Profile
        if not hasattr(user, 'doctor_profile') or not user.doctor_profile.medical_license_number:
            return Response(
                {"error": "Doctor profile with medical registration number is required to complete onboarding."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate Practice
        if not onboarding.practice:
            return Response(
                {"error": "Clinic / Practice details are required to complete onboarding."},
                status=status.HTTP_400_BAD_REQUEST
            )

        practice = onboarding.practice

        # Validate Services
        if not PracticeService.objects.filter(practice=practice, is_active=True).exists():
            return Response(
                {"error": "At least one active clinical service must be configured."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate Timings
        if not DoctorSchedule.objects.filter(practice=practice, is_active=True).exists():
            return Response(
                {"error": "At least one working timing slot must be configured."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Mark onboarding as complete
        onboarding.is_completed = True
        onboarding.current_step = DoctorOnboarding.STEP_COMPLETED
        onboarding.completed_at = timezone.now()
        onboarding.mark_step_completed(DoctorOnboarding.STEP_REVIEW)

        # Ensure Practice and Membership are active
        practice.is_active = True
        practice.save(update_fields=['is_active'])

        membership, _ = PracticeMembership.objects.update_or_create(
            practice=practice,
            user=user,
            defaults={'role': PracticeMembership.ROLE_OWNER, 'is_active': True}
        )

        return Response(
            {
                "success": True,
                "message": f"Congratulations Dr. {user.full_name}! Your clinic '{practice.name}' is now fully onboarded and ready.",
                "practice_id": str(practice.id),
                "practice": PracticeSerializer(practice, context={'request': request}).data,
                "doctor_profile": DoctorProfileSerializer(user.doctor_profile).data,
                "onboarding": DoctorOnboardingSerializer(onboarding).data,
            },
            status=status.HTTP_200_OK
        )


class DoctorOnboardingFileUploadView(APIView):
    """
    Multipart file upload endpoint for Doctor photos, Certificates, Clinic Logos, and Clinic Photos.
    POST /api/practices/onboarding/upload/
    Form-data: file=<file>, upload_type='doctor_photo'|'certificate'|'clinic_logo'|'clinic_photo'
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response({"error": "No file uploaded. Please include 'file' in form-data."}, status=status.HTTP_400_BAD_REQUEST)

        upload_type = request.data.get('upload_type', 'clinic_photo')
        allowed_types = ['doctor_photo', 'certificate', 'clinic_logo', 'clinic_photo']
        if upload_type not in allowed_types:
            return Response(
                {"error": f"Invalid upload_type. Must be one of {allowed_types}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        ext = os.path.splitext(uploaded_file.name)[1].lower()
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.pdf']
        if ext not in allowed_extensions:
            return Response(
                {"error": f"Unsupported file format '{ext}'. Allowed formats: {allowed_extensions}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Generate unique filename
        unique_filename = f"onboarding/{upload_type}_{uuid.uuid4().hex[:12]}{ext}"
        saved_path = default_storage.save(unique_filename, uploaded_file)
        file_url = default_storage.url(saved_path)

        # Build full URL if relative
        if not file_url.startswith('http'):
            file_url = request.build_absolute_uri(file_url)

        return Response(
            {
                "success": True,
                "upload_type": upload_type,
                "file_path": saved_path,
                "file_url": file_url,
            },
            status=status.HTTP_201_CREATED
        )


# =====================================================================
# 3. CLINIC SERVICES, TIMINGS & IMAGES CRUD VIEWS
# =====================================================================

class PracticeServiceListCreateView(generics.ListCreateAPIView):
    """
    List and create clinical services in a practice.
    GET /api/practices/<practice_id>/services/
    POST /api/practices/<practice_id>/services/
    """
    serializer_class = PracticeServiceSerializer
    permission_classes = [IsAuthenticated, IsPracticeMember]

    def get_queryset(self):
        practice_id = self.kwargs.get('practice_id')
        return PracticeService.objects.filter(practice_id=practice_id, is_active=True).order_by('name')

    def perform_create(self, serializer):
        practice = get_object_or_404(Practice, id=self.kwargs.get('practice_id'), is_active=True)
        doctor = getattr(self.request.user, 'doctor_profile', None)
        serializer.save(practice=practice, doctor=doctor)


class PracticeServiceDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    View, update or delete a clinical service.
    GET /api/practices/<practice_id>/services/<pk>/
    PATCH /api/practices/<practice_id>/services/<pk>/
    DELETE /api/practices/<practice_id>/services/<pk>/
    """
    serializer_class = PracticeServiceSerializer
    permission_classes = [IsAuthenticated, IsPracticeAdmin]

    def get_queryset(self):
        practice_id = self.kwargs.get('practice_id')
        return PracticeService.objects.filter(practice_id=practice_id)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=['is_active'])


class DoctorScheduleListCreateView(APIView):
    """
    List and configure weekly doctor schedules and consultation shifts in a practice.
    GET /api/practices/<practice_id>/timings/
    POST /api/practices/<practice_id>/timings/
    """
    permission_classes = [IsAuthenticated, IsPracticeMember]

    def get(self, request, practice_id):
        practice = get_object_or_404(Practice, id=practice_id, is_active=True)
        doctor_id = request.query_params.get('doctor_id')
        qs = DoctorSchedule.objects.filter(practice=practice, is_active=True)
        if doctor_id:
            qs = qs.filter(doctor_id=doctor_id)
        serializer = DoctorScheduleSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, practice_id):
        practice = get_object_or_404(Practice, id=practice_id, is_active=True)
        doctor = getattr(request.user, 'doctor_profile', None)
        if not doctor:
            return Response(
                {"error": "Authenticated user does not have a doctor profile."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = DoctorScheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        schedule = serializer.save(practice=practice, doctor=doctor)
        return Response(DoctorScheduleSerializer(schedule).data, status=status.HTTP_201_CREATED)


class DoctorScheduleDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    View, update or delete a specific schedule slot.
    GET /api/practices/<practice_id>/timings/<pk>/
    PATCH /api/practices/<practice_id>/timings/<pk>/
    DELETE /api/practices/<practice_id>/timings/<pk>/
    """
    serializer_class = DoctorScheduleSerializer
    permission_classes = [IsAuthenticated, IsPracticeAdmin]

    def get_queryset(self):
        practice_id = self.kwargs.get('practice_id')
        return DoctorSchedule.objects.filter(practice_id=practice_id)


class PracticeImageListCreateView(generics.ListCreateAPIView):
    """
    List and add clinic photos for a practice.
    GET /api/practices/<practice_id>/images/
    POST /api/practices/<practice_id>/images/
    """
    serializer_class = PracticeImageSerializer
    permission_classes = [IsAuthenticated, IsPracticeMember]

    def get_queryset(self):
        practice_id = self.kwargs.get('practice_id')
        return PracticeImage.objects.filter(practice_id=practice_id).order_by('order', '-created_at')

    def perform_create(self, serializer):
        practice = get_object_or_404(Practice, id=self.kwargs.get('practice_id'), is_active=True)
        serializer.save(practice=practice)


class PracticeImageDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    View, update or delete a clinic photo.
    GET /api/practices/<practice_id>/images/<pk>/
    PATCH /api/practices/<practice_id>/images/<pk>/
    DELETE /api/practices/<practice_id>/images/<pk>/
    """
    serializer_class = PracticeImageSerializer
    permission_classes = [IsAuthenticated, IsPracticeAdmin]

    def get_queryset(self):
        practice_id = self.kwargs.get('practice_id')
        return PracticeImage.objects.filter(practice_id=practice_id)

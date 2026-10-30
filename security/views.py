import os
import uuid
from django.conf import settings
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from practices.models import Practice, PracticeMembership
from leads.services.lead_service import LeadService
from security.models import AuditLog, BackupRecord, ConsentRecord
from security.permissions import (
    IsPracticeAdmin,
    IsPracticeDoctor,
    IsPracticeOwner,
    IsPracticeStaff,
    RoleChecker,
)
from security.serializers import (
    AuditLogSerializer,
    BackupCreateSerializer,
    BackupRecordSerializer,
    ConsentRecordCreateSerializer,
    ConsentRecordSerializer,
    ConsentWithdrawSerializer,
)
from security.services.audit_service import AuditService
from security.services.backup_service import BackupService
from security.services.consent_service import ConsentService
from security.throttling import AuthRateThrottle, BackupExportThrottle, PublicInquiryThrottle


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


# =====================================================================
# 1. ROLE CHECKS & RBAC MATRIX
# =====================================================================

class MyPermissionsView(APIView):
    """
    Returns the authenticated user's active role, practice memberships,
    and granular capability flags.
    GET /api/security/roles/my-permissions/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Provide 'X-Practice-ID' header."}, status=status.HTTP_400_BAD_REQUEST)

        membership = RoleChecker.get_membership(request.user, practice)
        if not membership:
            return Response({"error": "You are not an active member of this clinic."}, status=status.HTTP_403_FORBIDDEN)

        role = membership.role
        return Response({
            "user_id": str(request.user.id),
            "email": request.user.email,
            "practice_id": str(practice.id),
            "practice_name": practice.name,
            "role": role,
            "role_display": membership.get_role_display(),
            "capabilities": {
                "can_manage_billing": role == PracticeMembership.ROLE_OWNER,
                "can_manage_backups": role in [PracticeMembership.ROLE_OWNER, PracticeMembership.ROLE_ADMIN],
                "can_view_audit_logs": role in [PracticeMembership.ROLE_OWNER, PracticeMembership.ROLE_ADMIN],
                "can_manage_roles": role in [PracticeMembership.ROLE_OWNER, PracticeMembership.ROLE_ADMIN],
                "can_approve_clinical_content": role in [PracticeMembership.ROLE_OWNER, PracticeMembership.ROLE_ADMIN, PracticeMembership.ROLE_DOCTOR],
                "can_record_consent": True,
                "can_view_leads_and_bookings": True,
            }
        }, status=status.HTTP_200_OK)


class PracticeRolesOverviewView(APIView):
    """
    Overview of all practice team members and their RBAC assignments.
    GET /api/security/roles/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Provide 'X-Practice-ID' header."}, status=status.HTTP_400_BAD_REQUEST)
        if not RoleChecker.is_admin(request.user, practice):
            return Response({"error": "Only Practice Administrators or Owners can inspect team roles."}, status=status.HTTP_403_FORBIDDEN)

        memberships = PracticeMembership.objects.filter(
            practice=practice,
            is_active=True
        ).select_related('user').order_by('role', '-joined_at')

        team = [
            {
                "membership_id": str(m.id),
                "user_id": str(m.user.id),
                "name": m.user.get_full_name() or m.user.email,
                "email": m.user.email,
                "phone_number": getattr(m.user, 'phone_number', ''),
                "role": m.role,
                "role_display": m.get_role_display(),
                "joined_at": m.joined_at,
            }
            for m in memberships
        ]

        return Response({
            "practice_id": str(practice.id),
            "practice_name": practice.name,
            "total_members": len(team),
            "team": team
        }, status=status.HTTP_200_OK)


# =====================================================================
# 2. AUDIT LOGS
# =====================================================================

class AuditLogListView(APIView):
    """
    Queryable security and compliance audit trail.
    GET /api/security/audit-logs/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Provide 'X-Practice-ID' header."}, status=status.HTTP_400_BAD_REQUEST)
        if not RoleChecker.is_admin(request.user, practice):
            return Response({"error": "Permission denied: Audit logs require Administrator or Owner role."}, status=status.HTTP_403_FORBIDDEN)

        qs = AuditLog.objects.filter(practice=practice)

        category = request.query_params.get('category')
        if category:
            qs = qs.filter(category=category.strip())

        action = request.query_params.get('action')
        if action:
            qs = qs.filter(action__icontains=action.strip())

        severity = request.query_params.get('severity')
        if severity:
            qs = qs.filter(severity=severity.strip())

        date_from = request.query_params.get('date_from')
        if date_from:
            qs = qs.filter(created_at__gte=date_from.strip())

        date_to = request.query_params.get('date_to')
        if date_to:
            qs = qs.filter(created_at__lte=date_to.strip())

        limit = min(int(request.query_params.get('limit', 50)), 200)
        serializer = AuditLogSerializer(qs.order_by('-created_at')[:limit], many=True)

        return Response({
            "total_count": qs.count(),
            "results": serializer.data
        }, status=status.HTTP_200_OK)


class AuditLogDetailView(APIView):
    """
    Inspection of a single audit event with old vs new JSON diff state.
    GET /api/security/audit-logs/<pk>/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Provide 'X-Practice-ID' header."}, status=status.HTTP_400_BAD_REQUEST)
        if not RoleChecker.is_admin(request.user, practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        log = get_object_or_404(AuditLog, id=pk, practice=practice)
        serializer = AuditLogSerializer(log)
        return Response(serializer.data, status=status.HTTP_200_OK)


# =====================================================================
# 3. CONSENT RECORDS & PATIENT PRIVACY
# =====================================================================

class ConsentRecordListCreateView(APIView):
    """
    List practice consent records or record explicit patient consent.
    GET /api/security/consents/
    POST /api/security/consents/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Provide 'X-Practice-ID' header."}, status=status.HTTP_400_BAD_REQUEST)
        if not RoleChecker.is_staff(request.user, practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        qs = ConsentRecord.objects.filter(practice=practice)

        patient = request.query_params.get('patient')
        if patient:
            qs = qs.filter(patient_identifier__icontains=patient.strip())

        consent_type = request.query_params.get('type')
        if consent_type:
            qs = qs.filter(consent_type=consent_type.strip())

        status_param = request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param.strip())

        limit = min(int(request.query_params.get('limit', 50)), 100)
        serializer = ConsentRecordSerializer(qs.order_by('-granted_at')[:limit], many=True)
        return Response({
            "total_count": qs.count(),
            "results": serializer.data
        }, status=status.HTTP_200_OK)

    def post(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Provide 'X-Practice-ID' header."}, status=status.HTTP_400_BAD_REQUEST)
        if not RoleChecker.is_staff(request.user, practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        serializer = ConsentRecordCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        record = ConsentService.record_consent(
            practice=practice,
            data=serializer.validated_data,
            request=request
        )

        return Response(ConsentRecordSerializer(record).data, status=status.HTTP_201_CREATED)


class ConsentWithdrawView(APIView):
    """
    Patient consent withdrawal / opt-out endpoint.
    POST /api/security/consents/withdraw/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Provide 'X-Practice-ID' header."}, status=status.HTTP_400_BAD_REQUEST)
        if not RoleChecker.is_staff(request.user, practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        serializer = ConsentWithdrawSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        val = serializer.validated_data

        revoked = ConsentService.withdraw_consent(
            practice=practice,
            patient_identifier=val['patient_identifier'],
            consent_type=val.get('consent_type'),
            reason=val.get('reason', ''),
            performed_by=request.user,
            request=request
        )

        return Response({
            "success": True,
            "revoked_count": len(revoked),
            "message": f"Successfully revoked {len(revoked)} consent records for {val['patient_identifier']}."
        }, status=status.HTTP_200_OK)


class PublicConsentIntakeView(APIView):
    """
    Public patient consent acceptance endpoint (e.g., website intake / mobile consent gate).
    POST /api/security/public/<practice_slug_or_domain>/consent/
    """
    permission_classes = [AllowAny]
    throttle_classes = [PublicInquiryThrottle]

    def post(self, request, practice_slug_or_domain):
        practice, _ = LeadService.resolve_practice_and_website(practice_slug_or_domain)
        if not practice:
            return Response(
                {"error": f"Clinic not found for identifier '{practice_slug_or_domain}'."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ConsentRecordCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        record = ConsentService.record_consent(
            practice=practice,
            data=serializer.validated_data,
            request=request
        )

        return Response({
            "success": True,
            "consent_id": str(record.id),
            "audit_hash": record.audit_hash,
            "message": "Consent recorded and cryptographically signed."
        }, status=status.HTTP_201_CREATED)


class ConsentCheckView(APIView):
    """
    Verifies whether a patient has active consent for a specific communication/clinical channel.
    GET /api/security/consents/check/?patient=<phone>&type=<whatsapp_notifications>
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Provide 'X-Practice-ID' header."}, status=status.HTTP_400_BAD_REQUEST)
        if not RoleChecker.is_staff(request.user, practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        patient = request.query_params.get('patient')
        consent_type = request.query_params.get('type')

        if not patient or not consent_type:
            return Response({"error": "Both 'patient' and 'type' parameters are required."}, status=status.HTTP_400_BAD_REQUEST)

        has_consent = ConsentService.has_active_consent(practice, patient, consent_type)
        return Response({
            "patient_identifier": patient,
            "consent_type": consent_type,
            "has_active_consent": has_consent
        }, status=status.HTTP_200_OK)


# =====================================================================
# 4. BACKUPS & DISASTER RECOVERY
# =====================================================================

class BackupListCreateView(APIView):
    """
    List existing backups or trigger an on-demand snapshot of clinic data.
    GET /api/security/backups/
    POST /api/security/backups/
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [BackupExportThrottle]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Provide 'X-Practice-ID' header."}, status=status.HTTP_400_BAD_REQUEST)
        if not RoleChecker.is_admin(request.user, practice):
            return Response({"error": "Permission denied: Requires Administrator or Owner role."}, status=status.HTTP_403_FORBIDDEN)

        qs = BackupRecord.objects.filter(practice=practice).order_by('-created_at')
        serializer = BackupRecordSerializer(qs[:50], many=True)
        return Response({
            "total_count": qs.count(),
            "results": serializer.data
        }, status=status.HTTP_200_OK)

    def post(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Provide 'X-Practice-ID' header."}, status=status.HTTP_400_BAD_REQUEST)
        if not RoleChecker.is_admin(request.user, practice):
            return Response({"error": "Only Practice Administrators and Owners can generate backups."}, status=status.HTTP_403_FORBIDDEN)

        serializer = BackupCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        val = serializer.validated_data

        backup = BackupService.create_backup(
            practice=practice,
            user=request.user,
            backup_name=val.get('backup_name'),
            backup_type=val.get('backup_type', BackupRecord.TYPE_MANUAL),
            request=request
        )

        return Response(BackupRecordSerializer(backup).data, status=status.HTTP_201_CREATED)


class BackupVerifyView(APIView):
    """
    Integrity test: Recomputes SHA-256 checksum and verifies archive JSON schema.
    POST /api/security/backups/<uuid:pk>/verify/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Provide 'X-Practice-ID' header."}, status=status.HTTP_400_BAD_REQUEST)
        if not RoleChecker.is_admin(request.user, practice):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        backup = get_object_or_404(BackupRecord, id=pk, practice=practice)
        verification = BackupService.verify_backup(backup)

        status_code = status.HTTP_200_OK if verification.get('is_valid') else status.HTTP_400_BAD_REQUEST
        return Response(verification, status=status_code)


class BackupDownloadView(APIView):
    """
    Secure download of verified practice backup archive.
    Restricted strictly to the Practice Owner.
    GET /api/security/backups/<uuid:pk>/download/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Provide 'X-Practice-ID' header."}, status=status.HTTP_400_BAD_REQUEST)
        if not RoleChecker.is_owner(request.user, practice):
            return Response({"error": "Sensitive data download requires Practice Owner credentials."}, status=status.HTTP_403_FORBIDDEN)

        backup = get_object_or_404(BackupRecord, id=pk, practice=practice)
        full_path = os.path.join(settings.MEDIA_ROOT, backup.file_path)

        if not os.path.exists(full_path):
            raise Http404("Backup file not found on disk storage.")

        AuditService.log(
            practice=practice,
            action="backup.downloaded",
            category=AuditLog.CATEGORY_BACKUP,
            description=f"Backup archive '{backup.backup_name}' downloaded by Practice Owner {request.user.email}.",
            actor=request.user,
            severity=AuditLog.SEVERITY_WARNING,
            target_model="BackupRecord",
            target_id=str(backup.id),
            target_repr=backup.backup_name,
            request=request
        )

        return FileResponse(
            open(full_path, 'rb'),
            as_attachment=True,
            filename=f"{backup.backup_name}.json"
        )

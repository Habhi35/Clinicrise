from django.urls import path
from security.views import (
    AuditLogDetailView,
    AuditLogListView,
    BackupDownloadView,
    BackupListCreateView,
    BackupVerifyView,
    ConsentCheckView,
    ConsentRecordListCreateView,
    ConsentWithdrawView,
    MyPermissionsView,
    PracticeRolesOverviewView,
    PublicConsentIntakeView,
)

app_name = 'security'

urlpatterns = [
    # ---------------------------------------------------------
    # 1. Role Checks & Granular RBAC Matrix
    # ---------------------------------------------------------
    path('roles/', PracticeRolesOverviewView.as_view(), name='roles_overview'),
    path('roles/my-permissions/', MyPermissionsView.as_view(), name='my_permissions'),

    # ---------------------------------------------------------
    # 2. Security & Compliance Audit Logs
    # ---------------------------------------------------------
    path('audit-logs/', AuditLogListView.as_view(), name='audit_log_list'),
    path('audit-logs/<uuid:pk>/', AuditLogDetailView.as_view(), name='audit_log_detail'),

    # ---------------------------------------------------------
    # 3. Patient Consent Records & Opt-Outs
    # ---------------------------------------------------------
    path('consents/', ConsentRecordListCreateView.as_view(), name='consent_list_create'),
    path('consents/withdraw/', ConsentWithdrawView.as_view(), name='consent_withdraw'),
    path('consents/check/', ConsentCheckView.as_view(), name='consent_check'),
    path('public/<str:practice_slug_or_domain>/consent/', PublicConsentIntakeView.as_view(), name='public_consent_intake'),

    # ---------------------------------------------------------
    # 4. Practice Snapshots, Backups & Verification
    # ---------------------------------------------------------
    path('backups/', BackupListCreateView.as_view(), name='backup_list_create'),
    path('backups/<uuid:pk>/verify/', BackupVerifyView.as_view(), name='backup_verify'),
    path('backups/<uuid:pk>/download/', BackupDownloadView.as_view(), name='backup_download'),
]

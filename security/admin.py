from django.contrib import admin
from security.models import AuditLog, BackupRecord, ConsentRecord


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['action', 'category', 'severity', 'actor_email', 'practice', 'created_at']
    list_filter = ['category', 'severity', 'created_at', 'practice']
    search_fields = ['action', 'description', 'actor_email', 'target_repr', 'ip_address']
    readonly_fields = [
        'practice', 'actor', 'actor_email', 'actor_role', 'category', 'action',
        'severity', 'target_model', 'target_id', 'target_repr', 'description',
        'changes', 'ip_address', 'user_agent', 'request_path', 'request_method',
        'status_code', 'created_at', 'updated_at'
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ConsentRecord)
class ConsentRecordAdmin(admin.ModelAdmin):
    list_display = ['patient_identifier', 'consent_type', 'status', 'version', 'audit_hash', 'practice', 'granted_at']
    list_filter = ['consent_type', 'status', 'version', 'granted_at', 'practice']
    search_fields = ['patient_identifier', 'patient_name', 'audit_hash', 'consent_text']
    readonly_fields = ['audit_hash', 'granted_at', 'created_at', 'updated_at']


@admin.register(BackupRecord)
class BackupRecordAdmin(admin.ModelAdmin):
    list_display = ['backup_name', 'backup_type', 'status', 'records_count', 'file_size_bytes', 'practice', 'created_at']
    list_filter = ['backup_type', 'status', 'created_at', 'practice']
    search_fields = ['backup_name', 'checksum_sha256']
    readonly_fields = ['checksum_sha256', 'records_count', 'file_size_bytes', 'file_path', 'created_at', 'updated_at']

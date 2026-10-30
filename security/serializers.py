from rest_framework import serializers
from security.models import AuditLog, BackupRecord, ConsentRecord


class AuditLogSerializer(serializers.ModelSerializer):
    """Serializes security and compliance audit log entries."""
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id',
            'actor',
            'actor_email',
            'actor_role',
            'category',
            'category_display',
            'action',
            'severity',
            'severity_display',
            'target_model',
            'target_id',
            'target_repr',
            'description',
            'changes',
            'ip_address',
            'user_agent',
            'request_path',
            'request_method',
            'status_code',
            'created_at',
        ]
        read_only_fields = fields


class ConsentRecordSerializer(serializers.ModelSerializer):
    """Full patient consent record representation with cryptographic audit hash."""
    consent_type_display = serializers.CharField(source='get_consent_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = ConsentRecord
        fields = [
            'id',
            'patient_identifier',
            'patient_name',
            'consent_type',
            'consent_type_display',
            'status',
            'status_display',
            'consent_text',
            'version',
            'audit_hash',
            'ip_address',
            'user_agent',
            'device_fingerprint',
            'source_url',
            'granted_at',
            'expires_at',
            'withdrawn_at',
            'withdrawn_reason',
            'metadata',
            'created_at',
        ]
        read_only_fields = ['id', 'audit_hash', 'granted_at', 'withdrawn_at', 'created_at']


class ConsentRecordCreateSerializer(serializers.Serializer):
    """Validates patient consent intake."""
    patient_identifier = serializers.CharField(max_length=100, required=True)
    patient_name = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    consent_type = serializers.ChoiceField(choices=ConsentRecord.TYPE_CHOICES, default=ConsentRecord.TYPE_GENERAL_INTAKE)
    consent_text = serializers.CharField(required=False, allow_blank=True, default="")
    version = serializers.CharField(max_length=20, required=False, default="1.0")
    source_url = serializers.URLField(max_length=500, required=False, allow_blank=True, default="")
    expires_at = serializers.DateTimeField(required=False, allow_null=True, default=None)
    metadata = serializers.DictField(required=False, default=dict)


class ConsentWithdrawSerializer(serializers.Serializer):
    """Validates patient consent withdrawal / opt-out."""
    patient_identifier = serializers.CharField(max_length=100, required=True)
    consent_type = serializers.ChoiceField(choices=ConsentRecord.TYPE_CHOICES, required=False, allow_null=True)
    reason = serializers.CharField(required=False, allow_blank=True, default="Patient requested revocation")


class BackupRecordSerializer(serializers.ModelSerializer):
    """Serializes practice backup archives and verification status."""
    backup_type_display = serializers.CharField(source='get_backup_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = BackupRecord
        fields = [
            'id',
            'backup_name',
            'backup_type',
            'backup_type_display',
            'status',
            'status_display',
            'file_path',
            'file_size_bytes',
            'records_count',
            'checksum_sha256',
            'manifest',
            'expires_at',
            'error_message',
            'created_at',
        ]
        read_only_fields = fields


class BackupCreateSerializer(serializers.Serializer):
    """Validates on-demand backup generation request."""
    backup_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    backup_type = serializers.ChoiceField(choices=BackupRecord.TYPE_CHOICES, default=BackupRecord.TYPE_MANUAL)

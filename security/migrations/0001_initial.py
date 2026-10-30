from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('practices', '0002_doctor_onboarding'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('actor_email', models.CharField(blank=True, help_text='Cached email for historical permanence', max_length=255)),
                ('actor_role', models.CharField(blank=True, help_text='Role at the time of the action', max_length=50)),
                ('category', models.CharField(choices=[('auth', 'Authentication & Access'), ('rbac', 'Roles & Team Permissions'), ('patient_privacy', 'Patient Privacy & PHI Access'), ('consent', 'Patient Consent Management'), ('clinical', 'Clinical Content & Approvals'), ('billing', 'Billing & Financial Operations'), ('backup', 'Data Backup & Disaster Recovery'), ('security', 'System Security & Rate Limiting')], db_index=True, max_length=30)),
                ('action', models.CharField(db_index=True, help_text='e.g. auth.login, role.grant, patient.export', max_length=100)),
                ('severity', models.CharField(choices=[('info', 'Informational'), ('warning', 'Security Warning'), ('critical', 'Critical Alert')], db_index=True, default='info', max_length=20)),
                ('target_model', models.CharField(blank=True, help_text='e.g. BookingRequest, Lead, WebsitePage', max_length=100)),
                ('target_id', models.CharField(blank=True, help_text='UUID or identifier of affected entity', max_length=100)),
                ('target_repr', models.CharField(blank=True, help_text='Human-readable representation', max_length=255)),
                ('description', models.TextField(help_text='Clear explanation of the action performed')),
                ('changes', models.JSONField(blank=True, default=dict, help_text='Old vs New state dictionary')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True)),
                ('request_path', models.CharField(blank=True, max_length=500)),
                ('request_method', models.CharField(blank=True, max_length=10)),
                ('status_code', models.PositiveIntegerField(blank=True, null=True)),
                ('actor', models.ForeignKey(blank=True, help_text='User who initiated the action', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='security_audit_logs', to=settings.AUTH_USER_MODEL)),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_records', to='practices.practice')),
            ],
            options={
                'verbose_name': 'Audit Log',
                'verbose_name_plural': 'Audit Logs',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['practice', 'created_at'], name='security_au_practic_3c2d1a_idx'),
                    models.Index(fields=['practice', 'category'], name='security_au_practic_5e6f7a_idx'),
                    models.Index(fields=['practice', 'action'], name='security_au_practic_8b9c0d_idx'),
                    models.Index(fields=['practice', 'severity'], name='security_au_practic_1e2f3a_idx'),
                    models.Index(fields=['practice', 'actor'], name='security_au_practic_4b5c6d_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='BackupRecord',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('backup_name', models.CharField(max_length=255)),
                ('backup_type', models.CharField(choices=[('manual', 'Manual Practice Snapshot'), ('automated', 'Automated Scheduled Backup'), ('pre_update', 'Pre-System Update Snapshot')], default='manual', max_length=30)),
                ('status', models.CharField(choices=[('pending', 'Generating Snapshot...'), ('completed', 'Completed & Integrity Verified'), ('failed', 'Failed'), ('expired', 'Expired & Purged')], db_index=True, default='pending', max_length=20)),
                ('file_path', models.CharField(blank=True, max_length=500)),
                ('file_size_bytes', models.BigIntegerField(default=0)),
                ('records_count', models.PositiveIntegerField(default=0)),
                ('checksum_sha256', models.CharField(blank=True, max_length=64)),
                ('manifest', models.JSONField(blank=True, default=dict, help_text='Summary of exported tables and record counts')),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('error_message', models.TextField(blank=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_backups', to=settings.AUTH_USER_MODEL)),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_records', to='practices.practice')),
            ],
            options={
                'verbose_name': 'Practice Backup',
                'verbose_name_plural': 'Practice Backups',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['practice', 'created_at'], name='security_ba_practic_7d8e9f_idx'),
                    models.Index(fields=['practice', 'status'], name='security_ba_practic_0a1b2c_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='ConsentRecord',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('patient_identifier', models.CharField(db_index=True, help_text='Phone number (+91...), email, or patient hospital ID', max_length=100)),
                ('patient_name', models.CharField(blank=True, max_length=200)),
                ('consent_type', models.CharField(choices=[('teleconsultation', 'Telemedicine & Video Consultation Recording'), ('marketing', 'Promotional & Educational Health Communications'), ('treatment_procedure', 'Informed Clinical Procedure / Surgery Consent'), ('records_sharing', 'Sharing Health Records with Diagnostic Labs & Specialists'), ('whatsapp_notifications', 'WhatsApp Reminders & Care Updates'), ('sms_notifications', 'SMS Alerts & Reminders'), ('general_intake', 'General Clinic Intake & Privacy Terms')], db_index=True, max_length=50)),
                ('status', models.CharField(choices=[('granted', 'Granted / Active'), ('withdrawn', 'Revoked / Withdrawn'), ('expired', 'Expired')], db_index=True, default='granted', max_length=20)),
                ('consent_text', models.TextField(help_text='Exact legal disclosure / terms shown to the patient')),
                ('version', models.CharField(default='1.0', help_text='Version of clinic terms agreed upon', max_length=20)),
                ('audit_hash', models.CharField(db_index=True, editable=False, help_text='SHA-256 cryptographic signature of agreement', max_length=64)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True)),
                ('device_fingerprint', models.CharField(blank=True, max_length=128)),
                ('source_url', models.URLField(blank=True, max_length=500)),
                ('granted_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('withdrawn_at', models.DateTimeField(blank=True, null=True)),
                ('withdrawn_reason', models.TextField(blank=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_records', to='practices.practice')),
                ('withdrawn_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='revoked_consents', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Consent Record',
                'verbose_name_plural': 'Consent Records',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['practice', 'patient_identifier'], name='security_co_practic_1f2a3b_idx'),
                    models.Index(fields=['practice', 'consent_type', 'status'], name='security_co_practic_4c5d6e_idx'),
                    models.Index(fields=['practice', 'created_at'], name='security_co_practic_7f8a9b_idx'),
                ],
            },
        ),
    ]

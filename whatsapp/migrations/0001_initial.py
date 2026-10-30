from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('practices', '0002_doctor_onboarding'),
        ('bookings', '0001_initial'),
        ('leads', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='WhatsAppConfig',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('provider', models.CharField(choices=[('meta_cloud_api', 'Meta WhatsApp Cloud API'), ('twilio', 'Twilio WhatsApp API'), ('gupshup', 'Gupshup Enterprise WhatsApp'), ('mock_simulator', 'Mock Simulator (Testing & Local Dev)')], default='mock_simulator', max_length=50)),
                ('phone_number_id', models.CharField(blank=True, max_length=100)),
                ('waba_id', models.CharField(blank=True, max_length=100)),
                ('access_token', models.TextField(blank=True)),
                ('webhook_verify_token', models.CharField(blank=True, max_length=128)),
                ('display_phone_number', models.CharField(blank=True, max_length=30)),
                ('business_name', models.CharField(blank=True, max_length=200)),
                ('is_enabled', models.BooleanField(default=True)),
                ('auto_confirmation_enabled', models.BooleanField(default=True)),
                ('auto_reminders_enabled', models.BooleanField(default=True)),
                ('lead_auto_reply_enabled', models.BooleanField(default=True)),
                ('post_visit_review_enabled', models.BooleanField(default=True)),
                ('daily_send_limit', models.PositiveIntegerField(default=1000)),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_records', to='practices.practice')),
            ],
            options={
                'verbose_name': 'WhatsApp Configuration',
                'verbose_name_plural': 'WhatsApp Configurations',
            },
        ),
        migrations.CreateModel(
            name='WhatsAppTemplate',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('template_name', models.CharField(db_index=True, max_length=100)),
                ('title', models.CharField(max_length=200)),
                ('category', models.CharField(choices=[('UTILITY', 'Utility (Appointment Confirmations & Reminders)'), ('MARKETING', 'Marketing (Promotions & GBP Review Requests)'), ('AUTHENTICATION', 'Authentication (OTP / Verification)')], default='UTILITY', max_length=30)),
                ('language', models.CharField(default='en_US', max_length=15)),
                ('meta_template_id', models.CharField(blank=True, max_length=100)),
                ('meta_status', models.CharField(choices=[('APPROVED', 'Approved by Meta'), ('PENDING', 'Pending Meta Approval'), ('REJECTED', 'Rejected by Meta'), ('PAUSED', 'Paused')], default='APPROVED', max_length=20)),
                ('header_type', models.CharField(choices=[('none', 'None'), ('text', 'Text Header'), ('image', 'Image Header')], default='none', max_length=20)),
                ('header_text', models.CharField(blank=True, max_length=100)),
                ('body_text', models.TextField()),
                ('footer_text', models.CharField(blank=True, default='Reply STOP to unsubscribe', max_length=100)),
                ('buttons', models.JSONField(blank=True, default=list)),
                ('variable_mapping', models.JSONField(blank=True, default=dict)),
                ('is_active', models.BooleanField(default=True)),
                ('is_system_default', models.BooleanField(default=False)),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_records', to='practices.practice')),
            ],
            options={
                'verbose_name': 'WhatsApp Template',
                'verbose_name_plural': 'WhatsApp Templates',
                'ordering': ['category', 'template_name'],
                'unique_together': {('practice', 'template_name', 'language')},
            },
        ),
        migrations.CreateModel(
            name='WhatsAppOptOut',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('phone_number', models.CharField(db_index=True, max_length=30)),
                ('patient_name', models.CharField(blank=True, max_length=200)),
                ('reason', models.CharField(choices=[('keyword_stop', 'Inbound STOP / Opt-Out Keyword'), ('patient_request', 'Patient Verbal / Written Request'), ('staff_manual', 'Frontdesk Receptionist Manual Toggle'), ('delivery_bounce', 'Repeated Delivery Bounce / Invalid Number'), ('other', 'Other Compliance Withdrawal')], default='keyword_stop', max_length=50)),
                ('reason_notes', models.TextField(blank=True)),
                ('is_opted_out', models.BooleanField(db_index=True, default=True)),
                ('opted_out_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('opted_in_at', models.DateTimeField(blank=True, null=True)),
                ('source_channel', models.CharField(choices=[('inbound_whatsapp', 'Inbound WhatsApp Message'), ('web_form', 'Website Privacy Form'), ('reception_desk', 'Frontdesk / Reception'), ('patient_portal', 'Patient Portal'), ('api', 'API / Integration')], default='inbound_whatsapp', max_length=40)),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_records', to='practices.practice')),
            ],
            options={
                'verbose_name': 'WhatsApp Opt-Out',
                'verbose_name_plural': 'WhatsApp Opt-Outs',
                'ordering': ['-opted_out_at'],
                'unique_together': {('practice', 'phone_number')},
            },
        ),
        migrations.AddIndex(
            model_name='whatsappoptout',
            index=models.Index(fields=['practice', 'phone_number', 'is_opted_out'], name='whatsapp_wh_practic_77840c_idx'),
        ),
        migrations.CreateModel(
            name='WhatsAppReminder',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reminder_type', models.CharField(choices=[('appointment_24h', '24-Hour Advance Appointment Reminder'), ('appointment_2h', '2-Hour Immediate Consultation Reminder'), ('appointment_day_of', 'Day-of Morning Consultation Reminder'), ('lead_follow_up', '24-Hour Lead Follow-up Reminder'), ('post_visit_review', 'Post-Consultation Google Review Request')], db_index=True, max_length=40)),
                ('scheduled_for', models.DateTimeField(db_index=True)),
                ('status', models.CharField(choices=[('pending', 'Scheduled / Pending Dispatch'), ('sent', 'Dispatched Successfully'), ('cancelled', 'Cancelled (Rescheduled or Cancelled Visit)'), ('failed', 'Failed to Dispatch'), ('skipped_opt_out', 'Skipped (Patient Opted Out)')], db_index=True, default='pending', max_length=30)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('error_message', models.TextField(blank=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('booking', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='whatsapp_reminders', to='bookings.bookingrequest')),
                ('lead', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='whatsapp_reminders', to='leads.lead')),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_records', to='practices.practice')),
            ],
            options={
                'verbose_name': 'WhatsApp Reminder',
                'verbose_name_plural': 'WhatsApp Reminders',
                'ordering': ['scheduled_for'],
            },
        ),
        migrations.AddIndex(
            model_name='whatsappreminder',
            index=models.Index(fields=['practice', 'status', 'scheduled_for'], name='whatsapp_wh_practic_a87261_idx'),
        ),
        migrations.AddIndex(
            model_name='whatsappreminder',
            index=models.Index(fields=['practice', 'booking', 'reminder_type'], name='whatsapp_wh_practic_2594bc_idx'),
        ),
        migrations.CreateModel(
            name='WhatsAppMessageLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('message_id', models.CharField(db_index=True, max_length=64, unique=True)),
                ('provider_message_id', models.CharField(blank=True, db_index=True, max_length=128)),
                ('direction', models.CharField(choices=[('outbound', 'Outbound (Sent to Patient)'), ('inbound', 'Inbound (Received from Patient)')], db_index=True, default='outbound', max_length=20)),
                ('recipient_phone', models.CharField(db_index=True, max_length=30)),
                ('recipient_name', models.CharField(blank=True, max_length=200)),
                ('sender_phone', models.CharField(blank=True, max_length=30)),
                ('template_name', models.CharField(blank=True, max_length=100)),
                ('message_body', models.TextField()),
                ('parameters', models.JSONField(blank=True, default=dict)),
                ('status', models.CharField(choices=[('queued', 'Queued for Delivery'), ('sent', 'Sent by Gateway'), ('delivered', 'Delivered to Recipient Device'), ('read', 'Read / Opened by Recipient'), ('failed', 'Delivery Failed'), ('blocked_opt_out', 'Blocked by Opt-Out Registry')], db_index=True, default='sent', max_length=30)),
                ('error_code', models.CharField(blank=True, max_length=50)),
                ('error_message', models.TextField(blank=True)),
                ('cost_tier', models.CharField(default='utility', max_length=30)),
                ('sent_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('delivered_at', models.DateTimeField(blank=True, null=True)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('failed_at', models.DateTimeField(blank=True, null=True)),
                ('booking', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='whatsapp_messages', to='bookings.bookingrequest')),
                ('lead', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='whatsapp_messages', to='leads.lead')),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_records', to='practices.practice')),
                ('reminder', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='message_logs', to='whatsapp.whatsappreminder')),
                ('template', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='message_logs', to='whatsapp.whatsapptemplate')),
            ],
            options={
                'verbose_name': 'WhatsApp Message Log',
                'verbose_name_plural': 'WhatsApp Message Logs',
                'ordering': ['-sent_at'],
            },
        ),
        migrations.AddIndex(
            model_name='whatsappmessagelog',
            index=models.Index(fields=['practice', 'status'], name='whatsapp_wh_practic_3b84ac_idx'),
        ),
        migrations.AddIndex(
            model_name='whatsappmessagelog',
            index=models.Index(fields=['practice', 'recipient_phone'], name='whatsapp_wh_practic_281a44_idx'),
        ),
        migrations.AddIndex(
            model_name='whatsappmessagelog',
            index=models.Index(fields=['practice', 'direction', 'sent_at'], name='whatsapp_wh_practic_6f19ba_idx'),
        ),
        migrations.AddIndex(
            model_name='whatsappmessagelog',
            index=models.Index(fields=['provider_message_id'], name='whatsapp_wh_provide_73bc6a_idx'),
        ),
    ]

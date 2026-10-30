from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('practices', '0002_doctor_onboarding'),
        ('websites', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Lead',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('patient_name', models.CharField(help_text='Full name of prospective patient or contact person', max_length=200)),
                ('phone_number', models.CharField(db_index=True, help_text='Contact phone or mobile number', max_length=30)),
                ('email', models.EmailField(blank=True, help_text='Contact email address', max_length=254)),
                ('preferred_date', models.DateField(blank=True, help_text='Preferred appointment or consultation date', null=True)),
                ('preferred_time_slot', models.CharField(blank=True, help_text="e.g. 'Morning (9am-12pm)', 'Evening'", max_length=100)),
                ('service_requested', models.CharField(blank=True, help_text='Requested medical treatment or specialty', max_length=255)),
                ('doctor_requested', models.CharField(blank=True, help_text='Name of requested doctor, if any', max_length=255)),
                ('message', models.TextField(blank=True, help_text='Enquiry message, patient complaint, or notes')),
                ('status', models.CharField(choices=[('new', 'New / Uncontacted'), ('contacted', 'Contacted'), ('in_discussion', 'In Discussion'), ('appointment_scheduled', 'Appointment Scheduled'), ('converted', 'Converted / Patient Registered'), ('lost', 'Lost / Not Interested'), ('junk', 'Junk / Spam')], db_index=True, default='new', max_length=30)),
                ('priority', models.CharField(choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('urgent', 'Urgent')], default='medium', max_length=20)),
                ('is_read', models.BooleanField(db_index=True, default=False, help_text='False if new unviewed lead in inbox')),
                ('last_contacted_at', models.DateTimeField(blank=True, null=True)),
                ('follow_up_date', models.DateTimeField(blank=True, help_text='Next scheduled follow-up reminder', null=True)),
                ('lost_reason', models.CharField(blank=True, help_text='Reason why lead was marked lost', max_length=255)),
                ('source', models.CharField(choices=[('website_form', 'Website Enquiry Form'), ('whatsapp_click', 'WhatsApp Chat Click'), ('call_click', 'Phone Call Click'), ('manual', 'Reception / Frontdesk Manual Entry'), ('campaign', 'Marketing Ad Campaign'), ('referral', 'Patient / Doctor Referral'), ('other', 'Other')], db_index=True, default='website_form', max_length=30)),
                ('source_url', models.URLField(blank=True, help_text='Page URL where the enquiry was submitted', max_length=500)),
                ('referrer', models.TextField(blank=True, help_text='HTTP Referrer URL')),
                ('utm_source', models.CharField(blank=True, max_length=100)),
                ('utm_medium', models.CharField(blank=True, max_length=100)),
                ('utm_campaign', models.CharField(blank=True, max_length=150)),
                ('utm_term', models.CharField(blank=True, max_length=150)),
                ('utm_content', models.CharField(blank=True, max_length=150)),
                ('device_type', models.CharField(blank=True, help_text='mobile, desktop, tablet', max_length=50)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True)),
                ('consent_given', models.BooleanField(default=True, help_text='Explicit consent granted by user')),
                ('consent_timestamp', models.DateTimeField(default=django.utils.timezone.now, help_text='Exact timestamp of consent acceptance')),
                ('consent_text', models.TextField(blank=True, default='I agree to receive communications regarding my enquiry via Phone, WhatsApp, SMS and Email from ClinicRise and the clinic team.', help_text='The exact terms/disclosure presented to the user when consent was captured')),
                ('consent_ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('whatsapp_opt_in', models.BooleanField(default=True, help_text='Opted in for WhatsApp notifications & appointment reminders')),
                ('call_opt_in', models.BooleanField(default=True, help_text='Opted in for phone call follow-ups')),
                ('sms_opt_in', models.BooleanField(default=True, help_text='Opted in for SMS reminders')),
                ('email_opt_in', models.BooleanField(default=True, help_text='Opted in for email communications')),
                ('consent_withdrawn', models.BooleanField(default=False, help_text='Set to True if patient requests to unsubscribe/opt-out')),
                ('consent_withdrawn_at', models.DateTimeField(blank=True, null=True)),
                ('consent_withdrawn_reason', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assigned_to', models.ForeignKey(blank=True, help_text='Staff member or doctor assigned to triage and follow up', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_leads', to=settings.AUTH_USER_MODEL)),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='leads_lead_records', to='practices.practice')),
                ('website', models.ForeignKey(blank=True, help_text='Website from which this lead was generated, if applicable', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='leads', to='websites.clinicwebsite')),
            ],
            options={
                'verbose_name': 'Lead / Enquiry',
                'verbose_name_plural': 'Leads & Enquiries',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='LeadActivity',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('activity_type', models.CharField(choices=[('status_change', 'Status Changed'), ('note_added', 'Internal Note Added'), ('call_logged', 'Phone Call Logged'), ('whatsapp_sent', 'WhatsApp Message Sent'), ('email_sent', 'Email Sent'), ('assignment', 'Lead Reassigned'), ('consent_updated', 'Consent Preferences Updated')], default='note_added', max_length=30)),
                ('previous_status', models.CharField(blank=True, max_length=30)),
                ('new_status', models.CharField(blank=True, max_length=30)),
                ('note', models.TextField(blank=True, help_text='Description, call outcome, staff note, or change explanation')),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Additional arbitrary metadata (duration, templates, etc.)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('lead', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activities', to='leads.lead')),
                ('performed_by', models.ForeignKey(blank=True, help_text='User who logged this note or changed the status (null if system/public)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lead_activities', to=settings.AUTH_USER_MODEL)),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='leads_leadactivity_records', to='practices.practice')),
            ],
            options={
                'verbose_name': 'Lead Activity',
                'verbose_name_plural': 'Lead Activities',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ClickEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('event_type', models.CharField(choices=[('call_click', 'Phone Call Button Clicked'), ('whatsapp_click', 'WhatsApp Chat Button Clicked'), ('booking_cta_click', 'Book Appointment CTA Clicked'), ('directions_click', 'Get Directions / Maps Clicked'), ('share_click', 'Share Button Clicked')], db_index=True, max_length=30)),
                ('target_phone', models.CharField(blank=True, help_text='The phone or WhatsApp number targeted by the click', max_length=50)),
                ('doctor_id', models.UUIDField(blank=True, help_text='ID of doctor card if clicked on specific practitioner', null=True)),
                ('doctor_name', models.CharField(blank=True, max_length=255)),
                ('service_name', models.CharField(blank=True, max_length=255)),
                ('page_url', models.TextField(blank=True, help_text='Page URL where the click event occurred')),
                ('referrer', models.TextField(blank=True)),
                ('utm_source', models.CharField(blank=True, max_length=100)),
                ('utm_medium', models.CharField(blank=True, max_length=100)),
                ('utm_campaign', models.CharField(blank=True, max_length=150)),
                ('visitor_id', models.CharField(blank=True, help_text='Anonymous visitor session/cookie identifier', max_length=100)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True)),
                ('device_type', models.CharField(blank=True, help_text='mobile, desktop, tablet', max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('lead', models.ForeignKey(blank=True, help_text='Associated Lead if the click was converted or visitor provided phone', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='click_events', to='leads.lead')),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='leads_clickevent_records', to='practices.practice')),
                ('website', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='click_events', to='websites.clinicwebsite')),
            ],
            options={
                'verbose_name': 'Click Event',
                'verbose_name_plural': 'Click Events',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='lead',
            index=models.Index(fields=['practice', 'status'], name='leads_lead_practic_4c59a3_idx'),
        ),
        migrations.AddIndex(
            model_name='lead',
            index=models.Index(fields=['practice', 'is_read'], name='leads_lead_practic_314856_idx'),
        ),
        migrations.AddIndex(
            model_name='lead',
            index=models.Index(fields=['practice', 'source'], name='leads_lead_practic_584ad7_idx'),
        ),
        migrations.AddIndex(
            model_name='lead',
            index=models.Index(fields=['practice', 'created_at'], name='leads_lead_practic_7b0d91_idx'),
        ),
        migrations.AddIndex(
            model_name='clickevent',
            index=models.Index(fields=['practice', 'event_type'], name='leads_click_practic_3b9b47_idx'),
        ),
        migrations.AddIndex(
            model_name='clickevent',
            index=models.Index(fields=['practice', 'created_at'], name='leads_click_practic_9d7fc2_idx'),
        ),
    ]

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import patients.models
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('bookings', '0001_initial'),
        ('leads', '0001_initial'),
        ('practices', '0003_add_receptionist_assistant_roles'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Patient',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('patient_id', models.CharField(db_index=True, default=patients.models.generate_patient_mrn, help_text='Unique Medical Record Number (MRN) for practice patient charting', max_length=40, unique=True)),
                ('first_name', models.CharField(help_text='Patient given name', max_length=100)),
                ('last_name', models.CharField(blank=True, help_text='Patient family name / surname', max_length=100)),
                ('phone_number', models.CharField(db_index=True, help_text='Primary contact phone number (E.164)', max_length=30)),
                ('email', models.EmailField(blank=True, help_text='Optional patient email address', max_length=254)),
                ('gender', models.CharField(choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other'), ('unspecified', 'Prefer not to say')], default='unspecified', max_length=20)),
                ('date_of_birth', models.DateField(blank=True, help_text='Patient date of birth', null=True)),
                ('age', models.PositiveSmallIntegerField(blank=True, help_text='Calculated or reported age', null=True)),
                ('blood_group', models.CharField(blank=True, choices=[('A+', 'A+'), ('A-', 'A-'), ('B+', 'B+'), ('B-', 'B-'), ('AB+', 'AB+'), ('AB-', 'AB-'), ('O+', 'O+'), ('O-', 'O-'), ('unknown', 'Unknown / Not Tested')], default='unknown', max_length=15)),
                ('address', models.TextField(blank=True, help_text='Residential street address')),
                ('city', models.CharField(blank=True, max_length=100)),
                ('postal_code', models.CharField(blank=True, max_length=20)),
                ('emergency_contact_name', models.CharField(blank=True, max_length=150)),
                ('emergency_contact_phone', models.CharField(blank=True, max_length=30)),
                ('emergency_contact_relation', models.CharField(blank=True, help_text='e.g. Spouse, Parent, Sibling', max_length=50)),
                ('allergies', models.TextField(blank=True, help_text='Known drug, food, or environmental allergies (e.g. Penicillin, NSAIDs)')),
                ('chronic_conditions', models.JSONField(blank=True, default=list, help_text="List of chronic medical conditions (e.g. Diabetes, Hypertension)")),
                ('medical_alerts', models.TextField(blank=True, help_text='Critical clinical warnings displayed prominently in header banner')),
                ('tags', models.JSONField(blank=True, default=list, help_text='Categorization tags (e.g. VIP, Senior Citizen, Dental Anxiety)')),
                ('status', models.CharField(choices=[('active', 'Active Patient'), ('archived', 'Archived / Inactive'), ('inactive', 'Deactivated')], db_index=True, default='active', max_length=20)),
                ('source', models.CharField(choices=[('walk_in', 'Frontdesk Walk-in'), ('website_booking', 'Website Booking Request'), ('lead_conversion', 'Converted from Web/WhatsApp Lead'), ('phone_call', 'Phone Call Intake'), ('referral', 'Doctor / Patient Referral'), ('other', 'Other Source')], default='walk_in', max_length=30)),
                ('total_visits_count', models.PositiveIntegerField(default=0)),
                ('last_visit_date', models.DateField(blank=True, null=True)),
                ('preferred_language', models.CharField(blank=True, default='English', max_length=50)),
                ('whatsapp_opt_in', models.BooleanField(default=True)),
                ('sms_opt_in', models.BooleanField(default=True)),
                ('call_opt_in', models.BooleanField(default=True)),
                ('email_opt_in', models.BooleanField(default=True)),
                ('converted_from_lead', models.ForeignKey(blank=True, help_text='Original lead if this patient was converted from marketing inquiry', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='converted_patients', to='leads.lead')),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='patients_patient_records', to='practices.practice')),
                ('primary_doctor', models.ForeignKey(blank=True, help_text='Primary attending physician or dentist', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='primary_patients', to='practices.doctorprofile')),
            ],
            options={
                'verbose_name': 'Patient',
                'verbose_name_plural': 'Patients',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='PatientVitals',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('blood_pressure_systolic', models.PositiveSmallIntegerField(blank=True, help_text='Systolic BP (mmHg), e.g. 120', null=True)),
                ('blood_pressure_diastolic', models.PositiveSmallIntegerField(blank=True, help_text='Diastolic BP (mmHg), e.g. 80', null=True)),
                ('pulse_bpm', models.PositiveSmallIntegerField(blank=True, help_text='Heart rate / pulse in beats per min (bpm)', null=True)),
                ('temperature_fahrenheit', models.DecimalField(blank=True, decimal_places=1, help_text='Body temperature in °F, e.g. 98.6', max_digits=4, null=True)),
                ('oxygen_saturation_spo2', models.PositiveSmallIntegerField(blank=True, help_text='SpO2 percentage (e.g. 98%)', null=True)),
                ('respiratory_rate', models.PositiveSmallIntegerField(blank=True, help_text='Breaths per minute', null=True)),
                ('weight_kg', models.DecimalField(blank=True, decimal_places=2, help_text='Body weight in kg', max_digits=5, null=True)),
                ('height_cm', models.DecimalField(blank=True, decimal_places=1, help_text='Body height in cm', max_digits=5, null=True)),
                ('bmi', models.DecimalField(blank=True, decimal_places=1, help_text='Auto-calculated Body Mass Index', max_digits=4, null=True)),
                ('blood_sugar_fasting', models.PositiveSmallIntegerField(blank=True, help_text='Fasting blood sugar (mg/dL)', null=True)),
                ('blood_sugar_random', models.PositiveSmallIntegerField(blank=True, help_text='Random blood sugar (mg/dL)', null=True)),
                ('notes', models.TextField(blank=True, help_text='Clinical assistant remarks or observations')),
                ('booking', models.ForeignKey(blank=True, help_text='Associated appointment visit, if recorded during a clinic visit', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='vitals', to='bookings.bookingrequest')),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='vitals', to='patients.patient')),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='patients_patientvitals_records', to='practices.practice')),
                ('recorded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recorded_vitals', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Patient Vitals',
                'verbose_name_plural': 'Patient Vitals',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='PatientTimeline',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('performer_role', models.CharField(blank=True, help_text='e.g. receptionist, assistant, doctor, system', max_length=30)),
                ('event_type', models.CharField(choices=[('patient_created', 'Patient Registered / Intake'), ('patient_updated', 'Patient Profile Updated'), ('booking_requested', 'Appointment Requested'), ('booking_confirmed', 'Appointment Confirmed'), ('patient_checked_in', 'Patient Checked In at Frontdesk'), ('consultation_started', 'In Consultation Room with Doctor'), ('consultation_completed', 'Consultation Completed'), ('vitals_recorded', 'Vitals Recorded by Clinical Assistant'), ('clinical_note_added', 'Staff / Clinical Note Recorded'), ('follow_up_scheduled', 'Follow-up Task Scheduled'), ('follow_up_completed', 'Follow-up Task Completed'), ('phone_call_logged', 'Phone Call Logged'), ('whatsapp_sent', 'WhatsApp Notification Dispatched'), ('whatsapp_received', 'Inbound WhatsApp Reply Received'), ('consent_updated', 'Consent Preferences Updated')], db_index=True, max_length=40)),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='timeline', to='patients.patient')),
                ('performed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='patient_timeline_actions', to=settings.AUTH_USER_MODEL)),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='patients_patienttimeline_records', to='practices.practice')),
            ],
            options={
                'verbose_name': 'Patient Timeline Event',
                'verbose_name_plural': 'Patient Timeline Events',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='PatientNote',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('author_role', models.CharField(blank=True, help_text='e.g. receptionist, assistant, doctor, admin', max_length=30)),
                ('category', models.CharField(choices=[('frontdesk', 'Frontdesk / Check-In Note'), ('clinical_prep', 'Assistant Clinical Prep / Triage'), ('doctor_consultation', 'Doctor Consultation Observation'), ('follow_up', 'Follow-up Call / Recovery Check'), ('general', 'General Administrative Note')], default='general', max_length=30)),
                ('note', models.TextField(help_text='Text content of the note')),
                ('is_pinned', models.BooleanField(db_index=True, default=False, help_text='Pinned notes appear at top of patient profile banner')),
                ('pinned_at', models.DateTimeField(blank=True, null=True)),
                ('author', models.ForeignKey(blank=True, help_text='User who wrote this note', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='patient_notes', to=settings.AUTH_USER_MODEL)),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notes', to='patients.patient')),
                ('pinned_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pinned_patient_notes', to=settings.AUTH_USER_MODEL)),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='patients_patientnote_records', to='practices.practice')),
            ],
            options={
                'verbose_name': 'Patient Note',
                'verbose_name_plural': 'Patient Notes',
                'ordering': ['-is_pinned', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='PatientFollowUp',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('follow_up_type', models.CharField(choices=[('post_consultation_check', 'Post-Consultation / Procedure Check'), ('lab_report_review', 'Lab / Diagnostic Report Review'), ('medication_check', 'Medication Check & Tolerance'), ('routine_recall', 'Routine Periodic Recall / Dental Check'), ('booking_reschedule', 'Missed Booking Follow-up'), ('custom', 'Custom Clinical Task')], default='post_consultation_check', max_length=30)),
                ('priority', models.CharField(choices=[('low', 'Low Priority'), ('medium', 'Medium Priority'), ('high', 'High Priority'), ('urgent', 'Urgent / Priority')], default='medium', max_length=20)),
                ('due_date', models.DateTimeField(db_index=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('in_progress', 'In Progress / Called'), ('completed', 'Completed'), ('cancelled', 'Cancelled'), ('overdue', 'Overdue')], db_index=True, default='pending', max_length=20)),
                ('title', models.CharField(help_text='Short task summary, e.g. Post-extraction pain check', max_length=200)),
                ('instructions', models.TextField(blank=True, help_text='Guidance for receptionist or assistant executing the follow-up')),
                ('outcome_notes', models.TextField(blank=True, help_text='Notes recorded when completing follow-up')),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('assigned_to', models.ForeignKey(blank=True, help_text='Receptionist, assistant, or doctor responsible for actioning this follow-up', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_follow_ups', to=settings.AUTH_USER_MODEL)),
                ('booking', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='follow_ups', to='bookings.bookingrequest')),
                ('completed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='completed_follow_ups', to=settings.AUTH_USER_MODEL)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_follow_ups', to=settings.AUTH_USER_MODEL)),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='follow_ups', to='patients.patient')),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='patients_patientfollowup_records', to='practices.practice')),
            ],
            options={
                'verbose_name': 'Patient Follow-Up',
                'verbose_name_plural': 'Patient Follow-Ups',
                'ordering': ['due_date', '-priority'],
            },
        ),
        migrations.AddIndex(
            model_name='patient',
            index=models.Index(fields=['practice', 'phone_number'], name='patients_pa_practic_fa9333_idx'),
        ),
        migrations.AddIndex(
            model_name='patient',
            index=models.Index(fields=['practice', 'status'], name='patients_pa_practic_778f56_idx'),
        ),
        migrations.AddIndex(
            model_name='patient',
            index=models.Index(fields=['practice', 'last_visit_date'], name='patients_pa_practic_9d3e52_idx'),
        ),
        migrations.AddIndex(
            model_name='patient',
            index=models.Index(fields=['practice', 'created_at'], name='patients_pa_practic_f461bf_idx'),
        ),
        migrations.AddIndex(
            model_name='patienttimeline',
            index=models.Index(fields=['patient', 'event_type', 'created_at'], name='patients_pa_patient_fc53d1_idx'),
        ),
        migrations.AddIndex(
            model_name='patientfollowup',
            index=models.Index(fields=['practice', 'status', 'due_date'], name='patients_pa_practic_384eb1_idx'),
        ),
        migrations.AddIndex(
            model_name='patientfollowup',
            index=models.Index(fields=['practice', 'assigned_to', 'status'], name='patients_pa_practic_584c31_idx'),
        ),
    ]

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('practices', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='doctorprofile',
            name='gender',
            field=models.CharField(blank=True, choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other'), ('prefer_not_to_say', 'Prefer not to say')], max_length=20),
        ),
        migrations.AddField(
            model_name='doctorprofile',
            name='languages_spoken',
            field=models.CharField(blank=True, default='English', help_text='Comma-separated languages spoken (e.g. English, Hindi, Telugu)', max_length=255),
        ),
        migrations.AddField(
            model_name='doctorprofile',
            name='profile_photo',
            field=models.ImageField(blank=True, null=True, upload_to='doctor_photos/'),
        ),
        migrations.AddField(
            model_name='doctorprofile',
            name='profile_photo_url',
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='doctorprofile',
            name='registration_certificate',
            field=models.FileField(blank=True, null=True, upload_to='doctor_certificates/'),
        ),
        migrations.AddField(
            model_name='doctorprofile',
            name='registration_certificate_url',
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='doctorprofile',
            name='registration_council',
            field=models.CharField(blank=True, help_text='State Medical Council / Licensing Body (e.g. Maharashtra Medical Council)', max_length=255),
        ),
        migrations.AddField(
            model_name='doctorprofile',
            name='registration_year',
            field=models.PositiveSmallIntegerField(blank=True, help_text='Year of Medical Registration', null=True),
        ),
        migrations.AddField(
            model_name='doctorprofile',
            name='title',
            field=models.CharField(blank=True, default='Dr.', max_length=20),
        ),
        migrations.AddField(
            model_name='practice',
            name='about',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='practice',
            name='clinic_type',
            field=models.CharField(blank=True, choices=[('solo_clinic', 'Solo Clinic / Private Practice'), ('polyclinic', 'Polyclinic / Multispeciality Clinic'), ('dental_clinic', 'Dental Clinic'), ('hospital_opd', 'Hospital OPD / Branch'), ('diagnostic_center', 'Diagnostic & Wellness Center'), ('telehealth', 'Virtual / Teleconsultation Only')], default='solo_clinic', max_length=50),
        ),
        migrations.AddField(
            model_name='practice',
            name='established_year',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='practice',
            name='gst_number',
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name='practice',
            name='landmark',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='practice',
            name='logo_image',
            field=models.ImageField(blank=True, null=True, upload_to='practice_logos/'),
        ),
        migrations.AddField(
            model_name='practice',
            name='tagline',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.CreateModel(
            name='DoctorOnboarding',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('current_step', models.CharField(choices=[('doctor_profile', 'Doctor Profile & Registration Number'), ('clinic_details', 'Clinic & Practice Details'), ('services', 'Clinical Services & Consultation Fees'), ('timings', 'Clinic Timings & Working Hours'), ('images', 'Clinic Photos & Verification Documents'), ('review', 'Review & Finalize'), ('completed', 'Onboarding Completed')], default='doctor_profile', max_length=30)),
                ('completed_steps', models.JSONField(blank=True, default=list)),
                ('draft_data', models.JSONField(blank=True, default=dict)),
                ('is_completed', models.BooleanField(default=False)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('practice', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='doctor_onboardings', to='practices.practice')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='doctor_onboarding', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Doctor Onboarding',
                'verbose_name_plural': 'Doctor Onboardings',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='DoctorSchedule',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('day_of_week', models.PositiveSmallIntegerField(choices=[(0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')], help_text='Day of the week (0=Monday, 6=Sunday)')),
                ('session_name', models.CharField(default='General OPD', help_text='e.g. Morning Shift, Evening OPD', max_length=100)),
                ('start_time', models.TimeField(help_text='Shift start time, e.g. 09:00')),
                ('end_time', models.TimeField(help_text='Shift end time, e.g. 13:00')),
                ('slot_duration_minutes', models.PositiveSmallIntegerField(default=15, help_text='Duration per appointment slot in minutes')),
                ('is_active', models.BooleanField(default=True)),
                ('doctor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='schedules', to='practices.doctorprofile')),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_records', to='practices.practice')),
            ],
            options={
                'verbose_name': 'Doctor Schedule',
                'verbose_name_plural': 'Doctor Schedules',
                'ordering': ['day_of_week', 'start_time'],
            },
        ),
        migrations.CreateModel(
            name='PracticeImage',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('image', models.ImageField(blank=True, null=True, upload_to='practice_images/')),
                ('image_url', models.URLField(blank=True, help_text='Direct URL to hosted image', max_length=500, null=True)),
                ('image_type', models.CharField(choices=[('clinic_facade', 'Clinic Exterior / Facade'), ('reception', 'Reception / Frontdesk'), ('consultation_room', 'Doctor Consultation Room'), ('waiting_area', 'Patient Waiting Area'), ('equipment', 'Medical Equipment / OT'), ('certificate', 'License / Certificate'), ('logo', 'Clinic Logo'), ('other', 'Other Photo')], default='other', max_length=50)),
                ('caption', models.CharField(blank=True, max_length=255)),
                ('is_primary', models.BooleanField(default=False)),
                ('order', models.PositiveIntegerField(default=0)),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_records', to='practices.practice')),
            ],
            options={
                'verbose_name': 'Practice Image',
                'verbose_name_plural': 'Practice Images',
                'ordering': ['order', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='PracticeService',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(help_text='Service name, e.g. General OPD Consultation', max_length=255)),
                ('category', models.CharField(choices=[('consultation', 'Consultation'), ('follow_up', 'Follow-up Visit'), ('procedure', 'Clinical Procedure'), ('diagnostic', 'Diagnostic / Investigation'), ('surgery', 'Minor / Day Surgery'), ('teleconsultation', 'Video / Online Consultation'), ('other', 'Other Healthcare Service')], default='consultation', max_length=50)),
                ('description', models.TextField(blank=True, help_text='Service description or instructions for patients')),
                ('duration_minutes', models.PositiveSmallIntegerField(default=15, help_text='Expected consultation/procedure duration in minutes')),
                ('price', models.DecimalField(decimal_places=2, default=0.0, help_text='Fee in practice currency', max_digits=10)),
                ('is_active', models.BooleanField(default=True)),
                ('is_teleconsultation', models.BooleanField(default=False)),
                ('doctor', models.ForeignKey(blank=True, help_text='Optional doctor offering this service. If null, service is practice-wide.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='services', to='practices.doctorprofile')),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_records', to='practices.practice')),
            ],
            options={
                'verbose_name': 'Practice Service',
                'verbose_name_plural': 'Practice Services',
                'ordering': ['name'],
            },
        ),
    ]

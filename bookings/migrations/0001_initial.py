import bookings.models
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('leads', '0001_initial'),
        ('practices', '0002_doctor_onboarding'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PracticeLocation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(help_text='Branch or facility name, e.g. Jubilee Hills Main Clinic', max_length=255)),
                ('code', models.CharField(blank=True, help_text='Short identifier code, e.g. JH-01', max_length=30)),
                ('address', models.TextField(blank=True)),
                ('landmark', models.CharField(blank=True, max_length=255)),
                ('city', models.CharField(blank=True, max_length=100)),
                ('state', models.CharField(blank=True, max_length=100)),
                ('postal_code', models.CharField(blank=True, max_length=20)),
                ('country', models.CharField(default='India', max_length=100)),
                ('phone_number', models.CharField(blank=True, max_length=30)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('google_maps_url', models.URLField(blank=True, max_length=500, null=True)),
                ('is_telehealth_default', models.BooleanField(default=False, help_text='Designates this location for remote/video teleconsultations')),
                ('is_primary', models.BooleanField(default=False, help_text='Primary headquarters or main clinic branch')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bookings_practicelocation_records', to='practices.practice')),
            ],
            options={
                'verbose_name': 'Practice Location',
                'verbose_name_plural': 'Practice Locations',
                'ordering': ['-is_primary', 'name'],
            },
        ),
        migrations.CreateModel(
            name='DoctorSessionCapacity',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('session_name', models.CharField(default='General OPD', help_text='e.g. Morning OPD, Evening Shift', max_length=100)),
                ('booking_mode', models.CharField(choices=[('slot', 'Exact Time Slot Mode'), ('token', 'Session / Token Mode')], default='slot', max_length=20)),
                ('max_tokens_per_session', models.PositiveIntegerField(default=25, help_text='Maximum number of patient tokens allowed for this OPD session')),
                ('slot_duration_minutes', models.PositiveSmallIntegerField(default=15, help_text='Consultation slot duration in minutes (for time-slot mode)')),
                ('auto_confirm', models.BooleanField(default=False, help_text='Automatically confirm booking request if capacity check passes')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('doctor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='session_capacities', to='practices.doctorprofile')),
                ('location', models.ForeignKey(blank=True, help_text='Optional specific location for this session', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='session_capacities', to='bookings.practicelocation')),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bookings_doctorsessioncapacity_records', to='practices.practice')),
            ],
            options={
                'verbose_name': 'Doctor Session Capacity',
                'verbose_name_plural': 'Doctor Session Capacities',
                'unique_together': {('practice', 'doctor', 'session_name')},
            },
        ),
        migrations.CreateModel(
            name='BookingRequest',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('booking_reference', models.CharField(db_index=True, default=bookings.models.generate_booking_reference, help_text='Public patient tracking reference, e.g. CR-202610-8F9A', max_length=30, unique=True)),
                ('patient_name', models.CharField(help_text='Full patient name', max_length=200)),
                ('phone_number', models.CharField(db_index=True, help_text='Patient contact phone number', max_length=30)),
                ('email', models.EmailField(blank=True, help_text='Patient email address for confirmation notices', max_length=254)),
                ('gender', models.CharField(blank=True, choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')], max_length=20)),
                ('age', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('date_of_birth', models.DateField(blank=True, null=True)),
                ('patient_type', models.CharField(choices=[('new', 'New Patient'), ('returning', 'Returning Patient')], default='new', max_length=20)),
                ('consultation_mode', models.CharField(choices=[('in_person', 'In-Person Clinic Visit'), ('video', 'Video Teleconsultation'), ('phone', 'Phone Consultation'), ('home_visit', 'Home Healthcare Visit')], default='in_person', max_length=30)),
                ('preferred_date', models.DateField(help_text='Patient requested date')),
                ('preferred_time_window', models.CharField(choices=[('morning', 'Morning (9:00 AM - 12:00 PM)'), ('afternoon', 'Afternoon (12:00 PM - 4:00 PM)'), ('evening', 'Evening (4:00 PM - 8:00 PM)'), ('any', 'Any Available Time')], default='any', max_length=50)),
                ('chief_complaint', models.TextField(blank=True, help_text='Patient medical issue, symptoms, or reason for visit')),
                ('patient_notes', models.TextField(blank=True, help_text='Special requests, wheelchair assistance, etc.')),
                ('booking_mode', models.CharField(choices=[('slot', 'Exact Time Slot'), ('token', 'Session / Token Mode')], db_index=True, default='slot', max_length=20)),
                ('appointment_date', models.DateField(blank=True, db_index=True, help_text='Confirmed date of consultation', null=True)),
                ('session_name', models.CharField(blank=True, help_text='OPD Session name in Token mode (e.g. Morning OPD, Evening Shift)', max_length=100)),
                ('token_number', models.PositiveIntegerField(blank=True, db_index=True, help_text='Sequential queue token number assigned to patient', null=True)),
                ('start_time', models.TimeField(blank=True, help_text='Start time in Slot mode', null=True)),
                ('end_time', models.TimeField(blank=True, help_text='End time in Slot mode', null=True)),
                ('estimated_arrival_time', models.TimeField(blank=True, help_text='Estimated arrival or consult window', null=True)),
                ('status', models.CharField(choices=[('requested', 'Pending Clinic Confirmation'), ('confirmed', 'Confirmed'), ('rescheduled', 'Rescheduled'), ('checked_in', 'Checked In / Waiting Area'), ('in_consultation', 'In Consultation Room'), ('completed', 'Consultation Completed'), ('cancelled', 'Cancelled'), ('rejected', 'Declined / Rejected by Clinic'), ('no_show', 'Patient No Show')], db_index=True, default='requested', max_length=30)),
                ('confirmed_at', models.DateTimeField(blank=True, null=True)),
                ('rejection_reason', models.TextField(blank=True)),
                ('cancellation_reason', models.TextField(blank=True)),
                ('cancelled_at', models.DateTimeField(blank=True, null=True)),
                ('clinic_notes', models.TextField(blank=True, help_text='Internal staff remarks and instructions')),
                ('source', models.CharField(choices=[('website', 'Clinic Website'), ('patient_portal', 'Patient Portal'), ('frontdesk', 'Frontdesk / Reception'), ('phone', 'Phone Call'), ('doctor_referral', 'Doctor Referral')], default='website', max_length=30)),
                ('consent_given', models.BooleanField(default=True)),
                ('consent_timestamp', models.DateTimeField(default=django.utils.timezone.now)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('confirmed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='confirmed_bookings', to=settings.AUTH_USER_MODEL)),
                ('doctor', models.ForeignKey(blank=True, help_text='Assigned practitioner', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bookings', to='practices.doctorprofile')),
                ('lead', models.ForeignKey(blank=True, help_text='Associated inquiry/lead record if converted', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bookings', to='leads.lead')),
                ('location', models.ForeignKey(blank=True, help_text='Clinical branch or facility', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bookings', to='bookings.practicelocation')),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bookings_bookingrequest_records', to='practices.practice')),
                ('service', models.ForeignKey(blank=True, help_text='Requested medical treatment or consultation service', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bookings', to='practices.practiceservice')),
            ],
            options={
                'verbose_name': 'Booking Request',
                'verbose_name_plural': 'Booking Requests',
                'ordering': ['-appointment_date', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='BookingTimeline',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('action', models.CharField(help_text='e.g. requested, confirmed, rescheduled, cancelled, checked_in', max_length=40)),
                ('note', models.TextField(blank=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('booking', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='timeline', to='bookings.bookingrequest')),
                ('performed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='booking_timeline_actions', to=settings.AUTH_USER_MODEL)),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bookings_bookingtimeline_records', to='practices.practice')),
            ],
            options={
                'verbose_name': 'Booking Timeline',
                'verbose_name_plural': 'Booking Timelines',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='practicelocation',
            index=models.Index(fields=['practice', 'is_active'], name='bookings_pr_practic_8b9195_idx'),
        ),
        migrations.AddIndex(
            model_name='practicelocation',
            index=models.Index(fields=['practice', 'is_primary'], name='bookings_pr_practic_4c86ec_idx'),
        ),
        migrations.AddIndex(
            model_name='bookingrequest',
            index=models.Index(fields=['practice', 'status'], name='bookings_bo_practic_d92e59_idx'),
        ),
        migrations.AddIndex(
            model_name='bookingrequest',
            index=models.Index(fields=['practice', 'appointment_date'], name='bookings_bo_practic_3c2d4b_idx'),
        ),
        migrations.AddIndex(
            model_name='bookingrequest',
            index=models.Index(fields=['practice', 'doctor', 'appointment_date'], name='bookings_bo_practic_944a95_idx'),
        ),
        migrations.AddIndex(
            model_name='bookingrequest',
            index=models.Index(fields=['practice', 'booking_mode', 'appointment_date'], name='bookings_bo_practic_c824c4_idx'),
        ),
    ]

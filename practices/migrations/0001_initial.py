from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('authentication', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Practice',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(help_text='Clinic or Practice Name', max_length=255)),
                ('slug', models.SlugField(blank=True, max_length=255, unique=True)),
                ('phone_number', models.CharField(blank=True, max_length=20)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('website', models.URLField(blank=True, null=True)),
                ('logo_url', models.URLField(blank=True, max_length=500, null=True)),
                ('address', models.TextField(blank=True)),
                ('city', models.CharField(blank=True, max_length=100)),
                ('state', models.CharField(blank=True, max_length=100)),
                ('postal_code', models.CharField(blank=True, max_length=20)),
                ('country', models.CharField(default='India', max_length=100)),
                ('currency', models.CharField(default='INR', max_length=10)),
                ('timezone', models.CharField(default='Asia/Kolkata', max_length=50)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('owner', models.ForeignKey(help_text='User who owns the practice account', on_delete=django.db.models.deletion.PROTECT, related_name='owned_practices', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Practice',
                'verbose_name_plural': 'Practices',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='DoctorProfile',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('medical_license_number', models.CharField(db_index=True, help_text='State Medical Council / National Registration Number', max_length=100, unique=True)),
                ('specialization', models.CharField(help_text='e.g. General Physician, Dentist, Cardiologist, Pediatrician', max_length=150)),
                ('qualifications', models.CharField(help_text='e.g. MBBS, MD, BDS, MDS, MS', max_length=255)),
                ('experience_years', models.PositiveSmallIntegerField(default=0, help_text='Years of clinical practice experience')),
                ('bio', models.TextField(blank=True, help_text='Short professional summary / bio')),
                ('default_consultation_fee', models.DecimalField(decimal_places=2, default=0.0, help_text='Default consultation fee in practice currency', max_digits=10)),
                ('is_verified', models.BooleanField(default=False, help_text='Designates whether the doctor license has been verified by platform admins')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='doctor_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Doctor Profile',
                'verbose_name_plural': 'Doctor Profiles',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='PracticeInvitation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('email', models.EmailField(blank=True, max_length=254, null=True)),
                ('phone_number', models.CharField(blank=True, max_length=20, null=True)),
                ('role', models.CharField(choices=[('owner', 'Practice Owner'), ('admin', 'Practice Admin'), ('doctor', 'Doctor / Practitioner'), ('staff', 'Frontdesk / Staff')], default='doctor', max_length=20)),
                ('invite_code', models.CharField(db_index=True, max_length=64, unique=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected'), ('revoked', 'Revoked')], default='pending', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('invited_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sent_invitations', to=settings.AUTH_USER_MODEL)),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='invitations', to='practices.practice')),
            ],
            options={
                'verbose_name': 'Practice Invitation',
                'verbose_name_plural': 'Practice Invitations',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='PracticeMembership',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('role', models.CharField(choices=[('owner', 'Practice Owner'), ('admin', 'Practice Admin'), ('doctor', 'Doctor / Practitioner'), ('staff', 'Frontdesk / Staff')], default='staff', max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memberships', to='practices.practice')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='practice_memberships', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Practice Membership',
                'verbose_name_plural': 'Practice Memberships',
                'ordering': ['-joined_at'],
                'unique_together': {('practice', 'user')},
            },
        ),
    ]

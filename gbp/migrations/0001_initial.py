from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('practices', '0002_doctor_onboarding'),
    ]

    operations = [
        migrations.CreateModel(
            name='GBPProfileChecklist',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('google_maps_url', models.URLField(blank=True, help_text='Public Google Maps listing URL', max_length=500)),
                ('google_maps_place_id', models.CharField(blank=True, help_text='Google Place ID (e.g. ChIJN1t_tDeuEmsRUsoyG83frY4)', max_length=150)),
                ('google_review_link', models.URLField(blank=True, help_text='Direct patient write-review shortcut link', max_length=500)),
                ('verification_status', models.CharField(choices=[('unverified', 'Not Verified / Setup Incomplete'), ('pending', 'Pending Google Verification (Video / Phone / Postcard)'), ('verified', 'Verified & Active on Google Maps'), ('suspended', 'Suspended / Reinstatement Required')], db_index=True, default='unverified', max_length=30)),
                ('primary_category', models.CharField(blank=True, help_text='Primary Google Business healthcare category', max_length=150)),
                ('secondary_categories', models.JSONField(blank=True, default=list, help_text='List of secondary category strings')),
                ('custom_description', models.TextField(blank=True, help_text='Customized business description if edited by practice team')),
                ('has_wheelchair_accessible_entrance', models.BooleanField(default=True)),
                ('has_wheelchair_accessible_restroom', models.BooleanField(default=True)),
                ('requires_appointments', models.BooleanField(default=True)),
                ('accepts_upi_payments', models.BooleanField(default=True)),
                ('accepts_credit_cards', models.BooleanField(default=True)),
                ('manual_completed_items', models.JSONField(blank=True, default=list, help_text='Keys of checklist items manually verified by practice staff')),
                ('notes', models.TextField(blank=True, help_text='Internal staff notes regarding GBP setup and verification')),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_records', to='practices.practice')),
            ],
            options={
                'verbose_name': 'GBP Profile & Checklist',
                'verbose_name_plural': 'GBP Profiles & Checklists',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['practice', 'verification_status'], name='gbp_gbpprof_practic_4e8a2b_idx'),
                ],
            },
        ),
    ]

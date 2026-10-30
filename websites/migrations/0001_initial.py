from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('practices', '0002_doctor_onboarding'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ClinicWebsite',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(help_text='Public site title (e.g. City Dental Care)', max_length=255)),
                ('tagline', models.CharField(blank=True, help_text='Short subtitle or value proposition', max_length=255)),
                ('subdomain', models.SlugField(help_text="Subdomain for free hosting (e.g. 'citydental' -> citydental.clinicrise.com)", max_length=100, unique=True)),
                ('template_style', models.CharField(choices=[('modern_minimal', 'Modern Minimalist (Sleek, Typography-focused)'), ('clinical_clean', 'Clinical Clean (Hospital & General OPD)'), ('pediatric_warm', 'Pediatric Warm (Friendly, Playful Accents)'), ('dental_bright', 'Dental Bright (Vibrant, Smile-oriented)'), ('luxury_wellness', 'Luxury Wellness & Aesthetic (High-end, Soft Tones)'), ('dark_premium', 'Dark Mode Premium (Bold, High Contrast)')], default='modern_minimal', max_length=50)),
                ('primary_color', models.CharField(default='#0D9488', help_text='Hex brand color (e.g. #0D9488)', max_length=20)),
                ('secondary_color', models.CharField(default='#0F172A', help_text='Hex accent color (e.g. #0F172A)', max_length=20)),
                ('font_family', models.CharField(default='Inter', help_text='Google Font family name (e.g. Inter, Outfit, Plus Jakarta Sans)', max_length=50)),
                ('logo_url', models.URLField(blank=True, max_length=500, null=True)),
                ('favicon_url', models.URLField(blank=True, max_length=500, null=True)),
                ('header_cta_text', models.CharField(default='Book Appointment', max_length=50)),
                ('header_cta_link', models.CharField(default='#appointment', max_length=255)),
                ('footer_text', models.CharField(blank=True, max_length=255)),
                ('contact_phone', models.CharField(blank=True, max_length=30)),
                ('contact_email', models.EmailField(blank=True, max_length=254)),
                ('whatsapp_number', models.CharField(blank=True, help_text='With country code for direct chat', max_length=30)),
                ('emergency_contact', models.CharField(blank=True, max_length=30)),
                ('google_maps_url', models.URLField(blank=True, max_length=500, null=True)),
                ('facebook_url', models.URLField(blank=True, null=True)),
                ('instagram_url', models.URLField(blank=True, null=True)),
                ('linkedin_url', models.URLField(blank=True, null=True)),
                ('meta_title', models.CharField(blank=True, max_length=255)),
                ('meta_description', models.TextField(blank=True)),
                ('meta_keywords', models.CharField(blank=True, max_length=255)),
                ('og_image_url', models.URLField(blank=True, max_length=500, null=True)),
                ('google_analytics_id', models.CharField(blank=True, max_length=50)),
                ('is_published', models.BooleanField(default=False)),
                ('is_maintenance', models.BooleanField(default=False, help_text='Show maintenance under-construction notice to public visitors')),
                ('has_unpublished_changes', models.BooleanField(default=True)),
                ('published_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('practice', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='clinic_website', to='practices.practice')),
            ],
            options={
                'verbose_name': 'Clinic Website',
                'verbose_name_plural': 'Clinic Websites',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='CustomDomain',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('domain', models.CharField(db_index=True, help_text='Custom domain, e.g. www.cityhealthclinic.com or drrajesh.com', max_length=255, unique=True)),
                ('is_primary', models.BooleanField(default=False)),
                ('status', models.CharField(choices=[('pending_verification', 'Pending DNS Verification'), ('verified', 'DNS Verified (Provisioning SSL)'), ('active', 'Active & Secured (Live)'), ('failed', 'Verification Failed')], default='pending_verification', max_length=30)),
                ('ssl_status', models.CharField(choices=[('pending', 'Pending SSL Certificate'), ('issued', 'SSL Active (HTTPS Secured)'), ('failed', 'SSL Certificate Error')], default='pending', max_length=30)),
                ('verification_token', models.CharField(editable=False, max_length=64)),
                ('cname_target', models.CharField(default='sites.clinicrise.com', max_length=100)),
                ('last_verified_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('website', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='custom_domains', to='websites.clinicwebsite')),
            ],
            options={
                'verbose_name': 'Custom Domain',
                'verbose_name_plural': 'Custom Domains',
                'ordering': ['-is_primary', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='WebsiteInquiry',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('patient_name', models.CharField(max_length=150)),
                ('phone_number', models.CharField(max_length=20)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('preferred_service', models.CharField(blank=True, max_length=255)),
                ('preferred_date', models.DateField(blank=True, null=True)),
                ('message', models.TextField(blank=True)),
                ('is_read', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('website', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='inquiries', to='websites.clinicwebsite')),
            ],
            options={
                'verbose_name': 'Website Inquiry',
                'verbose_name_plural': 'Website Inquiries',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='WebsitePage',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(help_text='Page title, e.g. Home, About Us, Treatments', max_length=200)),
                ('slug', models.SlugField(help_text="URL slug (e.g. 'home', 'about', 'services')", max_length=200)),
                ('is_homepage', models.BooleanField(default=False)),
                ('page_type', models.CharField(choices=[('home', 'Home Page'), ('about', 'About Clinic & Doctors'), ('services', 'Treatments & Services'), ('doctors', 'Our Medical Team'), ('testimonials', 'Patient Reviews & Testimonials'), ('contact', 'Contact & Clinic Hours'), ('custom', 'Custom Content Page'), ('policy', 'Terms & Privacy Policy')], default='custom', max_length=30)),
                ('is_in_navigation', models.BooleanField(default=True)),
                ('is_in_footer', models.BooleanField(default=True)),
                ('nav_order', models.PositiveSmallIntegerField(default=0)),
                ('meta_title', models.CharField(blank=True, max_length=255)),
                ('meta_description', models.TextField(blank=True)),
                ('draft_content', models.JSONField(blank=True, default=dict, help_text='Active editing payload containing modular page sections')),
                ('published_content', models.JSONField(blank=True, default=dict, help_text='Currently live published snapshot visible to visitors')),
                ('is_published', models.BooleanField(default=False)),
                ('has_unpublished_changes', models.BooleanField(default=True)),
                ('published_version', models.PositiveIntegerField(default=0)),
                ('published_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('website', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pages', to='websites.clinicwebsite')),
            ],
            options={
                'verbose_name': 'Website Page',
                'verbose_name_plural': 'Website Pages',
                'ordering': ['nav_order', 'created_at'],
                'unique_together': {('website', 'slug')},
            },
        ),
        migrations.CreateModel(
            name='WebsitePageRevision',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('version', models.PositiveIntegerField()),
                ('content', models.JSONField()),
                ('published_at', models.DateTimeField(auto_now_add=True)),
                ('page', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='revisions', to='websites.websitepage')),
                ('published_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Page Revision',
                'verbose_name_plural': 'Page Revisions',
                'ordering': ['-version'],
                'unique_together': {('page', 'version')},
            },
        ),
    ]

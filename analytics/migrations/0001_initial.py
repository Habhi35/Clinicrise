from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('practices', '0002_doctor_onboarding'),
        ('websites', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='WebsiteVisit',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('visitor_id', models.CharField(blank=True, db_index=True, help_text='Anonymous visitor session/cookie identifier', max_length=100)),
                ('session_id', models.CharField(blank=True, help_text='Browser session token', max_length=100)),
                ('page_url', models.TextField(help_text='Full URL of the visited page')),
                ('page_path', models.CharField(blank=True, db_index=True, help_text='Normalized URL path (e.g. /services)', max_length=255)),
                ('page_title', models.CharField(blank=True, help_text='Title tag of the page', max_length=255)),
                ('referrer', models.TextField(blank=True, help_text='HTTP Referrer URL')),
                ('referrer_domain', models.CharField(blank=True, db_index=True, help_text='Host/domain from referrer', max_length=255)),
                ('traffic_channel', models.CharField(choices=[('organic_search', 'Organic Search (Google, Bing, Yahoo)'), ('direct', 'Direct / Typed URL'), ('social', 'Social Media (Instagram, Facebook, LinkedIn, YouTube)'), ('paid_ad', 'Paid Ads / Search Ads / PPC'), ('whatsapp', 'WhatsApp Links & Chats'), ('referral', 'Referral (External Websites)'), ('email', 'Email Newsletter & Links'), ('campaign', 'Custom Ad Campaign')], db_index=True, default='direct', max_length=50)),
                ('traffic_source', models.CharField(blank=True, db_index=True, help_text='Recognized source (e.g. Google, Instagram, WhatsApp, Direct)', max_length=100)),
                ('utm_source', models.CharField(blank=True, db_index=True, max_length=100)),
                ('utm_medium', models.CharField(blank=True, max_length=100)),
                ('utm_campaign', models.CharField(blank=True, db_index=True, max_length=150)),
                ('utm_term', models.CharField(blank=True, max_length=150)),
                ('utm_content', models.CharField(blank=True, max_length=150)),
                ('device_type', models.CharField(choices=[('mobile', 'Mobile Smartphone'), ('desktop', 'Desktop / Laptop'), ('tablet', 'Tablet'), ('unknown', 'Unknown Device')], default='desktop', max_length=30)),
                ('browser', models.CharField(blank=True, max_length=50)),
                ('os', models.CharField(blank=True, max_length=50)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True)),
                ('is_unique_daily', models.BooleanField(default=True, help_text='True if this is the first pageview from this visitor_id on this day')),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_records', to='practices.practice')),
                ('website', models.ForeignKey(blank=True, help_text='Clinic website being browsed', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='visits', to='websites.clinicwebsite')),
            ],
            options={
                'verbose_name': 'Website Visit',
                'verbose_name_plural': 'Website Visits',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['practice', 'created_at'], name='analytics_w_practic_2a0b12_idx'),
                    models.Index(fields=['practice', 'traffic_channel'], name='analytics_w_practic_4c5d6e_idx'),
                    models.Index(fields=['practice', 'traffic_source'], name='analytics_w_practic_7f8a9b_idx'),
                    models.Index(fields=['practice', 'visitor_id'], name='analytics_w_practic_0c1d2e_idx'),
                    models.Index(fields=['website', 'created_at'], name='analytics_w_website_3e4f5a_idx'),
                ],
            },
        ),
    ]

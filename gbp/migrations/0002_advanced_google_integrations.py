from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('gbp', '0001_initial'),
        ('practices', '0002_doctor_onboarding'),
    ]

    operations = [
        migrations.CreateModel(
            name='GBPConnection',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('google_account_email', models.EmailField(blank=True, help_text='Google Business Profile owner/manager email', max_length=254)),
                ('account_id', models.CharField(blank=True, help_text='e.g. accounts/10982347102', max_length=150)),
                ('location_id', models.CharField(blank=True, help_text='e.g. locations/89234710238', max_length=150)),
                ('api_key', models.CharField(blank=True, max_length=255)),
                ('access_token', models.TextField(blank=True)),
                ('refresh_token', models.TextField(blank=True)),
                ('token_expires_at', models.DateTimeField(blank=True, null=True)),
                ('is_connected', models.BooleanField(default=True)),
                ('sync_status', models.CharField(choices=[('idle', 'Idle'), ('syncing', 'Sync in Progress'), ('success', 'Connected & Synced'), ('error', 'Sync Error / Reauthorization Needed')], default='success', max_length=30)),
                ('last_synced_at', models.DateTimeField(blank=True, null=True)),
                ('last_sync_error', models.TextField(blank=True)),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gbp_gbpconnection_records', to='practices.practice')),
            ],
            options={
                'verbose_name': 'GBP API Connection',
                'verbose_name_plural': 'GBP API Connections',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='GoogleReview',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('review_id', models.CharField(db_index=True, max_length=200, unique=True)),
                ('reviewer_name', models.CharField(max_length=200)),
                ('reviewer_photo_url', models.URLField(blank=True, max_length=500)),
                ('star_rating', models.PositiveSmallIntegerField(default=5, help_text='1 to 5 stars')),
                ('comment', models.TextField(blank=True)),
                ('review_timestamp', models.DateTimeField()),
                ('reply_text', models.TextField(blank=True)),
                ('replied_at', models.DateTimeField(blank=True, null=True)),
                ('is_replied', models.BooleanField(db_index=True, default=False)),
                ('ai_suggested_reply', models.TextField(blank=True, help_text='AI suggested response draft compliant with healthcare privacy')),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gbp_googlereview_records', to='practices.practice')),
            ],
            options={
                'verbose_name': 'Google Review',
                'verbose_name_plural': 'Google Reviews',
                'ordering': ['-review_timestamp'],
            },
        ),
        migrations.CreateModel(
            name='GBPPost',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('post_type', models.CharField(choices=[('update', "What's New / Clinical Update"), ('offer', 'Special Treatment Offer'), ('event', 'Health Camp / Clinic Event')], default='update', max_length=20)),
                ('summary', models.TextField(help_text='Post body text / health tip / announcement')),
                ('cta_type', models.CharField(choices=[('BOOK', 'Book Appointment'), ('CALL', 'Call Now'), ('LEARN_MORE', 'Learn More'), ('SIGN_UP', 'Sign Up'), ('NONE', 'No Button')], default='BOOK', max_length=20)),
                ('cta_url', models.URLField(blank=True, max_length=500)),
                ('image_url', models.URLField(blank=True, max_length=500)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('published', 'Published on Google Maps'), ('scheduled', 'Scheduled')], default='published', max_length=20)),
                ('published_at', models.DateTimeField(blank=True, null=True)),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gbp_gbppost_records', to='practices.practice')),
            ],
            options={
                'verbose_name': 'GBP Post',
                'verbose_name_plural': 'GBP Posts',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='GBPInsight',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('date', models.DateField(db_index=True)),
                ('search_impressions_direct', models.PositiveIntegerField(default=0, help_text='Searched clinic name directly')),
                ('search_impressions_discovery', models.PositiveIntegerField(default=0, help_text="Searched category e.g. 'dentist near me'")),
                ('search_impressions_branded', models.PositiveIntegerField(default=0, help_text='Searched related brand')),
                ('maps_impressions', models.PositiveIntegerField(default=0, help_text='Views on Google Maps')),
                ('search_impressions', models.PositiveIntegerField(default=0, help_text='Views on Google Search')),
                ('website_clicks', models.PositiveIntegerField(default=0, help_text='Clicks to clinic website')),
                ('call_clicks', models.PositiveIntegerField(default=0, help_text='Direct phone call clicks from Google profile')),
                ('direction_requests', models.PositiveIntegerField(default=0, help_text='Driving / transit directions requested')),
                ('bookings_clicks', models.PositiveIntegerField(default=0, help_text='Clicks on appointment booking button')),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gbp_gbpinsight_records', to='practices.practice')),
            ],
            options={
                'verbose_name': 'GBP Insight',
                'verbose_name_plural': 'GBP Insights',
                'ordering': ['-date'],
                'unique_together': {('practice', 'date')},
            },
        ),
        migrations.CreateModel(
            name='SearchConsoleQuery',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('query', models.CharField(db_index=True, help_text="Medical search query, e.g. 'root canal cost indiranagar'", max_length=255)),
                ('page', models.CharField(blank=True, help_text='Landing page URL path', max_length=500)),
                ('clicks', models.PositiveIntegerField(default=0)),
                ('impressions', models.PositiveIntegerField(default=0)),
                ('ctr', models.DecimalField(decimal_places=4, default=0.0, help_text='Click-through rate (e.g. 0.0540 = 5.4%)', max_digits=5)),
                ('position', models.DecimalField(decimal_places=2, default=0.0, help_text='Average organic position (e.g. 2.4)', max_digits=5)),
                ('date', models.DateField(db_index=True)),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gbp_searchconsolequery_records', to='practices.practice')),
            ],
            options={
                'verbose_name': 'Search Console Query',
                'verbose_name_plural': 'Search Console Queries',
                'ordering': ['-clicks', '-impressions'],
            },
        ),
        migrations.CreateModel(
            name='LocalRankKeyword',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('keyword', models.CharField(db_index=True, help_text="e.g. 'dentist near me', 'dental implants bengaluru'", max_length=200)),
                ('target_city', models.CharField(default='Bengaluru', max_length=100)),
                ('target_radius_km', models.PositiveSmallIntegerField(default=10)),
                ('current_pack_rank', models.PositiveSmallIntegerField(blank=True, help_text='1, 2, 3 in local 3-pack, or null if outside top 20', null=True)),
                ('previous_pack_rank', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('organic_rank', models.PositiveSmallIntegerField(blank=True, help_text='Organic SERP rank position', null=True)),
                ('is_in_local_three_pack', models.BooleanField(db_index=True, default=False)),
                ('last_checked_at', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gbp_localrankkeyword_records', to='practices.practice')),
            ],
            options={
                'verbose_name': 'Local Rank Keyword',
                'verbose_name_plural': 'Local Rank Keywords',
                'ordering': ['current_pack_rank', 'keyword'],
                'unique_together': {('practice', 'keyword')},
            },
        ),
        migrations.CreateModel(
            name='LocalRankSnapshot',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('check_date', models.DateField(db_index=True)),
                ('pack_rank_position', models.PositiveSmallIntegerField(blank=True, help_text='1 to 20 (1-3 = Local 3-Pack)', null=True)),
                ('in_three_pack', models.BooleanField(default=False)),
                ('organic_rank_position', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('competitors_in_pack', models.JSONField(blank=True, default=list, help_text='Names of top 3 clinics occupying the local pack')),
                ('rank_change', models.IntegerField(default=0, help_text='Position change (+2 means jumped up 2 spots, -1 dropped)')),
                ('keyword', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='snapshots', to='gbp.localrankkeyword')),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gbp_localranksnapshot_records', to='practices.practice')),
            ],
            options={
                'verbose_name': 'Local Rank Snapshot',
                'verbose_name_plural': 'Local Rank Snapshots',
                'ordering': ['-check_date'],
            },
        ),
        migrations.AddIndex(
            model_name='googlereview',
            index=models.Index(fields=['practice', 'star_rating'], name='gbp_googler_practic_fa9131_idx'),
        ),
        migrations.AddIndex(
            model_name='googlereview',
            index=models.Index(fields=['practice', 'is_replied'], name='gbp_googler_practic_b59931_idx'),
        ),
        migrations.AddIndex(
            model_name='gbpinsight',
            index=models.Index(fields=['practice', 'date'], name='gbp_gbpinsi_practic_ea0121_idx'),
        ),
        migrations.AddIndex(
            model_name='searchconsolequery',
            index=models.Index(fields=['practice', 'date'], name='gbp_searchc_practic_cd0121_idx'),
        ),
        migrations.AddIndex(
            model_name='searchconsolequery',
            index=models.Index(fields=['practice', 'query'], name='gbp_searchc_practic_838121_idx'),
        ),
        migrations.AddIndex(
            model_name='localranksnapshot',
            index=models.Index(fields=['keyword', 'check_date'], name='gbp_localra_keyword_410121_idx'),
        ),
    ]

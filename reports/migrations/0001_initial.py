import django.db.models.deletion
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('practices', '0003_add_receptionist_assistant_roles'),
    ]

    operations = [
        migrations.CreateModel(
            name='MonthlyGrowthReport',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('year', models.PositiveSmallIntegerField(db_index=True, default=2026)),
                ('month', models.PositiveSmallIntegerField(db_index=True, default=10, help_text='Month number 1 to 12')),
                ('title', models.CharField(max_length=255)),
                ('period_start', models.DateField()),
                ('period_end', models.DateField()),
                ('patient_metrics', models.JSONField(blank=True, default=dict, help_text='Consultations, new patients, online vs walk-ins, attendance rate')),
                ('gbp_metrics', models.JSONField(blank=True, default=dict, help_text='Search views, map views, calls, directions, website clicks, reviews gained')),
                ('gsc_metrics', models.JSONField(blank=True, default=dict, help_text='Organic clicks, impressions, CTR, average position, top search queries')),
                ('rank_metrics', models.JSONField(blank=True, default=dict, help_text='Keywords in Top 3 local pack, keywords in Top 10, average rank')),
                ('executive_summary', models.TextField(blank=True, help_text='Doctor-focused executive performance summary')),
                ('recommendations', models.JSONField(blank=True, default=list, help_text='List of prioritized growth recommendations')),
                ('status', models.CharField(choices=[('generated', 'Generated / Internal Review'), ('published', 'Published / Shared with Doctor')], default='generated', max_length=20)),
                ('generated_at', models.DateTimeField(auto_now_add=True)),
                ('practice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reports_monthlygrowthreport_records', to='practices.practice')),
            ],
            options={
                'verbose_name': 'Monthly Growth Report',
                'verbose_name_plural': 'Monthly Growth Reports',
                'ordering': ['-year', '-month'],
                'unique_together': {('practice', 'year', 'month')},
            },
        ),
        migrations.AddIndex(
            model_name='monthlygrowthreport',
            index=models.Index(fields=['practice', 'year', 'month'], name='reports_mon_practic_861421_idx'),
        ),
    ]

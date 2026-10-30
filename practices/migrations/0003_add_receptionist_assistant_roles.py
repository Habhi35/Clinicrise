from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('practices', '0002_doctor_onboarding'),
    ]

    operations = [
        migrations.AlterField(
            model_name='practicemembership',
            name='role',
            field=models.CharField(
                choices=[
                    ('owner', 'Practice Owner'),
                    ('admin', 'Practice Admin'),
                    ('doctor', 'Doctor / Practitioner'),
                    ('receptionist', 'Frontdesk / Receptionist'),
                    ('assistant', 'Clinical Assistant / Nurse'),
                    ('staff', 'General Staff'),
                ],
                default='staff',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='practiceinvitation',
            name='role',
            field=models.CharField(
                choices=[
                    ('owner', 'Practice Owner'),
                    ('admin', 'Practice Admin'),
                    ('doctor', 'Doctor / Practitioner'),
                    ('receptionist', 'Frontdesk / Receptionist'),
                    ('assistant', 'Clinical Assistant / Nurse'),
                    ('staff', 'General Staff'),
                ],
                default='doctor',
                max_length=20,
            ),
        ),
    ]

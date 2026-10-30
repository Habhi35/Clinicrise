from decimal import Decimal
from django.core.management.base import BaseCommand
from billing.models import SubscriptionPlan


class Command(BaseCommand):
    help = 'Seeds initial subscription plans for ClinicRise (Free Trial, Solo Starter, Growth Polyclinic, Enterprise Hospital).'

    def handle(self, *args, **options):
        plans_data = [
            {
                'name': '14-Day Free Trial',
                'slug': 'free-trial',
                'tier': SubscriptionPlan.TIER_TRIAL,
                'tagline': 'Experience the power of ClinicRise risk-free',
                'description': 'Full access to core scheduling, OPD consultations, digital prescriptions, and patient lead inquiries.',
                'monthly_price': Decimal('0.00'),
                'yearly_price': Decimal('0.00'),
                'yearly_discount_percent': 0,
                'currency': 'INR',
                'trial_days': 14,
                'max_doctors': 1,
                'max_staff': 2,
                'max_locations': 1,
                'max_appointments_per_month': 50,
                'max_storage_mb': 500,
                'custom_domain_enabled': False,
                'teleconsultation_enabled': True,
                'sms_reminders_enabled': True,
                'whatsapp_notifications_enabled': False,
                'prescription_builder_enabled': True,
                'analytics_reports_enabled': True,
                'priority_support': False,
                'api_access_enabled': False,
                'is_active': True,
                'is_public': False,
                'is_default_trial': True,
                'sort_order': 0,
                'features_list': [
                    '1 Doctor Profile',
                    '1 Practice Location',
                    '50 Appointments per month',
                    'Digital Prescription Builder',
                    'Online Teleconsultations',
                    'Patient Lead Management',
                ]
            },
            {
                'name': 'Solo Practitioner',
                'slug': 'solo-starter',
                'tier': SubscriptionPlan.TIER_STARTER,
                'tagline': 'Ideal for individual practitioners and private clinics',
                'description': 'Everything needed to run an independent clinic efficiently, eliminate no-shows, and provide digital prescriptions.',
                'monthly_price': Decimal('1499.00'),
                'yearly_price': Decimal('14990.00'),  # 2 months free equivalent
                'yearly_discount_percent': 17,
                'currency': 'INR',
                'trial_days': 0,
                'max_doctors': 1,
                'max_staff': 3,
                'max_locations': 1,
                'max_appointments_per_month': 250,
                'max_storage_mb': 2048,
                'custom_domain_enabled': False,
                'teleconsultation_enabled': True,
                'sms_reminders_enabled': True,
                'whatsapp_notifications_enabled': False,
                'prescription_builder_enabled': True,
                'analytics_reports_enabled': True,
                'priority_support': False,
                'api_access_enabled': False,
                'is_active': True,
                'is_public': True,
                'is_default_trial': False,
                'sort_order': 1,
                'features_list': [
                    '1 Doctor Profile included',
                    'Up to 3 Staff / Receptionists',
                    '1 Clinic Location',
                    '250 Appointments per month',
                    'Automated SMS Reminders to patients',
                    'Digital Rx Prescriptions & History',
                    'Basic Revenue & Patient Analytics',
                    'Email & Chat Support',
                ]
            },
            {
                'name': 'Growth Polyclinic',
                'slug': 'growth-polyclinic',
                'tier': SubscriptionPlan.TIER_GROWTH,
                'tagline': 'Designed for multi-specialty clinics and expanding teams',
                'description': 'Scale your clinic operations with multiple doctors, locations, WhatsApp reminders, and custom branding.',
                'monthly_price': Decimal('3999.00'),
                'yearly_price': Decimal('39990.00'),
                'yearly_discount_percent': 17,
                'currency': 'INR',
                'trial_days': 0,
                'max_doctors': 5,
                'max_staff': 10,
                'max_locations': 2,
                'max_appointments_per_month': 1000,
                'max_storage_mb': 10240,
                'custom_domain_enabled': True,
                'teleconsultation_enabled': True,
                'sms_reminders_enabled': True,
                'whatsapp_notifications_enabled': True,
                'prescription_builder_enabled': True,
                'analytics_reports_enabled': True,
                'priority_support': False,
                'api_access_enabled': False,
                'is_active': True,
                'is_public': True,
                'is_default_trial': False,
                'sort_order': 2,
                'features_list': [
                    'Up to 5 Doctor Profiles',
                    'Up to 10 Staff Accounts',
                    '2 Clinic Locations / Branches',
                    '1,000 Appointments per month',
                    'Custom Domain Mapping (e.g. yourclinic.com)',
                    'WhatsApp & SMS Reminders',
                    'Teleconsultation Video Calling',
                    'Advanced Financial & Clinical Analytics',
                ]
            },
            {
                'name': 'Enterprise Hospital',
                'slug': 'enterprise-hospital',
                'tier': SubscriptionPlan.TIER_ENTERPRISE,
                'tagline': 'Unlimited scale and dedicated support for healthcare networks',
                'description': 'Full power of ClinicRise with unlimited doctors, multi-branch management, custom integrations, and SLA.',
                'monthly_price': Decimal('8999.00'),
                'yearly_price': Decimal('89990.00'),
                'yearly_discount_percent': 17,
                'currency': 'INR',
                'trial_days': 0,
                'max_doctors': -1,  # Unlimited
                'max_staff': -1,
                'max_locations': -1,
                'max_appointments_per_month': -1,
                'max_storage_mb': 51200,
                'custom_domain_enabled': True,
                'teleconsultation_enabled': True,
                'sms_reminders_enabled': True,
                'whatsapp_notifications_enabled': True,
                'prescription_builder_enabled': True,
                'analytics_reports_enabled': True,
                'priority_support': True,
                'api_access_enabled': True,
                'is_active': True,
                'is_public': True,
                'is_default_trial': False,
                'sort_order': 3,
                'features_list': [
                    'Unlimited Doctor Profiles',
                    'Unlimited Staff Accounts',
                    'Unlimited Clinic Locations',
                    'Unlimited Patient Appointments',
                    'Dedicated Account Manager & 24/7 Priority Support',
                    'Custom Domain & White-labeling',
                    'REST API & Webhook Access',
                    '99.9% Uptime Service Level Agreement',
                ]
            },
        ]

        created_count = 0
        updated_count = 0

        for item in plans_data:
            slug = item.pop('slug')
            plan, created = SubscriptionPlan.objects.update_or_create(
                slug=slug,
                defaults=item
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Created plan: {plan.name}"))
            else:
                updated_count += 1
                self.stdout.write(self.style.NOTICE(f"Updated plan: {plan.name}"))

        self.stdout.write(self.style.SUCCESS(f"Finished seeding plans ({created_count} created, {updated_count} updated)."))

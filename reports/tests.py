import io
import uuid
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from authentication.services.jwt_service import get_tokens_for_user
from practices.models import Practice, PracticeMembership
from reports.models import MonthlyGrowthReport
from reports.services.report_generator_service import ReportGeneratorService
from reports.services.report_pdf_service import ReportPDFService

User = get_user_model()


class GrowthReportsTestCase(TestCase):
    """
    Test suite for Monthly Clinical Performance Summaries and Vector PDF Generation.
    """

    def setUp(self):
        self.client = APIClient()

        # 1. Practice Owner User (Tenant A)
        self.owner = User.objects.create_user(
            email='dr.ananya@zenithortho.com',
            phone_number='+919988776655',
            first_name='Dr. Ananya',
            last_name='Deshmukh',
            password='StrongPassword123!'
        )
        self.owner_tokens = get_tokens_for_user(self.owner)

        # 2. Staff User (Tenant A)
        self.staff_user = User.objects.create_user(
            email='staff@zenithortho.com',
            phone_number='+919988776656',
            first_name='Kavita',
            last_name='Rao',
            password='StrongPassword123!'
        )
        self.staff_tokens = get_tokens_for_user(self.staff_user)

        # 3. Practice Owner (Tenant B - External Clinic)
        self.other_user = User.objects.create_user(
            email='other@externalphysio.com',
            phone_number='+919988776657',
            password='StrongPassword123!'
        )
        self.other_tokens = get_tokens_for_user(self.other_user)

        # 4. Practice Tenant A: Zenith Ortho Clinic
        self.practice = Practice.objects.create(
            name='Zenith Orthocare',
            slug='zenith-orthocare',
            clinic_type='specialty_clinic',
            owner=self.owner,
            phone_number='+919876543000',
            email='info@zenithortho.com',
            city='Bengaluru',
            currency='INR',
            is_active=True
        )
        self.owner_membership = PracticeMembership.objects.create(
            practice=self.practice,
            user=self.owner,
            role=PracticeMembership.ROLE_OWNER,
            is_active=True
        )
        self.staff_membership = PracticeMembership.objects.create(
            practice=self.practice,
            user=self.staff_user,
            role=PracticeMembership.ROLE_STAFF,
            is_active=True
        )

        # 5. Practice Tenant B: External Clinic
        self.other_practice = Practice.objects.create(
            name='Apex Wellness',
            slug='apex-wellness',
            clinic_type='general_clinic',
            owner=self.other_user,
            is_active=True
        )
        self.other_membership = PracticeMembership.objects.create(
            practice=self.other_practice,
            user=self.other_user,
            role=PracticeMembership.ROLE_OWNER,
            is_active=True
        )

    def test_report_generation_service(self):
        """Generates a structured monthly growth report with aggregated KPIs."""
        report = ReportGeneratorService.generate_monthly_report(self.practice, year=2026, month=10)

        self.assertIsNotNone(report.id)
        self.assertEqual(report.practice, self.practice)
        self.assertEqual(report.year, 2026)
        self.assertEqual(report.month, 10)
        self.assertIn("October 2026", report.title)

        # Check metrics structures
        self.assertIn('total_consultations', report.patient_metrics)
        self.assertIn('search_views', report.gbp_metrics)
        self.assertIn('total_impressions', report.gsc_metrics)
        self.assertIn('pack_rank_dominance_pct', report.rank_metrics)
        self.assertTrue(len(report.executive_summary) > 20)
        self.assertTrue(len(report.recommendations) >= 3)

    def test_report_pdf_generation_bytes(self):
        """ReportPDFService compiles a publication-ready vector PDF."""
        report = ReportGeneratorService.generate_monthly_report(self.practice, year=2026, month=10)
        pdf_bytes = ReportPDFService.generate_pdf(report)

        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(len(pdf_bytes) > 1000)
        # PDF magic header
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))

    def test_list_monthly_reports_api(self):
        """Staff can list reports and triggers automatic current month report generation."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.staff_tokens['access']}")
        url = reverse('reports:monthly_reports_list')
        response = self.client.get(url, HTTP_X_PRACTICE_ID=str(self.practice.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data) >= 1)
        first_rep = response.data[0]
        self.assertIn('patient_metrics', first_rep)
        self.assertIn('gbp_metrics', first_rep)
        self.assertIn('rank_metrics', first_rep)

    def test_generate_custom_monthly_report_api(self):
        """Generates a specific month report via POST /api/reports/monthly/generate/."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_tokens['access']}")
        url = reverse('reports:monthly_report_generate')
        payload = {"year": 2026, "month": 9}

        response = self.client.post(url, payload, format='json', HTTP_X_PRACTICE_ID=str(self.practice.id))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['year'], 2026)
        self.assertEqual(response.data['month'], 9)
        self.assertIn("September 2026", response.data['title'])

    def test_report_detail_api(self):
        """GET /api/reports/monthly/<id>/ returns full JSON payload of report."""
        report = ReportGeneratorService.generate_monthly_report(self.practice, year=2026, month=10)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.staff_tokens['access']}")
        url = reverse('reports:monthly_report_detail', kwargs={'pk': report.id})

        response = self.client.get(url, HTTP_X_PRACTICE_ID=str(self.practice.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(report.id))
        self.assertEqual(response.data['year'], 2026)

    def test_download_report_pdf_endpoint(self):
        """GET /api/reports/monthly/<id>/pdf/ serves binary PDF with proper headers."""
        report = ReportGeneratorService.generate_monthly_report(self.practice, year=2026, month=10)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_tokens['access']}")
        url = reverse('reports:monthly_report_pdf', kwargs={'pk': report.id})

        response = self.client.get(url, HTTP_X_PRACTICE_ID=str(self.practice.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_download_latest_report_pdf_endpoint(self):
        """GET /api/reports/monthly/latest/pdf/ serves latest month PDF directly."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.staff_tokens['access']}")
        url = reverse('reports:monthly_report_latest_pdf')

        response = self.client.get(url, HTTP_X_PRACTICE_ID=str(self.practice.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_tenant_isolation_on_reports(self):
        """Tenant B user cannot view or download reports belonging to Tenant A."""
        report = ReportGeneratorService.generate_monthly_report(self.practice, year=2026, month=10)

        # Authenticate as Tenant B
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.other_tokens['access']}")

        # 1. Detail endpoint with Tenant A's ID
        url_detail = reverse('reports:monthly_report_detail', kwargs={'pk': report.id})
        res1 = self.client.get(url_detail, HTTP_X_PRACTICE_ID=str(self.other_practice.id))
        self.assertEqual(res1.status_code, status.HTTP_404_NOT_FOUND)

        # 2. PDF download endpoint
        url_pdf = reverse('reports:monthly_report_pdf', kwargs={'pk': report.id})
        res2 = self.client.get(url_pdf, HTTP_X_PRACTICE_ID=str(self.other_practice.id))
        self.assertEqual(res2.status_code, status.HTTP_404_NOT_FOUND)

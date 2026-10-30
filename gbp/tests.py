import uuid
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from authentication.services.jwt_service import get_tokens_for_user
from practices.models import (
    DoctorProfile,
    DoctorSchedule,
    Practice,
    PracticeImage,
    PracticeMembership,
    PracticeService,
)
from websites.models import ClinicWebsite
from gbp.models import (
    GBPConnection,
    GBPInsight,
    GBPPost,
    GBPProfileChecklist,
    GoogleReview,
    LocalRankKeyword,
    LocalRankSnapshot,
    SearchConsoleQuery,
)
from gbp.services.gbp_service import GBPService
from gbp.services.google_integration_service import GoogleIntegrationService
from gbp.services.local_rank_service import LocalRankService

User = get_user_model()


class GBPChecklistTestCase(TestCase):
    """
    Test suite for Google Business Profile (GBP) checklist,
    progress scoring, and generated setup information.
    """

    def setUp(self):
        self.client = APIClient()

        # 1. Practice Owner User
        self.owner = User.objects.create_user(
            email='dr.rajesh@apollodental.com',
            phone_number='+919876543200',
            first_name='Dr. Rajesh',
            last_name='Sharma',
            password='StrongPassword123!'
        )
        self.owner_tokens = get_tokens_for_user(self.owner)

        # 2. Staff User
        self.staff_user = User.objects.create_user(
            email='reception@apollodental.com',
            phone_number='+919876543201',
            first_name='Priya',
            last_name='Nair',
            password='StrongPassword123!'
        )
        self.staff_tokens = get_tokens_for_user(self.staff_user)

        # 3. External User (Tenant B)
        self.other_user = User.objects.create_user(
            email='other@externalclinic.com',
            phone_number='+919876543202',
            password='StrongPassword123!'
        )
        self.other_tokens = get_tokens_for_user(self.other_user)

        # 4. Practice Tenant A: Apollo Dental Care
        self.practice = Practice.objects.create(
            name='Apollo Dental Care',
            slug='apollo-dental-care',
            clinic_type='dental_clinic',
            owner=self.owner,
            phone_number='+919876543210',
            email='contact@apollodental.com',
            address='Plot 42, Road No. 36, Jubilee Hills',
            landmark='Near Metro Pillar 1400',
            city='Hyderabad',
            state='Telangana',
            postal_code='500033',
            country='India',
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

        # 5. Doctor Profile
        self.doctor = DoctorProfile.objects.create(
            user=self.owner,
            medical_license_number='REG-APOLLO-001',
            specialization='Orthodontist & Implantologist',
            qualifications='MDS (Orthodontics), BDS',
            experience_years=14,
            default_consultation_fee=600,
            bio='Experienced orthodontist specializing in clear aligners and painless dental implants.'
        )

        # 6. Doctor Schedule
        self.schedule = DoctorSchedule.objects.create(
            practice=self.practice,
            doctor=self.doctor,
            day_of_week=DoctorSchedule.DAY_MONDAY,
            session_name='Morning OPD',
            start_time='09:00',
            end_time='13:00'
        )

        # 7. Clinical Services
        self.service1 = PracticeService.objects.create(
            practice=self.practice,
            name='Dental Implants',
            category='Dental Procedure',
            price=25000,
            duration_minutes=60,
            description='Titanium root replacement and premium porcelain crown restoration.'
        )
        self.service2 = PracticeService.objects.create(
            practice=self.practice,
            name='Clear Teeth Aligners',
            category='Orthodontics',
            price=45000,
            duration_minutes=45,
            description='Invisible braces for teeth straightening.'
        )

        # 8. Published Website
        self.website = ClinicWebsite.objects.create(
            practice=self.practice,
            title='Apollo Dental Care - Best Dentist in Jubilee Hills',
            subdomain='apollodental',
            contact_phone='+919876543210',
            whatsapp_number='+919876543210',
            is_published=True
        )

        # 9. Tenant B (for multi-tenant isolation testing)
        self.other_practice = Practice.objects.create(
            name='City Skin & Wellness',
            slug='city-skin',
            owner=self.other_user,
            is_active=True
        )
        self.other_membership = PracticeMembership.objects.create(
            practice=self.other_practice,
            user=self.other_user,
            role=PracticeMembership.ROLE_OWNER,
            is_active=True
        )

    def test_checklist_evaluation(self):
        """Verifies dynamic evaluation of all 10 checklist items and scoring."""
        data = GBPService.evaluate_checklist(self.practice)

        self.assertEqual(data['practice_name'], 'Apollo Dental Care')
        progress = data['progress']
        self.assertEqual(progress['total_items'], 10)
        self.assertTrue(progress['completed_items'] >= 6)  # Name, address, phone, hours, website, services are populated
        self.assertTrue(progress['completion_percentage'] >= 60.0)

        # Check specific items
        items_by_key = {it['key']: it for it in data['checklist']}
        self.assertTrue(items_by_key['business_name']['is_completed'])
        self.assertTrue(items_by_key['location_address']['is_completed'])
        self.assertTrue(items_by_key['phone_and_contact']['is_completed'])
        self.assertTrue(items_by_key['operating_hours']['is_completed'])
        self.assertTrue(items_by_key['website_and_appointment_links']['is_completed'])
        self.assertTrue(items_by_key['services_menu']['is_completed'])

    def test_generated_setup_information(self):
        """Generates complete copy-pasteable assets for Google Business Profile."""
        setup = GBPService.generate_setup_information(self.practice)

        # Business Identity
        ident = setup['business_identity']
        self.assertEqual(ident['business_name'], 'Apollo Dental Care')
        self.assertEqual(ident['primary_category'], 'Dental Clinic')
        self.assertIn('Dental Implants Periodontist', ident['secondary_categories'])
        self.assertIn('Orthodontist', ident['secondary_categories'])

        # SEO Description
        seo = setup['seo_description']
        self.assertIn('Apollo Dental Care', seo['text'])
        self.assertIn('Dr. Rajesh Sharma', seo['text'])
        self.assertIn('Dental Implants', seo['text'])
        self.assertLessEqual(seo['character_count'], 750)

        # NAP
        nap = setup['nap_contact']
        self.assertEqual(nap['business_name'], 'Apollo Dental Care')
        self.assertEqual(nap['phone_number'], '+919876543210')
        self.assertIn('Jubilee Hills', nap['single_line_address'])
        self.assertIn('Hyderabad', nap['single_line_address'])

        # Online Links
        links = setup['online_links']
        self.assertIn('apollodental.clinicrise.com', links['website_url'])
        self.assertIn('#appointment', links['appointment_booking_url'])

        # Operating Hours
        hours = setup['operating_hours']
        self.assertIn('Monday', hours['summary'])

        # Services Catalog
        services = setup['services_catalog']
        self.assertEqual(len(services), 2)
        service_names = [s['name'] for s in services]
        self.assertIn('Dental Implants', service_names)
        self.assertIn('Clear Teeth Aligners', service_names)

        # Review Templates
        rev = setup['review_strategy']
        self.assertIn('Apollo Dental Care', rev['whatsapp_template'])
        self.assertIn('Dr. Rajesh Sharma', rev['whatsapp_template'])

        # Welcome Post
        post = setup['welcome_post']
        self.assertEqual(post['call_to_action'], 'BOOK')
        self.assertIn('Apollo Dental Care', post['title'])

    def test_checklist_api_endpoint(self):
        """Staff can fetch checklist progress via API."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.staff_tokens['access']}")
        url = reverse('gbp:checklist')
        response = self.client.get(url, HTTP_X_PRACTICE_ID=str(self.practice.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('progress', response.data)
        self.assertIn('checklist', response.data)
        self.assertEqual(response.data['progress']['total_items'], 10)

    def test_patch_profile_settings_and_audit(self):
        """Admin can update GBP profile settings and record audit log."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_tokens['access']}")
        url = reverse('gbp:checklist')
        payload = {
            'google_maps_place_id': 'ChIJ_apollo_hyd_123',
            'verification_status': 'verified',
            'google_review_link': 'https://g.page/r/apollo-dental-review',
            'primary_category': 'Dental Clinic'
        }

        response = self.client.patch(url, payload, format='json', HTTP_X_PRACTICE_ID=str(self.practice.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['google_maps_place_id'], 'ChIJ_apollo_hyd_123')
        self.assertEqual(response.data['verification_status'], 'verified')

        profile = GBPProfileChecklist.objects.get(practice=self.practice)
        self.assertEqual(profile.google_maps_place_id, 'ChIJ_apollo_hyd_123')

    def test_toggle_checklist_item(self):
        """Manually checking off a checklist item updates progress percentage."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.staff_tokens['access']}")
        url = reverse('gbp:checklist_toggle')
        payload = {
            'item_key': 'clinic_photos',
            'is_completed': True
        }

        response = self.client.post(url, payload, format='json', HTTP_X_PRACTICE_ID=str(self.practice.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertTrue(response.data['is_completed'])

        profile = GBPProfileChecklist.objects.get(practice=self.practice)
        self.assertIn('clinic_photos', profile.manual_completed_items)

    def test_setup_info_api_endpoint(self):
        """GET /api/gbp/setup-info/ returns complete setup assets."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.staff_tokens['access']}")
        url = reverse('gbp:setup_info')
        response = self.client.get(url, HTTP_X_PRACTICE_ID=str(self.practice.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('business_identity', response.data)
        self.assertIn('seo_description', response.data)
        self.assertIn('nap_contact', response.data)
        self.assertIn('operating_hours', response.data)
        self.assertIn('services_catalog', response.data)
        self.assertIn('welcome_post', response.data)

    def test_review_link_endpoint(self):
        """GET /api/gbp/review-link/ returns review shortcut and WhatsApp templates."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.staff_tokens['access']}")
        url = reverse('gbp:review_link')
        response = self.client.get(url, HTTP_X_PRACTICE_ID=str(self.practice.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('review_url', response.data)
        self.assertIn('whatsapp_template', response.data)

    def test_tenant_isolation(self):
        """Tenant B user cannot access Tenant A's GBP checklist."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.other_tokens['access']}")
        url = reverse('gbp:checklist')
        response = self.client.get(url, HTTP_X_PRACTICE_ID=str(self.practice.id))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class GBPAdvancedIntegrationsTestCase(TestCase):
    """
    Test suite for Google Business Profile API Management, Google Search Console,
    HIPAA-compliant AI Review Replies, and Local 3-Pack Rank Tracking.
    """

    def setUp(self):
        self.client = APIClient()

        # Practice Owner (Tenant A)
        self.owner = User.objects.create_user(
            email='dr.vikram@crestwoodortho.com',
            phone_number='+919876543300',
            first_name='Dr. Vikram',
            last_name='Mehta',
            password='StrongPassword123!'
        )
        self.owner_tokens = get_tokens_for_user(self.owner)

        # Staff User (Tenant A)
        self.staff_user = User.objects.create_user(
            email='reception@crestwoodortho.com',
            phone_number='+919876543301',
            first_name='Anjali',
            last_name='Sharma',
            password='StrongPassword123!'
        )
        self.staff_tokens = get_tokens_for_user(self.staff_user)

        # External User (Tenant B)
        self.other_user = User.objects.create_user(
            email='other@externalclinic.com',
            phone_number='+919876543302',
            password='StrongPassword123!'
        )
        self.other_tokens = get_tokens_for_user(self.other_user)

        # Practice Tenant A: Crestwood Orthodontics
        self.practice = Practice.objects.create(
            name='Crestwood Orthodontics',
            slug='crestwood-orthodontics',
            clinic_type='dental_clinic',
            owner=self.owner,
            phone_number='+919876543310',
            email='contact@crestwoodortho.com',
            city='Bengaluru',
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

        # Practice Tenant B
        self.other_practice = Practice.objects.create(
            name='Lakeside Derm',
            slug='lakeside-derm',
            owner=self.other_user,
            is_active=True
        )
        self.other_membership = PracticeMembership.objects.create(
            practice=self.other_practice,
            user=self.other_user,
            role=PracticeMembership.ROLE_OWNER,
            is_active=True
        )

    def test_gbp_connection_lifecycle(self):
        """GET /api/gbp/connection/ and POST /api/gbp/connection/ for OAuth & Location config."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_tokens['access']}")
        url = reverse('gbp:connection')

        # Initial fetch
        res = self.client.get(url, HTTP_X_PRACTICE_ID=str(self.practice.id))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('is_connected', res.data)

        # Update connection with location ID & credentials
        post_data = {
            'account_id': 'accounts/1098234710',
            'location_id': 'locations/8821947291',
            'google_account_email': 'clinic.google@crestwoodortho.com',
            'is_connected': True,
            'sync_status': 'success'
        }
        res_post = self.client.post(url, post_data, format='json', HTTP_X_PRACTICE_ID=str(self.practice.id))
        self.assertEqual(res_post.status_code, status.HTTP_200_OK)
        self.assertTrue(res_post.data['is_connected'])
        self.assertEqual(res_post.data['location_id'], 'locations/8821947291')
        self.assertEqual(res_post.data['google_account_email'], 'clinic.google@crestwoodortho.com')

    def test_sync_gbp_and_gsc(self):
        """POST /api/gbp/sync/ pulls 30-day GBP insights, reviews, and GSC organic queries."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.staff_tokens['access']}")
        url = reverse('gbp:sync')

        res = self.client.post(url, {}, HTTP_X_PRACTICE_ID=str(self.practice.id))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'success')

        # Check records in DB
        self.assertTrue(GBPInsight.objects.filter(practice=self.practice).exists())
        self.assertTrue(GoogleReview.objects.filter(practice=self.practice).exists())
        self.assertTrue(SearchConsoleQuery.objects.filter(practice=self.practice).exists())

    def test_reviews_listing_and_filtering(self):
        """Staff can list reviews and filter by rating or reply status."""
        GoogleIntegrationService.sync_gbp_data(self.practice)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.staff_tokens['access']}")
        url = reverse('gbp:reviews')

        # List all
        res = self.client.get(url, HTTP_X_PRACTICE_ID=str(self.practice.id))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(len(res.data['reviews']) >= 3)
        self.assertTrue(res.data['total_reviews'] >= 3)

        # Filter 5-star
        res_5star = self.client.get(f"{url}?rating=5", HTTP_X_PRACTICE_ID=str(self.practice.id))
        self.assertEqual(res_5star.status_code, status.HTTP_200_OK)
        for r in res_5star.data['reviews']:
            self.assertEqual(r['star_rating'], 5)

    def test_ai_review_reply_generation_hipaa_safe(self):
        """AI generates an empathetic, professional reply without disclosing medical records."""
        review = GoogleReview.objects.create(
            practice=self.practice,
            review_id='test_rev_5star',
            reviewer_name='Rahul K.',
            star_rating=5,
            comment='Excellent clear aligners treatment by Dr. Vikram. Painless and very modern clinic!',
            review_timestamp=timezone.now()
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.staff_tokens['access']}")
        url = reverse('gbp:review_generate_reply', kwargs={'pk': review.id})

        res = self.client.post(url, {}, HTTP_X_PRACTICE_ID=str(self.practice.id))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        reply = res.data['ai_suggested_reply']
        self.assertTrue(len(reply) > 20)
        self.assertIn('Rahul', reply)
        # Verify confidentiality reminder
        self.assertIn('compliance_note', res.data)

    def test_submit_review_reply(self):
        """Staff can post a reply to a patient review."""
        review = GoogleReview.objects.create(
            practice=self.practice,
            review_id='test_rev_reply_me',
            reviewer_name='Sunita M.',
            star_rating=4,
            comment='Good doctor and hygiene.',
            review_timestamp=timezone.now()
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.staff_tokens['access']}")
        url = reverse('gbp:review_reply', kwargs={'pk': review.id})
        payload = {'reply_text': 'Thank you Sunita for your gracious review! We wish you continuous healthy smiles.'}

        res = self.client.post(url, payload, format='json', HTTP_X_PRACTICE_ID=str(self.practice.id))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['is_replied'])
        self.assertEqual(res.data['reply_text'], payload['reply_text'])

        review.refresh_from_db()
        self.assertTrue(review.is_replied)
        self.assertIsNotNone(review.replied_at)

    def test_gbp_post_creation_and_listing(self):
        """Doctors can publish Google Posts/Updates with Call to Action."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_tokens['access']}")
        url = reverse('gbp:posts')

        post_data = {
            'post_type': 'offer',
            'summary': 'October Dental Checkup Camp: Avail free digital panoramic X-ray with consultation.',
            'cta_type': 'book',
            'cta_url': 'https://crestwoodortho.clinicrise.com#appointment',
        }

        res_create = self.client.post(url, post_data, format='json', HTTP_X_PRACTICE_ID=str(self.practice.id))
        self.assertEqual(res_create.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res_create.data['post_type'], 'offer')
        self.assertEqual(res_create.data['status'], 'published')

        # List posts
        res_list = self.client.get(url, HTTP_X_PRACTICE_ID=str(self.practice.id))
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_list.data), 1)

    def test_search_console_overview_and_queries(self):
        """GET /api/gbp/search-console/overview/ and queries return organic traffic data."""
        GoogleIntegrationService.sync_search_console(self.practice)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.staff_tokens['access']}")

        # Overview
        url_overview = reverse('gbp:search_console_overview')
        res_overview = self.client.get(url_overview, HTTP_X_PRACTICE_ID=str(self.practice.id))
        self.assertEqual(res_overview.status_code, status.HTTP_200_OK)
        self.assertIn('total_organic_clicks', res_overview.data)
        self.assertIn('total_impressions', res_overview.data)
        self.assertIn('top_queries', res_overview.data)
        self.assertTrue(res_overview.data['total_organic_clicks'] > 0)

        # Queries
        url_queries = reverse('gbp:search_console_queries')
        res_queries = self.client.get(url_queries, HTTP_X_PRACTICE_ID=str(self.practice.id))
        self.assertEqual(res_queries.status_code, status.HTTP_200_OK)
        self.assertTrue(len(res_queries.data) >= 1)

    def test_local_rank_tracking_engine(self):
        """Tests keyword seeding, rank checking, and local 3-pack overview."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.staff_tokens['access']}")

        # 1. Fetch keywords (auto seeds 5 standard dental keywords)
        url_keywords = reverse('gbp:rank_keywords')
        res_kw = self.client.get(url_keywords, HTTP_X_PRACTICE_ID=str(self.practice.id))
        self.assertEqual(res_kw.status_code, status.HTTP_200_OK)
        self.assertTrue(len(res_kw.data) >= 4)

        # 2. Trigger Rank Check
        url_check = reverse('gbp:rank_check')
        res_check = self.client.post(url_check, {}, HTTP_X_PRACTICE_ID=str(self.practice.id))
        self.assertEqual(res_check.status_code, status.HTTP_200_OK)
        self.assertTrue(res_check.data['success'])
        self.assertTrue(res_check.data['keywords_checked'] >= 4)

        # 3. Fetch Local Rank Overview
        url_overview = reverse('gbp:rank_overview')
        res_overview = self.client.get(url_overview, HTTP_X_PRACTICE_ID=str(self.practice.id))
        self.assertEqual(res_overview.status_code, status.HTTP_200_OK)
        self.assertIn('pack_rank_dominance_pct', res_overview.data)
        self.assertIn('keywords_in_top_3', res_overview.data)
        self.assertIn('average_pack_rank', res_overview.data)

    def test_tenant_isolation_advanced_features(self):
        """Tenant B cannot access Tenant A's reviews, posts, or rank data."""
        # Seed Tenant A data
        GoogleIntegrationService.sync_gbp_data(self.practice)
        rev = GoogleReview.objects.filter(practice=self.practice).first()

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.other_tokens['access']}")

        # Attempt to reply to Tenant A's review
        url_reply = reverse('gbp:review_reply', kwargs={'pk': rev.id})
        res = self.client.post(url_reply, {'reply_text': 'Hacked reply'}, format='json', HTTP_X_PRACTICE_ID=str(self.other_practice.id))
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

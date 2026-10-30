import uuid
from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from authentication.services.jwt_service import get_tokens_for_user
from practices.models import Practice, PracticeMembership
from websites.models import ClinicWebsite
from leads.models import ClickEvent, Lead
from bookings.models import BookingRequest
from analytics.models import WebsiteVisit
from analytics.services.traffic_parser import TrafficParser
from analytics.services.analytics_service import AnalyticsService

User = get_user_model()


class TrafficParserTestCase(TestCase):
    """
    Tests for traffic channel attribution, UTM parameter parsing, and device detection.
    """

    def test_organic_search_classification(self):
        result = TrafficParser.parse_visit_data({
            'page_url': 'https://citydental.clinicrise.com/treatments',
            'referrer': 'https://www.google.com/search?q=dentist+near+me',
        })
        self.assertEqual(result['traffic_channel'], WebsiteVisit.CHANNEL_ORGANIC_SEARCH)
        self.assertEqual(result['traffic_source'], 'Google')
        self.assertEqual(result['referrer_domain'], 'www.google.com')

    def test_direct_traffic_classification(self):
        result = TrafficParser.parse_visit_data({
            'page_url': 'https://citydental.clinicrise.com/',
            'referrer': '',
        })
        self.assertEqual(result['traffic_channel'], WebsiteVisit.CHANNEL_DIRECT)
        self.assertEqual(result['traffic_source'], 'Direct')

    def test_social_instagram_classification(self):
        result = TrafficParser.parse_visit_data({
            'page_url': 'https://citydental.clinicrise.com/doctors',
            'referrer': 'https://l.instagram.com/',
        })
        self.assertEqual(result['traffic_channel'], WebsiteVisit.CHANNEL_SOCIAL)
        self.assertEqual(result['traffic_source'], 'Instagram')

    def test_whatsapp_classification(self):
        result = TrafficParser.parse_visit_data({
            'page_url': 'https://citydental.clinicrise.com/appointment?utm_source=whatsapp',
            'referrer': 'https://api.whatsapp.com/send',
        })
        self.assertEqual(result['traffic_channel'], WebsiteVisit.CHANNEL_WHATSAPP)
        self.assertEqual(result['traffic_source'], 'WhatsApp')

    def test_paid_ad_classification_with_gclid(self):
        result = TrafficParser.parse_visit_data({
            'page_url': 'https://citydental.clinicrise.com/?gclid=AIzaSyDxyz123&utm_medium=cpc&utm_source=google_ads&utm_campaign=teeth_whitening',
            'referrer': 'https://www.google.com/',
        })
        self.assertEqual(result['traffic_channel'], WebsiteVisit.CHANNEL_PAID_AD)
        self.assertEqual(result['utm_campaign'], 'teeth_whitening')
        self.assertEqual(result['utm_medium'], 'cpc')

    def test_external_referral_classification(self):
        result = TrafficParser.parse_visit_data({
            'page_url': 'https://citydental.clinicrise.com/',
            'referrer': 'https://www.practo.com/hyderabad/clinic/city-dental-care',
        })
        self.assertEqual(result['traffic_channel'], WebsiteVisit.CHANNEL_REFERRAL)
        self.assertIn('practo.com', result['traffic_source'])

    def test_device_detection(self):
        mobile_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"
        desktop_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/114.0.0.0 Safari/537.36"
        tablet_ua = "Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"

        self.assertEqual(TrafficParser.detect_device(mobile_ua), WebsiteVisit.DEVICE_MOBILE)
        self.assertEqual(TrafficParser.detect_device(desktop_ua), WebsiteVisit.DEVICE_DESKTOP)
        self.assertEqual(TrafficParser.detect_device(tablet_ua), WebsiteVisit.DEVICE_TABLET)


class AnalyticsDashboardTestCase(TestCase):
    """
    End-to-end tests for Basic Analytics:
    - Public visit tracking beacon
    - Authenticated dashboard KPI aggregation
    - Traffic sources breakdown
    - Calls, WhatsApp clicks, enquiries, bookings
    - Patient conversion funnel
    - Tenant isolation
    """

    def setUp(self):
        self.client = APIClient()

        # 1. Practice Owner User
        self.owner = User.objects.create_user(
            email='dr.rajesh@apollodental.com',
            phone_number='+919876543200',
            first_name='Rajesh',
            last_name='Sharma',
            password='StrongPassword123!'
        )
        self.owner_tokens = get_tokens_for_user(self.owner)

        # 2. Practice Tenant A
        self.practice = Practice.objects.create(
            name='Apollo Dental Care',
            slug='apollo-dental',
            owner=self.owner,
            city='Hyderabad',
            state='Telangana',
            is_active=True
        )
        self.membership = PracticeMembership.objects.create(
            practice=self.practice,
            user=self.owner,
            role=PracticeMembership.ROLE_OWNER,
            is_active=True
        )

        # 3. Practice Website
        self.website = ClinicWebsite.objects.create(
            practice=self.practice,
            title='Apollo Dental Care Official',
            subdomain='apollodental',
            is_published=True
        )

        # 4. Another Tenant B (for multi-tenant isolation verification)
        self.other_owner = User.objects.create_user(
            email='dr.other@otherclinic.com',
            phone_number='+919876543201',
            password='StrongPassword123!'
        )
        self.other_practice = Practice.objects.create(
            name='Other Health Clinic',
            slug='other-clinic',
            owner=self.other_owner,
            is_active=True
        )
        self.other_membership = PracticeMembership.objects.create(
            practice=self.other_practice,
            user=self.other_owner,
            role=PracticeMembership.ROLE_OWNER,
            is_active=True
        )

    def test_public_visit_tracking(self):
        """Public beacon logs website visits with attribution."""
        url = reverse('analytics:public_visit_track', kwargs={'practice_slug_or_domain': self.practice.slug})
        payload = {
            'page_url': 'https://apollodental.clinicrise.com/treatments/implants',
            'page_path': '/treatments/implants',
            'page_title': 'Dental Implants | Apollo Dental',
            'referrer': 'https://www.google.com/',
            'visitor_id': 'vis_test_123',
            'session_id': 'sess_test_abc',
            'device_type': 'mobile'
        }

        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['traffic_channel'], WebsiteVisit.CHANNEL_ORGANIC_SEARCH)
        self.assertEqual(response.data['traffic_source'], 'Google')
        self.assertTrue(response.data['is_unique_daily'])

        # Verify record in database
        visit = WebsiteVisit.objects.get(id=response.data['visit_id'])
        self.assertEqual(visit.practice, self.practice)
        self.assertEqual(visit.website, self.website)
        self.assertEqual(visit.page_path, '/treatments/implants')

    def test_unique_daily_visitor_flagging(self):
        """Second visit by the same visitor_id on the same day is marked is_unique_daily=False."""
        url = reverse('analytics:public_visit_track', kwargs={'practice_slug_or_domain': self.practice.slug})
        payload = {
            'page_url': 'https://apollodental.clinicrise.com/',
            'visitor_id': 'vis_repeat_999',
        }

        # 1st visit
        res1 = self.client.post(url, payload, format='json')
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res1.data['is_unique_daily'])

        # 2nd visit
        res2 = self.client.post(url, payload, format='json')
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)
        self.assertFalse(res2.data['is_unique_daily'])

    def test_basic_analytics_dashboard_metrics(self):
        """
        Dashboard calculates website visits, traffic sources, calls,
        WhatsApp clicks, enquiries, bookings, and funnel correctly.
        """
        # Create seed analytics data:
        # 1. Website Visits (1 Organic, 1 Social, 1 Direct)
        WebsiteVisit.objects.create(
            practice=self.practice,
            website=self.website,
            visitor_id='vis_1',
            page_url='https://apollodental.clinicrise.com/',
            page_path='/',
            traffic_channel=WebsiteVisit.CHANNEL_ORGANIC_SEARCH,
            traffic_source='Google',
            device_type=WebsiteVisit.DEVICE_MOBILE,
            is_unique_daily=True
        )
        WebsiteVisit.objects.create(
            practice=self.practice,
            website=self.website,
            visitor_id='vis_2',
            page_url='https://apollodental.clinicrise.com/doctors',
            page_path='/doctors',
            traffic_channel=WebsiteVisit.CHANNEL_SOCIAL,
            traffic_source='Instagram',
            utm_campaign='summer_smile',
            device_type=WebsiteVisit.DEVICE_DESKTOP,
            is_unique_daily=True
        )
        WebsiteVisit.objects.create(
            practice=self.practice,
            website=self.website,
            visitor_id='vis_3',
            page_url='https://apollodental.clinicrise.com/',
            page_path='/',
            traffic_channel=WebsiteVisit.CHANNEL_DIRECT,
            traffic_source='Direct',
            device_type=WebsiteVisit.DEVICE_MOBILE,
            is_unique_daily=True
        )

        # 2. Call and WhatsApp click events
        ClickEvent.objects.create(
            practice=self.practice,
            website=self.website,
            event_type=ClickEvent.TYPE_CALL_CLICK,
            target_phone='+919876543200'
        )
        ClickEvent.objects.create(
            practice=self.practice,
            website=self.website,
            event_type=ClickEvent.TYPE_WHATSAPP_CLICK,
            target_phone='+919876543200'
        )
        ClickEvent.objects.create(
            practice=self.practice,
            website=self.website,
            event_type=ClickEvent.TYPE_WHATSAPP_CLICK,
            target_phone='+919876543200'
        )

        # 3. Patient Enquiries (Leads)
        Lead.objects.create(
            practice=self.practice,
            website=self.website,
            patient_name='Patient Anita',
            phone_number='+919876511111',
            status=Lead.STATUS_CONVERTED,
            source=Lead.SOURCE_WEBSITE_FORM
        )
        Lead.objects.create(
            practice=self.practice,
            website=self.website,
            patient_name='Patient Suresh',
            phone_number='+919876522222',
            status=Lead.STATUS_NEW,
            source=Lead.SOURCE_WHATSAPP_CLICK
        )

        # 4. Appointment Booking Request
        BookingRequest.objects.create(
            practice=self.practice,
            patient_name='Patient Anita',
            phone_number='+919876511111',
            preferred_date=date.today(),
            status=BookingRequest.STATUS_CONFIRMED,
            consultation_mode=BookingRequest.MODE_IN_PERSON
        )

        # 5. Data in Other Practice (should NOT bleed in)
        WebsiteVisit.objects.create(
            practice=self.other_practice,
            page_url='https://other.clinicrise.com/',
            traffic_channel=WebsiteVisit.CHANNEL_DIRECT
        )

        # Query authenticated dashboard
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_tokens['access']}")
        url = reverse('analytics:dashboard')
        response = self.client.get(url, HTTP_X_PRACTICE_ID=str(self.practice.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data

        # Verify Summary KPIs
        summary = data['summary']
        self.assertEqual(summary['website_visits'], 3)
        self.assertEqual(summary['unique_visitors'], 3)
        self.assertEqual(summary['calls'], 1)
        self.assertEqual(summary['whatsapp_clicks'], 2)
        self.assertEqual(summary['total_clicks'], 3)
        self.assertEqual(summary['enquiries'], 2)
        self.assertEqual(summary['bookings'], 1)
        self.assertEqual(summary['confirmed_bookings'], 1)

        # Verify Traffic Sources
        channels = data['traffic_sources']['channels']
        self.assertEqual(channels['organic_search']['count'], 1)
        self.assertEqual(channels['social']['count'], 1)
        self.assertEqual(channels['direct']['count'], 1)

        # Top sources
        sources = [s['source'] for s in data['traffic_sources']['top_sources']]
        self.assertIn('Google', sources)
        self.assertIn('Instagram', sources)

        # Top campaigns
        campaigns = [c['campaign'] for c in data['traffic_sources']['top_campaigns']]
        self.assertIn('summer_smile', campaigns)

        # Calls & WhatsApp
        self.assertEqual(data['calls_and_whatsapp']['total_calls'], 1)
        self.assertEqual(data['calls_and_whatsapp']['total_whatsapp_clicks'], 2)

        # Enquiries
        self.assertEqual(data['enquiries']['total'], 2)
        self.assertEqual(data['enquiries']['conversion_rate_percentage'], 50.0)

        # Bookings
        self.assertEqual(data['bookings']['total'], 1)
        self.assertEqual(data['bookings']['confirmed'], 1)
        self.assertEqual(data['bookings']['confirmation_rate_percentage'], 100.0)

        # Conversion Funnel
        funnel = data['conversion_funnel']
        self.assertEqual(funnel['stages'][0]['count'], 3)  # 3 Visits
        self.assertEqual(funnel['stages'][1]['count'], 3)  # 3 Interactions (1 Call + 2 WhatsApp)
        self.assertEqual(funnel['stages'][2]['count'], 3)  # 2 Enquiries + 1 Booking = 3
        self.assertEqual(funnel['stages'][3]['count'], 2)  # 1 Converted Enquiry + 1 Confirmed Booking = 2

        # Timeseries
        self.assertTrue(len(data['timeseries']) > 0)
        today_point = [pt for pt in data['timeseries'] if pt['date'] == str(date.today())]
        self.assertEqual(len(today_point), 1)
        self.assertEqual(today_point[0]['visits'], 3)
        self.assertEqual(today_point[0]['calls'], 1)
        self.assertEqual(today_point[0]['whatsapp_clicks'], 2)

    def test_traffic_sources_endpoint(self):
        """GET /api/analytics/traffic-sources/ returns channel and referrer details."""
        WebsiteVisit.objects.create(
            practice=self.practice,
            page_url='https://apollodental.clinicrise.com/',
            traffic_channel=WebsiteVisit.CHANNEL_PAID_AD,
            traffic_source='Google Ads',
            utm_campaign='implant_camp',
            device_type=WebsiteVisit.DEVICE_MOBILE
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_tokens['access']}")
        url = reverse('analytics:traffic_sources')
        response = self.client.get(url, HTTP_X_PRACTICE_ID=str(self.practice.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('traffic_sources', response.data)
        self.assertIn('channels', response.data['traffic_sources'])
        self.assertEqual(response.data['traffic_sources']['channels']['paid_ad']['count'], 1)

    def test_conversion_funnel_endpoint(self):
        """GET /api/analytics/funnel/ returns the 4-stage funnel."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_tokens['access']}")
        url = reverse('analytics:funnel')
        response = self.client.get(url, HTTP_X_PRACTICE_ID=str(self.practice.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('conversion_funnel', response.data)
        self.assertEqual(len(response.data['conversion_funnel']['stages']), 4)

    def test_website_direct_analytics_endpoint(self):
        """GET /api/websites/<website_id>/analytics/ returns website-scoped metrics."""
        WebsiteVisit.objects.create(
            practice=self.practice,
            website=self.website,
            page_url='https://apollodental.clinicrise.com/',
            traffic_channel=WebsiteVisit.CHANNEL_DIRECT
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_tokens['access']}")
        url = reverse('websites:website_analytics', kwargs={'website_id': self.website.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['summary']['website_visits'], 1)

    def test_tenant_isolation_and_permission_checks(self):
        """Other users cannot access practice analytics."""
        unauthorized_user = User.objects.create_user(
            email='unauth@random.com',
            phone_number='+919876543999',
            password='StrongPassword123!'
        )
        unauth_tokens = get_tokens_for_user(unauthorized_user)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {unauth_tokens['access']}")
        url = reverse('analytics:dashboard')
        response = self.client.get(url, HTTP_X_PRACTICE_ID=str(self.practice.id))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

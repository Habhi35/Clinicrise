from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from authentication.models import User
from authentication.services.jwt_service import get_tokens_for_user
from practices.models import Practice, PracticeMembership
from websites.models import ClinicWebsite, CustomDomain, WebsitePage
from websites.services.approval_service import ContentApprovalService

class WebsitesAppAPITests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="dr.owner@websiteclinic.com",
            phone_number="+919876540001",
            first_name="Dr. Owner",
            password="StrongPassword123!"
        )
        self.tokens = get_tokens_for_user(self.owner)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.tokens['access']}")

        self.practice = Practice.objects.create(
            name="Website Test Clinic",
            clinic_type=Practice.CLINIC_TYPE_SOLO,
            city="Mumbai",
            state="Maharashtra",
            phone_number="+919876540001",
            owner=self.owner
        )
        PracticeMembership.objects.create(
            practice=self.practice,
            user=self.owner,
            role=PracticeMembership.ROLE_OWNER,
            is_active=True
        )

    def test_website_generation_and_rendering(self):
        # 1. Generate website
        res = self.client.post("/api/websites/generate/", {
            "practice_id": str(self.practice.id),
            "subdomain": "websitetestclinic",
            "template_style": "modern_minimal",
            "auto_publish": True
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data['success'])
        website_id = res.data['website']['id']

        # 2. Public rendering
        from rest_framework.test import APIClient
        public_client = APIClient()
        pub_res = public_client.get("/api/websites/public/websitetestclinic/")
        self.assertEqual(pub_res.status_code, status.HTTP_200_OK)
        self.assertEqual(pub_res.data['website']['title'], "Website Test Clinic")

        # 3. Add Custom Domain
        dom_res = self.client.post(f"/api/websites/{website_id}/domains/", {
            "domain": "testcliniccustom.com"
        }, format="json")
        self.assertEqual(dom_res.status_code, status.HTTP_201_CREATED)
        domain_id = dom_res.data['domain']['id']

        # 4. Verify Custom Domain
        ver_res = self.client.post(f"/api/websites/{website_id}/domains/{domain_id}/verify/", {"simulate": True}, format="json")
        self.assertEqual(ver_res.status_code, status.HTTP_200_OK)

        # 5. Page Review & Approval
        page = WebsitePage.objects.create(
            website_id=website_id,
            title="Aesthetic Treatments",
            slug="aesthetic-treatments",
            page_type=WebsitePage.PAGE_TYPE_SERVICES,
            draft_content={"intro": "Clinical details"}
        )
        ContentApprovalService.submit_for_review(page, self.owner, submission_notes="Initial medical draft")

        rev_res = self.client.post(f"/api/websites/{website_id}/pages/{page.id}/review/", {
            "action": "approve",
            "review_notes": "Medically verified"
        }, format="json")
        self.assertEqual(rev_res.status_code, status.HTTP_200_OK)
        self.assertEqual(rev_res.data['approval_status'], ContentApprovalService.STATUS_APPROVED)

        # 6. Publish Page
        pub_page_res = self.client.post(f"/api/websites/{website_id}/pages/{page.id}/publish/", {}, format="json")
        self.assertEqual(pub_page_res.status_code, status.HTTP_200_OK)
        self.assertTrue(pub_page_res.data['page']['is_published'])

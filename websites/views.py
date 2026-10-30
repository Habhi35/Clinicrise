from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from practices.models import Practice, PracticeMembership
from practices.permissions import IsPracticeAdmin, IsPracticeMember
from websites.models import (
    ClinicWebsite,
    CustomDomain,
    WebsiteInquiry,
    WebsitePage,
    WebsitePageRevision,
)
from websites.serializers import (
    BlogPostCreateUpdateSerializer,
    ClinicWebsiteSerializer,
    ClinicWebsiteUpdateSerializer,
    CustomDomainSerializer,
    DoctorReviewActionSerializer,
    SubmitReviewRequestSerializer,
    WebsiteGenerateInputSerializer,
    WebsiteInquirySerializer,
    WebsitePageEditSerializer,
    WebsitePageRevisionSerializer,
    WebsitePageSerializer,
    WebsitePageSummarySerializer,
)
from websites.services.approval_service import ContentApprovalService
from websites.services.domain_verifier import DomainVerificationService
from websites.services.website_generator import WebsiteGenerationService


def _get_user_practice(request, practice_id=None):
    """Resolve practice from parameter, active tenant header, or user's owned practice."""
    if practice_id:
        return get_object_or_404(Practice, id=practice_id, is_active=True)
    
    tenant_practice = getattr(request, 'practice', None)
    if tenant_practice:
        return tenant_practice

    # Fallback to user's first owned or active practice
    owned = request.user.owned_practices.filter(is_active=True).first()
    if owned:
        return owned
    
    membership = request.user.practice_memberships.filter(is_active=True).select_related('practice').first()
    if membership:
        return membership.practice
    return None


def _check_website_permission(request, website):
    """Verify that the user is an owner, admin, or doctor of the practice owning the website."""
    if not request.user or not request.user.is_authenticated:
        return False
    membership = PracticeMembership.objects.filter(
        practice=website.practice,
        user=request.user,
        is_active=True
    ).first()
    return bool(membership and membership.role in [
        PracticeMembership.ROLE_OWNER,
        PracticeMembership.ROLE_ADMIN,
        PracticeMembership.ROLE_DOCTOR
    ])


def _check_doctor_permission(request, website):
    """Verify that user is a verified doctor, admin, or owner in the practice."""
    if not request.user or not request.user.is_authenticated:
        return False
    membership = PracticeMembership.objects.filter(
        practice=website.practice,
        user=request.user,
        is_active=True
    ).first()
    return bool(membership and membership.is_doctor)


def _check_member_permission(request, website):
    """Verify that user has active membership (staff, doctor, admin, owner) in the practice."""
    if not request.user or not request.user.is_authenticated:
        return False
    return PracticeMembership.objects.filter(
        practice=website.practice,
        user=request.user,
        is_active=True
    ).exists()


# =====================================================================
# 1. WEBSITE CORE & GENERATION VIEWS
# =====================================================================

class WebsiteCurrentView(APIView):
    """
    Get the website configuration for the active practice tenant.
    GET /api/websites/current/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_user_practice(request)
        if not practice:
            return Response(
                {"error": "No active practice found. Please create a practice or provide 'X-Practice-ID' header."},
                status=status.HTTP_404_NOT_FOUND
            )

        website = getattr(practice, 'clinic_website', None)
        if not website:
            return Response(
                {
                    "has_website": False,
                    "message": f"No website has been generated yet for practice '{practice.name}'. Use POST /api/websites/generate/ to create one.",
                    "practice_id": str(practice.id),
                    "practice_name": practice.name,
                },
                status=status.HTTP_200_OK
            )

        serializer = ClinicWebsiteSerializer(website)
        data = serializer.data
        data['has_website'] = True
        return Response(data, status=status.HTTP_200_OK)


class WebsiteGenerateView(APIView):
    """
    Auto-generate a complete clinic website from practice details,
    doctor credentials, services, timings, and gallery images.
    POST /api/websites/generate/
    Payload: {"practice_id": "<uuid>", "template_style": "modern_minimal", "subdomain": "citydental", "auto_publish": true}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = WebsiteGenerateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        practice = _get_user_practice(request, data.get('practice_id'))
        if not practice:
            return Response(
                {"error": "Valid practice is required to generate a website."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check permissions
        membership = PracticeMembership.objects.filter(
            practice=practice,
            user=request.user,
            is_active=True
        ).first()
        if not membership or membership.role not in [PracticeMembership.ROLE_OWNER, PracticeMembership.ROLE_ADMIN]:
            return Response(
                {"error": "Only practice owners or administrators can generate a website."},
                status=status.HTTP_403_FORBIDDEN
            )

        website = WebsiteGenerationService.generate_for_practice(
            practice=practice,
            template_style=data.get('template_style'),
            subdomain=data.get('subdomain'),
            auto_publish=data.get('auto_publish', True)
        )

        return Response(
            {
                "success": True,
                "message": f"Website '{website.title}' generated successfully!",
                "public_url": website.public_url,
                "website": ClinicWebsiteSerializer(website).data,
            },
            status=status.HTTP_201_CREATED
        )


class WebsiteDetailView(APIView):
    """
    Retrieve or update website settings, theme, typography, SEO, and contact quicklinks.
    GET /api/websites/<website_id>/
    PATCH /api/websites/<website_id>/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, website_id):
        website = get_object_or_404(ClinicWebsite, id=website_id)
        if not _check_website_permission(request, website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        return Response(ClinicWebsiteSerializer(website).data, status=status.HTTP_200_OK)

    def patch(self, request, website_id):
        website = get_object_or_404(ClinicWebsite, id=website_id)
        if not _check_website_permission(request, website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        serializer = ClinicWebsiteUpdateSerializer(website, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Mark website has unpublished changes if styling changed
        website.has_unpublished_changes = True
        website.save(update_fields=['has_unpublished_changes'])

        return Response(ClinicWebsiteSerializer(website).data, status=status.HTTP_200_OK)


class WebsitePublishView(APIView):
    """
    1-Click publish entire website. Publishes all draft pages and sets live status.
    POST /api/websites/<website_id>/publish/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, website_id):
        website = get_object_or_404(ClinicWebsite, id=website_id)
        if not _check_website_permission(request, website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        # If user is staff (not doctor/owner), ensure all pages are approved before 1-click publish
        if not _check_doctor_permission(request, website):
            for p in website.pages.all():
                can_pub, reason = ContentApprovalService.check_can_publish(p, request.user)
                if not can_pub:
                    return Response({"error": f"Cannot publish website: '{p.title}' requires doctor approval."}, status=status.HTTP_403_FORBIDDEN)

        website.publish_all()

        return Response(
            {
                "success": True,
                "message": f"Website '{website.title}' and all pages have been published live!",
                "public_url": website.public_url,
                "published_at": website.published_at,
                "website": ClinicWebsiteSerializer(website).data,
            },
            status=status.HTTP_200_OK
        )


class WebsiteUnpublishView(APIView):
    """
    Unpublish website or put it in maintenance mode.
    POST /api/websites/<website_id>/unpublish/
    Payload: {"is_maintenance": true}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, website_id):
        website = get_object_or_404(ClinicWebsite, id=website_id)
        if not _check_website_permission(request, website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        is_maintenance = request.data.get('is_maintenance', False)
        website.is_published = False
        website.is_maintenance = is_maintenance
        website.save(update_fields=['is_published', 'is_maintenance', 'updated_at'])

        status_msg = "placed in maintenance mode" if is_maintenance else "unpublished"
        return Response(
            {
                "success": True,
                "message": f"Website has been {status_msg}.",
                "is_published": website.is_published,
                "is_maintenance": website.is_maintenance,
            },
            status=status.HTTP_200_OK
        )


# =====================================================================
# 2. PAGE MANAGEMENT & DRAFT EDITING VIEWS
# =====================================================================

class WebsitePageListCreateView(APIView):
    """
    List all pages of a website or create a new custom page.
    GET /api/websites/<website_id>/pages/
    POST /api/websites/<website_id>/pages/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, website_id):
        website = get_object_or_404(ClinicWebsite, id=website_id)
        if not _check_website_permission(request, website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        pages = website.pages.all().order_by('nav_order', 'created_at')
        serializer = WebsitePageSummarySerializer(pages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, website_id):
        website = get_object_or_404(ClinicWebsite, id=website_id)
        if not _check_website_permission(request, website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        serializer = WebsitePageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        slug = serializer.validated_data.get('slug')
        if WebsitePage.objects.filter(website=website, slug=slug).exists():
            return Response(
                {"error": f"A page with slug '/{slug}' already exists on this website."},
                status=status.HTTP_400_BAD_REQUEST
            )

        page = serializer.save(website=website, has_unpublished_changes=True)
        website.has_unpublished_changes = True
        website.save(update_fields=['has_unpublished_changes'])

        return Response(WebsitePageSerializer(page).data, status=status.HTTP_201_CREATED)


class WebsitePageDetailView(APIView):
    """
    Get, edit draft content, or delete a website page.
    GET /api/websites/<website_id>/pages/<pk>/
    PATCH /api/websites/<website_id>/pages/<pk>/
    DELETE /api/websites/<website_id>/pages/<pk>/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, website_id, pk):
        page = get_object_or_404(WebsitePage, id=pk, website_id=website_id)
        if not _check_website_permission(request, page.website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        return Response(WebsitePageSerializer(page).data, status=status.HTTP_200_OK)

    def patch(self, request, website_id, pk):
        page = get_object_or_404(WebsitePage, id=pk, website_id=website_id)
        if not _check_website_permission(request, page.website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        serializer = WebsitePageEditSerializer(page, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_page = serializer.save()

        # Update website draft state
        page.website.has_unpublished_changes = True
        page.website.save(update_fields=['has_unpublished_changes'])

        return Response(
            {
                "success": True,
                "message": "Page draft saved successfully.",
                "page": WebsitePageSerializer(updated_page).data,
            },
            status=status.HTTP_200_OK
        )

    def delete(self, request, website_id, pk):
        page = get_object_or_404(WebsitePage, id=pk, website_id=website_id)
        if not _check_website_permission(request, page.website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        if page.is_homepage:
            return Response({"error": "Homepage cannot be deleted."}, status=status.HTTP_400_BAD_REQUEST)

        page.delete()
        return Response({"success": True, "message": "Page deleted successfully."}, status=status.HTTP_200_OK)


class WebsitePagePublishView(APIView):
    """
    Publish draft changes for a specific page.
    POST /api/websites/<website_id>/pages/<pk>/publish/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, website_id, pk):
        page = get_object_or_404(WebsitePage, id=pk, website_id=website_id)
        if not _check_website_permission(request, page.website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        # Enforce Doctor Clinical Approval Gate
        can_publish, reason = ContentApprovalService.check_can_publish(page, request.user)
        if not can_publish:
            return Response({"error": reason}, status=status.HTTP_403_FORBIDDEN)

        page.publish(user=request.user)

        # Mark approval metadata as published
        approval = ContentApprovalService.get_approval_data(page)
        approval['status'] = 'published'
        approval['published_at'] = timezone.now().isoformat()
        if not isinstance(page.draft_content, dict):
            page.draft_content = {}
        page.draft_content['approval'] = approval
        page.save(update_fields=['draft_content'])

        # Check if website should be marked published
        if not page.website.is_published:
            page.website.is_published = True
            page.website.published_at = timezone.now()

        # Check if there are other pages with unpublished changes
        has_other_drafts = page.website.pages.filter(has_unpublished_changes=True).exists()
        page.website.has_unpublished_changes = has_other_drafts
        page.website.save(update_fields=['is_published', 'has_unpublished_changes', 'published_at'])

        return Response(
            {
                "success": True,
                "message": f"Page '{page.title}' published live (v{page.published_version})!",
                "page": WebsitePageSerializer(page).data,
            },
            status=status.HTTP_200_OK
        )


class WebsitePageRevisionsView(APIView):
    """
    List historical version snapshots of a page for rollback audit.
    GET /api/websites/<website_id>/pages/<pk>/revisions/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, website_id, pk):
        page = get_object_or_404(WebsitePage, id=pk, website_id=website_id)
        if not _check_website_permission(request, page.website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        revisions = page.revisions.all().order_by('-version')
        serializer = WebsitePageRevisionSerializer(revisions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class WebsitePageRevertView(APIView):
    """
    Rollback a page's draft content to a previous historical version.
    POST /api/websites/<website_id>/pages/<pk>/revert/
    Payload: {"version": 1}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, website_id, pk):
        page = get_object_or_404(WebsitePage, id=pk, website_id=website_id)
        if not _check_website_permission(request, page.website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        version = request.data.get('version')
        if version is None:
            return Response({"error": "version number is required."}, status=status.HTTP_400_BAD_REQUEST)

        success = page.revert_to_version(int(version))
        if not success:
            return Response(
                {"error": f"Revision version {version} not found for this page."},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            {
                "success": True,
                "message": f"Draft content reverted to v{version}. Review and publish when ready.",
                "page": WebsitePageSerializer(page).data,
            },
            status=status.HTTP_200_OK
        )


# =====================================================================
# 3. PREVIEW & LIVE PUBLIC RENDERING VIEWS
# =====================================================================

class WebsitePreviewView(APIView):
    """
    Preview draft website before publishing live.
    Renders draft sections, branding, and styling.
    GET /api/websites/<website_id>/preview/?slug=home
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, website_id):
        website = get_object_or_404(ClinicWebsite, id=website_id)
        if not _check_website_permission(request, website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        requested_slug = request.query_params.get('slug', 'home')
        page = website.pages.filter(slug=requested_slug).first()
        if not page and requested_slug == 'home':
            page = website.pages.filter(is_homepage=True).first()

        nav_pages = website.pages.filter(is_in_navigation=True).order_by('nav_order')

        return Response(
            {
                "preview_mode": True,
                "website": {
                    "id": str(website.id),
                    "title": website.title,
                    "tagline": website.tagline,
                    "subdomain": website.subdomain,
                    "template_style": website.template_style,
                    "primary_color": website.primary_color,
                    "secondary_color": website.secondary_color,
                    "font_family": website.font_family,
                    "logo_url": website.logo_url,
                    "header_cta_text": website.header_cta_text,
                    "header_cta_link": website.header_cta_link,
                    "footer_text": website.footer_text,
                    "contact_phone": website.contact_phone,
                    "contact_email": website.contact_email,
                    "whatsapp_number": website.whatsapp_number,
                },
                "navigation": [
                    {"title": p.title, "slug": p.slug, "is_homepage": p.is_homepage}
                    for p in nav_pages
                ],
                "active_page": {
                    "id": str(page.id) if page else None,
                    "title": page.title if page else "Not Found",
                    "slug": page.slug if page else requested_slug,
                    "content": page.draft_content if page else {},
                    "has_unpublished_changes": page.has_unpublished_changes if page else False,
                }
            },
            status=status.HTTP_200_OK
        )


class PublicWebsiteRenderView(APIView):
    """
    Public live visitor rendering endpoint.
    Resolves website via subdomain or custom domain and returns strictly published content.
    GET /api/websites/public/<domain_or_subdomain>/?slug=home
    """
    permission_classes = [AllowAny]

    def get(self, request, domain_or_subdomain):
        clean_target = domain_or_subdomain.lower().strip()

        # Check by custom domain first
        custom_domain = CustomDomain.objects.filter(
            domain=clean_target,
            status=CustomDomain.STATUS_ACTIVE
        ).select_related('website').first()

        if custom_domain:
            website = custom_domain.website
        else:
            # Check by subdomain
            website = ClinicWebsite.objects.filter(subdomain=clean_target).first()

        if not website:
            return Response(
                {"error": "Clinic website not found.", "code": "WEBSITE_NOT_FOUND"},
                status=status.HTTP_404_NOT_FOUND
            )

        if website.is_maintenance:
            return Response(
                {
                    "is_maintenance": True,
                    "title": website.title,
                    "message": "Our website is currently undergoing scheduled maintenance. Please check back shortly.",
                    "contact_phone": website.contact_phone,
                    "contact_email": website.contact_email,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        if not website.is_published:
            return Response(
                {"error": "This clinic website is not yet published.", "code": "NOT_PUBLISHED"},
                status=status.HTTP_404_NOT_FOUND
            )

        requested_slug = request.query_params.get('slug', 'home')
        page = website.pages.filter(slug=requested_slug, is_published=True).first()
        if not page and requested_slug == 'home':
            page = website.pages.filter(is_homepage=True, is_published=True).first()

        if not page:
            return Response(
                {"error": f"Page '/{requested_slug}' not found on this website."},
                status=status.HTTP_404_NOT_FOUND
            )

        nav_pages = website.pages.filter(is_in_navigation=True, is_published=True).order_by('nav_order')

        return Response(
            {
                "website": {
                    "id": str(website.id),
                    "title": website.title,
                    "tagline": website.tagline,
                    "template_style": website.template_style,
                    "primary_color": website.primary_color,
                    "secondary_color": website.secondary_color,
                    "font_family": website.font_family,
                    "logo_url": website.logo_url,
                    "favicon_url": website.favicon_url,
                    "header_cta_text": website.header_cta_text,
                    "header_cta_link": website.header_cta_link,
                    "footer_text": website.footer_text,
                    "contact_phone": website.contact_phone,
                    "contact_email": website.contact_email,
                    "whatsapp_number": website.whatsapp_number,
                    "emergency_contact": website.emergency_contact,
                    "google_maps_url": website.google_maps_url,
                    "google_analytics_id": website.google_analytics_id,
                },
                "seo": {
                    "meta_title": page.meta_title or website.meta_title or website.title,
                    "meta_description": page.meta_description or website.meta_description,
                    "og_image_url": website.og_image_url,
                },
                "navigation": [
                    {"title": p.title, "slug": p.slug, "is_homepage": p.is_homepage}
                    for p in nav_pages
                ],
                "page": {
                    "id": str(page.id),
                    "title": page.title,
                    "slug": page.slug,
                    "is_homepage": page.is_homepage,
                    "content": page.published_content,
                    "published_at": page.published_at,
                }
            },
            status=status.HTTP_200_OK
        )


class PublicWebsiteInquiryView(APIView):
    """
    Public lead capture endpoint for patient inquiries submitted through the website.
    POST /api/websites/public/<domain_or_subdomain>/inquire/
    Payload: {"patient_name": "Ravi Kumar", "phone_number": "+919876543210", "email": "ravi@gmail.com", "message": "Book dental cleaning"}
    """
    permission_classes = [AllowAny]

    def post(self, request, domain_or_subdomain):
        clean_target = domain_or_subdomain.lower().strip()
        custom_domain = CustomDomain.objects.filter(domain=clean_target, status=CustomDomain.STATUS_ACTIVE).select_related('website').first()
        website = custom_domain.website if custom_domain else ClinicWebsite.objects.filter(subdomain=clean_target).first()

        if not website:
            return Response({"error": "Website not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = WebsiteInquirySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        inquiry = serializer.save(website=website)

        # Seamlessly sync with the unified ClinicRise Lead Inbox & Consent tracker
        try:
            from leads.services.lead_service import LeadService
            LeadService.create_lead_from_enquiry(
                practice=website.practice,
                data=serializer.validated_data,
                request=request,
                website=website
            )
        except Exception:
            pass

        return Response(
            {
                "success": True,
                "message": "Thank you! Your appointment request has been submitted to the clinic team.",
                "inquiry_id": str(inquiry.id),
            },
            status=status.HTTP_201_CREATED
        )


# =====================================================================
# 4. CUSTOM DOMAIN MANAGEMENT VIEWS
# =====================================================================

class CustomDomainListCreateView(APIView):
    """
    List connected domains or add a custom domain to a clinic website.
    GET /api/websites/<website_id>/domains/
    POST /api/websites/<website_id>/domains/
    Payload: {"domain": "www.citydentalcare.com"}
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, website_id):
        website = get_object_or_404(ClinicWebsite, id=website_id)
        if not _check_website_permission(request, website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        domains = website.custom_domains.all()
        serializer = CustomDomainSerializer(domains, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, website_id):
        website = get_object_or_404(ClinicWebsite, id=website_id)
        if not _check_website_permission(request, website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        serializer = CustomDomainSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        domain_name = serializer.validated_data['domain']

        if CustomDomain.objects.filter(domain=domain_name).exists():
            return Response(
                {"error": f"The domain '{domain_name}' is already connected to a website."},
                status=status.HTTP_400_BAD_REQUEST
            )

        custom_domain = serializer.save(website=website)

        return Response(
            {
                "success": True,
                "message": f"Domain '{domain_name}' added. Please configure the DNS records shown below.",
                "domain": CustomDomainSerializer(custom_domain).data,
            },
            status=status.HTTP_201_CREATED
        )


class CustomDomainDetailView(APIView):
    """
    View or disconnect a custom domain.
    GET /api/websites/<website_id>/domains/<pk>/
    DELETE /api/websites/<website_id>/domains/<pk>/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, website_id, pk):
        domain = get_object_or_404(CustomDomain, id=pk, website_id=website_id)
        if not _check_website_permission(request, domain.website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        return Response(CustomDomainSerializer(domain).data, status=status.HTTP_200_OK)

    def delete(self, request, website_id, pk):
        domain = get_object_or_404(CustomDomain, id=pk, website_id=website_id)
        if not _check_website_permission(request, domain.website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        domain.delete()
        return Response({"success": True, "message": "Domain disconnected successfully."}, status=status.HTTP_200_OK)


class CustomDomainVerifyView(APIView):
    """
    Trigger DNS verification and SSL certificate provisioning for a custom domain.
    POST /api/websites/<website_id>/domains/<pk>/verify/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, website_id, pk):
        domain = get_object_or_404(CustomDomain, id=pk, website_id=website_id)
        if not _check_website_permission(request, domain.website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        force_simulate = request.data.get('simulate', True)
        verified, message = DomainVerificationService.verify_domain(domain, force_simulate=force_simulate)

        return Response(
            {
                "success": verified,
                "message": message,
                "domain": CustomDomainSerializer(domain).data,
            },
            status=status.HTTP_200_OK if verified else status.HTTP_400_BAD_REQUEST
        )


class CustomDomainSetPrimaryView(APIView):
    """
    Set a verified custom domain as the primary domain for the website.
    POST /api/websites/<website_id>/domains/<pk>/set-primary/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, website_id, pk):
        domain = get_object_or_404(CustomDomain, id=pk, website_id=website_id)
        if not _check_website_permission(request, domain.website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        domain.is_primary = True
        domain.save()

        return Response(
            {
                "success": True,
                "message": f"'{domain.domain}' is now the primary live domain for this website.",
                "domain": CustomDomainSerializer(domain).data,
            },
            status=status.HTTP_200_OK
        )


# =====================================================================
# 5. WEBSITE INQUIRIES VIEWS
# =====================================================================

class WebsiteInquiryListView(APIView):
    """
    List patient appointment inquiries received through the website.
    GET /api/websites/<website_id>/inquiries/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, website_id):
        website = get_object_or_404(ClinicWebsite, id=website_id)
        if not _check_website_permission(request, website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        inquiries = website.inquiries.all().order_by('-created_at')
        serializer = WebsiteInquirySerializer(inquiries, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class WebsiteInquiryDetailView(APIView):
    """
    View or mark patient inquiry as read.
    PATCH /api/websites/<website_id>/inquiries/<pk>/
    DELETE /api/websites/<website_id>/inquiries/<pk>/
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, website_id, pk):
        inquiry = get_object_or_404(WebsiteInquiry, id=pk, website_id=website_id)
        if not _check_website_permission(request, inquiry.website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        is_read = request.data.get('is_read', True)
        inquiry.is_read = is_read
        inquiry.save(update_fields=['is_read'])
        return Response(WebsiteInquirySerializer(inquiry).data, status=status.HTTP_200_OK)

    def delete(self, request, website_id, pk):
        inquiry = get_object_or_404(WebsiteInquiry, id=pk, website_id=website_id)
        if not _check_website_permission(request, inquiry.website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        inquiry.delete()
        return Response({"success": True, "message": "Inquiry removed."}, status=status.HTTP_200_OK)


# =====================================================================
# 6. CONTENT APPROVALS & DOCTOR CLINICAL REVIEW VIEWS
# =====================================================================

class PageSubmitReviewView(APIView):
    """
    Staff / Author submits page changes for doctor review before publication.
    POST /api/websites/<website_id>/pages/<pk>/submit-review/
    Payload: {"submission_notes": "Updated treatment pricing and added new laser therapy section."}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, website_id, pk):
        page = get_object_or_404(WebsitePage, id=pk, website_id=website_id)
        if not _check_member_permission(request, page.website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        serializer = SubmitReviewRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        notes = serializer.validated_data.get('submission_notes', '')

        updated_page = ContentApprovalService.submit_for_review(page, request.user, submission_notes=notes)

        return Response(
            {
                "success": True,
                "message": f"Draft changes for '{page.title}' have been submitted for doctor review.",
                "approval_status": ContentApprovalService.STATUS_PENDING,
                "page": WebsitePageSerializer(updated_page).data,
            },
            status=status.HTTP_200_OK
        )


class PageDoctorReviewView(APIView):
    """
    Doctor reviews and approves or requests changes on page draft changes.
    POST /api/websites/<website_id>/pages/<pk>/review/
    Payload:
    {
        "action": "approve" | "request_changes",
        "review_notes": "Medically verified. Approved for live publication."
    }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, website_id, pk):
        page = get_object_or_404(WebsitePage, id=pk, website_id=website_id)
        if not _check_doctor_permission(request, page.website):
            return Response(
                {"error": "Only verified medical doctors or practice owners can review and approve clinical content."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = DoctorReviewActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action = serializer.validated_data['action']
        review_notes = serializer.validated_data.get('review_notes', '')

        updated_page = ContentApprovalService.review_content(
            page=page,
            doctor_user=request.user,
            action=action,
            review_notes=review_notes
        )

        approval_data = ContentApprovalService.get_approval_data(updated_page)
        action_msg = "approved for publication" if action == 'approve' else "returned with requested changes"

        return Response(
            {
                "success": True,
                "message": f"Content {action_msg}.",
                "approval_status": approval_data['status'],
                "approval": approval_data,
                "page": WebsitePageSerializer(updated_page).data,
            },
            status=status.HTTP_200_OK
        )


class ApprovalQueueView(APIView):
    """
    Unified Doctor & Admin Review Dashboard / Queue.
    Lists all website pages and blog drafts awaiting doctor review.
    GET /api/websites/<website_id>/approvals/
    Query params: ?status=pending_approval | approved | changes_requested
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, website_id):
        website = get_object_or_404(ClinicWebsite, id=website_id)
        if not _check_member_permission(request, website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        status_filter = request.query_params.get('status')
        queue_data = ContentApprovalService.get_approval_queue(website, status_filter=status_filter)
        return Response(queue_data, status=status.HTTP_200_OK)


# =====================================================================
# 7. BLOG MANAGEMENT & CLINICAL HEALTH ARTICLES
# =====================================================================

class BlogListCreateView(APIView):
    """
    List blog posts or create a new blog article draft.
    GET /api/websites/<website_id>/blogs/
    POST /api/websites/<website_id>/blogs/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, website_id):
        website = get_object_or_404(ClinicWebsite, id=website_id)
        if not _check_member_permission(request, website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        status_filter = request.query_params.get('status')
        blogs = ContentApprovalService.list_blogs(website, status_filter=status_filter)
        return Response(blogs, status=status.HTTP_200_OK)

    def post(self, request, website_id):
        website = get_object_or_404(ClinicWebsite, id=website_id)
        if not _check_member_permission(request, website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        serializer = BlogPostCreateUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        page = ContentApprovalService.create_blog(
            website=website,
            author_user=request.user,
            data=serializer.validated_data
        )

        return Response(
            {
                "success": True,
                "message": f"Blog post draft '{page.title}' created.",
                "blog": {
                    "id": str(page.id),
                    "title": page.title,
                    "slug": page.slug,
                    "draft_content": page.draft_content,
                    "approval": ContentApprovalService.get_approval_data(page),
                }
            },
            status=status.HTTP_201_CREATED
        )


class BlogDetailView(APIView):
    """
    Retrieve, update or delete a blog post draft.
    GET /api/websites/<website_id>/blogs/<pk_or_slug>/
    PATCH /api/websites/<website_id>/blogs/<pk_or_slug>/
    DELETE /api/websites/<website_id>/blogs/<pk_or_slug>/
    """
    permission_classes = [IsAuthenticated]

    def _get_blog_page(self, website, pk_or_slug):
        import uuid
        try:
            val_uuid = uuid.UUID(pk_or_slug)
            return get_object_or_404(WebsitePage, id=val_uuid, website=website)
        except (ValueError, TypeError):
            target_slug = f"blog/{pk_or_slug}" if not pk_or_slug.startswith('blog/') else pk_or_slug
            return get_object_or_404(WebsitePage, slug=target_slug, website=website)

    def get(self, request, website_id, pk_or_slug):
        website = get_object_or_404(ClinicWebsite, id=website_id)
        if not _check_member_permission(request, website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        page = self._get_blog_page(website, pk_or_slug)
        draft = page.draft_content if isinstance(page.draft_content, dict) else {}
        return Response({
            "id": str(page.id),
            "title": page.title,
            "slug": page.slug,
            "category": draft.get('category', 'General Healthcare'),
            "excerpt": draft.get('excerpt', ''),
            "body_html": draft.get('body_html', ''),
            "cover_image_url": draft.get('cover_image_url', ''),
            "author_doctor_name": draft.get('author_doctor_name', ''),
            "read_time_minutes": draft.get('read_time_minutes', 4),
            "tags": draft.get('tags', []),
            "approval": ContentApprovalService.get_approval_data(page),
            "is_published": page.is_published,
            "has_unpublished_changes": page.has_unpublished_changes,
            "published_at": page.published_at,
            "created_at": page.created_at,
            "updated_at": page.updated_at,
        }, status=status.HTTP_200_OK)

    def patch(self, request, website_id, pk_or_slug):
        website = get_object_or_404(ClinicWebsite, id=website_id)
        if not _check_member_permission(request, website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        page = self._get_blog_page(website, pk_or_slug)
        serializer = BlogPostCreateUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        draft = dict(page.draft_content) if isinstance(page.draft_content, dict) else {}
        for k in ['category', 'excerpt', 'body_html', 'cover_image_url', 'author_doctor_name', 'tags', 'read_time_minutes']:
            if k in serializer.validated_data:
                draft[k] = serializer.validated_data[k]

        if 'title' in serializer.validated_data:
            page.title = serializer.validated_data['title']

        # Any content edit resets approval to draft so doctor must sign off on modified text
        approval = ContentApprovalService.get_approval_data(page)
        if approval.get('status') in [ContentApprovalService.STATUS_APPROVED, ContentApprovalService.STATUS_PENDING]:
            approval['status'] = ContentApprovalService.STATUS_DRAFT
            history = approval.get('history', [])
            history.append({
                'action': 'edited_after_review',
                'user': getattr(request.user, 'full_name', str(request.user)),
                'timestamp': timezone.now().isoformat(),
                'notes': 'Draft edited. Re-approval required.'
            })
            approval['history'] = history
        draft['approval'] = approval

        page.draft_content = draft
        page.has_unpublished_changes = True
        page.save(update_fields=['title', 'draft_content', 'has_unpublished_changes', 'updated_at'])

        return Response({
            "success": True,
            "message": "Blog post updated.",
            "approval_status": approval['status'],
            "blog": {
                "id": str(page.id),
                "title": page.title,
                "slug": page.slug,
                "approval": approval,
            }
        }, status=status.HTTP_200_OK)

    def delete(self, request, website_id, pk_or_slug):
        website = get_object_or_404(ClinicWebsite, id=website_id)
        if not _check_website_permission(request, website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        page = self._get_blog_page(website, pk_or_slug)
        page.delete()
        return Response({"success": True, "message": "Blog post deleted."}, status=status.HTTP_200_OK)


class BlogSubmitReviewView(APIView):
    """
    Submit blog post draft for doctor clinical review.
    POST /api/websites/<website_id>/blogs/<pk_or_slug>/submit-review/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, website_id, pk_or_slug):
        website = get_object_or_404(ClinicWebsite, id=website_id)
        if not _check_member_permission(request, website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        blog_view = BlogDetailView()
        page = blog_view._get_blog_page(website, pk_or_slug)

        serializer = SubmitReviewRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        notes = serializer.validated_data.get('submission_notes', '')

        updated_page = ContentApprovalService.submit_for_review(page, request.user, submission_notes=notes)

        return Response({
            "success": True,
            "message": f"Blog post '{page.title}' submitted for doctor review.",
            "approval_status": ContentApprovalService.STATUS_PENDING,
            "approval": ContentApprovalService.get_approval_data(updated_page),
        }, status=status.HTTP_200_OK)


class BlogDoctorReviewView(APIView):
    """
    Doctor reviews and approves or requests revisions on a blog post.
    POST /api/websites/<website_id>/blogs/<pk_or_slug>/review/
    Payload:
    {
        "action": "approve" | "request_changes",
        "review_notes": "Medically verified advice regarding dental hygiene."
    }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, website_id, pk_or_slug):
        website = get_object_or_404(ClinicWebsite, id=website_id)
        if not _check_doctor_permission(request, website):
            return Response(
                {"error": "Only verified doctors or practice owners can review and approve medical blog posts."},
                status=status.HTTP_403_FORBIDDEN
            )

        blog_view = BlogDetailView()
        page = blog_view._get_blog_page(website, pk_or_slug)

        serializer = DoctorReviewActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action = serializer.validated_data['action']
        review_notes = serializer.validated_data.get('review_notes', '')

        updated_page = ContentApprovalService.review_content(
            page=page,
            doctor_user=request.user,
            action=action,
            review_notes=review_notes
        )

        approval = ContentApprovalService.get_approval_data(updated_page)
        action_msg = "approved for publication" if action == 'approve' else "returned with requested revisions"

        return Response({
            "success": True,
            "message": f"Blog article {action_msg}.",
            "approval_status": approval['status'],
            "approval": approval,
        }, status=status.HTTP_200_OK)


class BlogPublishView(APIView):
    """
    Publish an approved blog article live to the clinic website.
    POST /api/websites/<website_id>/blogs/<pk_or_slug>/publish/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, website_id, pk_or_slug):
        website = get_object_or_404(ClinicWebsite, id=website_id)
        if not _check_website_permission(request, website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        blog_view = BlogDetailView()
        page = blog_view._get_blog_page(website, pk_or_slug)

        can_pub, reason = ContentApprovalService.check_can_publish(page, request.user)
        if not can_pub:
            return Response({"error": reason}, status=status.HTTP_403_FORBIDDEN)

        page.publish(user=request.user)

        # Update approval status to published
        approval = ContentApprovalService.get_approval_data(page)
        approval['status'] = 'published'
        approval['published_at'] = timezone.now().isoformat()
        if not isinstance(page.draft_content, dict):
            page.draft_content = {}
        page.draft_content['approval'] = approval
        page.save(update_fields=['draft_content'])

        return Response({
            "success": True,
            "message": f"Blog post '{page.title}' published live!",
            "public_slug": page.slug,
            "published_at": page.published_at,
        }, status=status.HTTP_200_OK)


class PublicBlogListView(APIView):
    """
    Public endpoint: List all published blog articles on a clinic website.
    GET /api/websites/public/<domain_or_subdomain>/blogs/
    """
    permission_classes = [AllowAny]

    def get(self, request, domain_or_subdomain):
        clean_target = domain_or_subdomain.lower().strip()
        custom_domain = CustomDomain.objects.filter(domain=clean_target, status=CustomDomain.STATUS_ACTIVE).select_related('website').first()
        website = custom_domain.website if custom_domain else ClinicWebsite.objects.filter(subdomain=clean_target).first()

        if not website:
            return Response({"error": "Website not found."}, status=status.HTTP_404_NOT_FOUND)

        pages = website.pages.filter(is_published=True).order_by('-published_at')
        published_blogs = []

        for p in pages:
            content = p.published_content if isinstance(p.published_content, dict) else {}
            if content.get('content_type') == 'blog_post' or p.slug.startswith('blog/'):
                published_blogs.append({
                    "id": str(p.id),
                    "title": p.title,
                    "slug": p.slug.replace('blog/', ''),
                    "category": content.get('category', 'General Healthcare'),
                    "excerpt": content.get('excerpt', ''),
                    "cover_image_url": content.get('cover_image_url', ''),
                    "author_doctor_name": content.get('author_doctor_name', ''),
                    "read_time_minutes": content.get('read_time_minutes', 4),
                    "tags": content.get('tags', []),
                    "published_at": p.published_at,
                })

        return Response({
            "website_title": website.title,
            "subdomain": website.subdomain,
            "blogs_count": len(published_blogs),
            "blogs": published_blogs,
        }, status=status.HTTP_200_OK)


class PublicBlogDetailView(APIView):
    """
    Public endpoint: Read a single published blog article by slug.
    GET /api/websites/public/<domain_or_subdomain>/blogs/<slug>/
    """
    permission_classes = [AllowAny]

    def get(self, request, domain_or_subdomain, slug):
        clean_target = domain_or_subdomain.lower().strip()
        custom_domain = CustomDomain.objects.filter(domain=clean_target, status=CustomDomain.STATUS_ACTIVE).select_related('website').first()
        website = custom_domain.website if custom_domain else ClinicWebsite.objects.filter(subdomain=clean_target).first()

        if not website:
            return Response({"error": "Website not found."}, status=status.HTTP_404_NOT_FOUND)

        target_slug = f"blog/{slug}" if not slug.startswith('blog/') else slug
        page = WebsitePage.objects.filter(website=website, slug=target_slug, is_published=True).first()
        if not page:
            # Also try raw slug
            page = WebsitePage.objects.filter(website=website, slug=slug, is_published=True).first()

        if not page:
            return Response({"error": "Blog post not found or not published."}, status=status.HTTP_404_NOT_FOUND)

        content = page.published_content if isinstance(page.published_content, dict) else {}

        return Response({
            "id": str(page.id),
            "title": page.title,
            "slug": page.slug.replace('blog/', ''),
            "category": content.get('category', 'General Healthcare'),
            "excerpt": content.get('excerpt', ''),
            "body_html": content.get('body_html', ''),
            "cover_image_url": content.get('cover_image_url', ''),
            "author_doctor_name": content.get('author_doctor_name', ''),
            "read_time_minutes": content.get('read_time_minutes', 4),
            "tags": content.get('tags', []),
            "published_at": page.published_at,
            "website": {
                "title": website.title,
                "subdomain": website.subdomain,
                "phone": website.contact_phone,
                "booking_link": website.header_cta_link,
            }
        }, status=status.HTTP_200_OK)


class WebsiteAnalyticsView(APIView):
    """
    Direct endpoint for fetching analytics for a specific ClinicWebsite.
    GET /api/websites/<website_id>/analytics/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, website_id):
        website = get_object_or_404(ClinicWebsite, id=website_id)
        if not _check_website_permission(request, website):
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        from analytics.serializers import AnalyticsQueryParamSerializer
        from analytics.services.analytics_service import AnalyticsService

        param_serializer = AnalyticsQueryParamSerializer(data=request.query_params)
        param_serializer.is_valid(raise_exception=True)
        validated = param_serializer.validated_data

        overview = AnalyticsService.get_analytics_overview(
            practice=website.practice,
            website=website,
            preset=validated.get('preset', '30d'),
            date_from=str(validated['date_from']) if validated.get('date_from') else None,
            date_to=str(validated['date_to']) if validated.get('date_to') else None,
        )
        return Response(overview, status=status.HTTP_200_OK)

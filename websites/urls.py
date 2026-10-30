from django.urls import path

from websites.views import (
    ApprovalQueueView,
    BlogDetailView,
    BlogDoctorReviewView,
    BlogListCreateView,
    BlogPublishView,
    BlogSubmitReviewView,
    CustomDomainDetailView,
    CustomDomainListCreateView,
    CustomDomainSetPrimaryView,
    CustomDomainVerifyView,
    PageDoctorReviewView,
    PageSubmitReviewView,
    PublicBlogDetailView,
    PublicBlogListView,
    PublicWebsiteInquiryView,
    PublicWebsiteRenderView,
    WebsiteAnalyticsView,
    WebsiteCurrentView,
    WebsiteDetailView,
    WebsiteGenerateView,
    WebsiteInquiryDetailView,
    WebsiteInquiryListView,
    WebsitePageDetailView,
    WebsitePageListCreateView,
    WebsitePagePublishView,
    WebsitePageRevertView,
    WebsitePageRevisionsView,
    WebsitePreviewView,
    WebsitePublishView,
    WebsiteUnpublishView,
)

app_name = 'websites'

urlpatterns = [
    # ---------------------------------------------------------
    # Current Tenant Website & Auto-Generation
    # ---------------------------------------------------------
    path('current/', WebsiteCurrentView.as_view(), name='website_current'),
    path('generate/', WebsiteGenerateView.as_view(), name='website_generate'),

    # ---------------------------------------------------------
    # Unified Content Approval Queue for Doctors
    # ---------------------------------------------------------
    path('<uuid:website_id>/approvals/', ApprovalQueueView.as_view(), name='approval_queue'),

    # ---------------------------------------------------------
    # Website Settings, Publishing & Live Previews
    # ---------------------------------------------------------
    path('<uuid:website_id>/', WebsiteDetailView.as_view(), name='website_detail'),
    path('<uuid:website_id>/analytics/', WebsiteAnalyticsView.as_view(), name='website_analytics'),
    path('<uuid:website_id>/publish/', WebsitePublishView.as_view(), name='website_publish'),
    path('<uuid:website_id>/unpublish/', WebsiteUnpublishView.as_view(), name='website_unpublish'),
    path('<uuid:website_id>/preview/', WebsitePreviewView.as_view(), name='website_preview'),

    # ---------------------------------------------------------
    # Page Management, Draft Editing & Content Approvals
    # ---------------------------------------------------------
    path('<uuid:website_id>/pages/', WebsitePageListCreateView.as_view(), name='page_list_create'),
    path('<uuid:website_id>/pages/<uuid:pk>/', WebsitePageDetailView.as_view(), name='page_detail'),
    path('<uuid:website_id>/pages/<uuid:pk>/submit-review/', PageSubmitReviewView.as_view(), name='page_submit_review'),
    path('<uuid:website_id>/pages/<uuid:pk>/review/', PageDoctorReviewView.as_view(), name='page_doctor_review'),
    path('<uuid:website_id>/pages/<uuid:pk>/publish/', WebsitePagePublishView.as_view(), name='page_publish'),
    path('<uuid:website_id>/pages/<uuid:pk>/revisions/', WebsitePageRevisionsView.as_view(), name='page_revisions'),
    path('<uuid:website_id>/pages/<uuid:pk>/revert/', WebsitePageRevertView.as_view(), name='page_revert'),

    # ---------------------------------------------------------
    # Blog Management, Drafts & Doctor Clinical Reviews
    # ---------------------------------------------------------
    path('<uuid:website_id>/blogs/', BlogListCreateView.as_view(), name='blog_list_create'),
    path('<uuid:website_id>/blogs/<str:pk_or_slug>/', BlogDetailView.as_view(), name='blog_detail'),
    path('<uuid:website_id>/blogs/<str:pk_or_slug>/submit-review/', BlogSubmitReviewView.as_view(), name='blog_submit_review'),
    path('<uuid:website_id>/blogs/<str:pk_or_slug>/review/', BlogDoctorReviewView.as_view(), name='blog_doctor_review'),
    path('<uuid:website_id>/blogs/<str:pk_or_slug>/publish/', BlogPublishView.as_view(), name='blog_publish'),

    # ---------------------------------------------------------
    # Custom Domains & DNS Routing
    # ---------------------------------------------------------
    path('<uuid:website_id>/domains/', CustomDomainListCreateView.as_view(), name='domain_list_create'),
    path('<uuid:website_id>/domains/<uuid:pk>/', CustomDomainDetailView.as_view(), name='domain_detail'),
    path('<uuid:website_id>/domains/<uuid:pk>/verify/', CustomDomainVerifyView.as_view(), name='domain_verify'),
    path('<uuid:website_id>/domains/<uuid:pk>/set-primary/', CustomDomainSetPrimaryView.as_view(), name='domain_set_primary'),

    # ---------------------------------------------------------
    # Patient Inquiries (Leads & Booking Requests)
    # ---------------------------------------------------------
    path('<uuid:website_id>/inquiries/', WebsiteInquiryListView.as_view(), name='inquiry_list'),
    path('<uuid:website_id>/inquiries/<uuid:pk>/', WebsiteInquiryDetailView.as_view(), name='inquiry_detail'),

    # ---------------------------------------------------------
    # Public Live Website & Blog Articles
    # ---------------------------------------------------------
    path('public/<str:domain_or_subdomain>/', PublicWebsiteRenderView.as_view(), name='public_website_render'),
    path('public/<str:domain_or_subdomain>/blogs/', PublicBlogListView.as_view(), name='public_blog_list'),
    path('public/<str:domain_or_subdomain>/blogs/<str:slug>/', PublicBlogDetailView.as_view(), name='public_blog_detail'),
    path('public/<str:domain_or_subdomain>/inquire/', PublicWebsiteInquiryView.as_view(), name='public_website_inquire'),
]

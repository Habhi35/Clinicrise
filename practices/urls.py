from django.urls import path

from practices.views import (
    AcceptInvitationView,
    CurrentPracticeView,
    DoctorOnboardingCompleteView,
    DoctorOnboardingFileUploadView,
    DoctorOnboardingProgressView,
    DoctorOnboardingSaveDraftView,
    DoctorOnboardingStepClinicView,
    DoctorOnboardingStepImagesView,
    DoctorOnboardingStepProfileView,
    DoctorOnboardingStepServicesView,
    DoctorOnboardingStepTimingsView,
    DoctorProfileView,
    DoctorScheduleDetailView,
    DoctorScheduleListCreateView,
    InviteMemberView,
    PracticeDetailView,
    PracticeDoctorListView,
    PracticeImageDetailView,
    PracticeImageListCreateView,
    PracticeListCreateView,
    PracticeMemberDetailView,
    PracticeMemberListCreateView,
    PracticeRoleMatrixView,
    PracticeServiceDetailView,
    PracticeServiceListCreateView,
)

app_name = 'practices'

urlpatterns = [
    # ---------------------------------------------------------
    # Doctor Onboarding Wizard & Saved Progress
    # ---------------------------------------------------------
    path('onboarding/progress/', DoctorOnboardingProgressView.as_view(), name='onboarding_progress'),
    path('onboarding/draft/', DoctorOnboardingSaveDraftView.as_view(), name='onboarding_save_draft'),
    path('onboarding/step/doctor-profile/', DoctorOnboardingStepProfileView.as_view(), name='onboarding_step_profile'),
    path('onboarding/step/clinic-details/', DoctorOnboardingStepClinicView.as_view(), name='onboarding_step_clinic'),
    path('onboarding/step/services/', DoctorOnboardingStepServicesView.as_view(), name='onboarding_step_services'),
    path('onboarding/step/timings/', DoctorOnboardingStepTimingsView.as_view(), name='onboarding_step_timings'),
    path('onboarding/step/images/', DoctorOnboardingStepImagesView.as_view(), name='onboarding_step_images'),
    path('onboarding/complete/', DoctorOnboardingCompleteView.as_view(), name='onboarding_complete'),
    path('onboarding/upload/', DoctorOnboardingFileUploadView.as_view(), name='onboarding_upload'),

    # ---------------------------------------------------------
    # Practice CRUD & Active Context
    # ---------------------------------------------------------
    path('', PracticeListCreateView.as_view(), name='practice_list_create'),
    path('current/', CurrentPracticeView.as_view(), name='practice_current'),
    path('<uuid:pk>/', PracticeDetailView.as_view(), name='practice_detail'),

    # ---------------------------------------------------------
    # Practice Clinical Services
    # ---------------------------------------------------------
    path('<uuid:practice_id>/services/', PracticeServiceListCreateView.as_view(), name='practice_services'),
    path('<uuid:practice_id>/services/<uuid:pk>/', PracticeServiceDetailView.as_view(), name='practice_service_detail'),

    # ---------------------------------------------------------
    # Doctor Schedule & Clinic Timings
    # ---------------------------------------------------------
    path('<uuid:practice_id>/timings/', DoctorScheduleListCreateView.as_view(), name='practice_timings'),
    path('<uuid:practice_id>/timings/<uuid:pk>/', DoctorScheduleDetailView.as_view(), name='practice_timing_detail'),

    # ---------------------------------------------------------
    # Clinic Photos & Images
    # ---------------------------------------------------------
    path('<uuid:practice_id>/images/', PracticeImageListCreateView.as_view(), name='practice_images'),
    path('<uuid:practice_id>/images/<uuid:pk>/', PracticeImageDetailView.as_view(), name='practice_image_detail'),

    # ---------------------------------------------------------
    path('roles/', PracticeRoleMatrixView.as_view(), name='practice_roles'),
    path('<uuid:practice_id>/members/', PracticeMemberListCreateView.as_view(), name='practice_members'),
    path('<uuid:practice_id>/invite/', InviteMemberView.as_view(), name='practice_invite'),
    path('<uuid:practice_id>/members/<uuid:pk>/', PracticeMemberDetailView.as_view(), name='practice_member_detail'),
    path('<uuid:practice_id>/doctors/', PracticeDoctorListView.as_view(), name='practice_doctors'),

    # ---------------------------------------------------------
    # Doctor Account / Profile Management
    # ---------------------------------------------------------
    path('doctor/profile/', DoctorProfileView.as_view(), name='doctor_profile'),

    # ---------------------------------------------------------
    # Invitations Acceptance
    # ---------------------------------------------------------
    path('invitations/accept/', AcceptInvitationView.as_view(), name='invitation_accept'),
]

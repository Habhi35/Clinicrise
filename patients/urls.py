from django.urls import path
from patients.views import (
    ConvertLeadToPatientView,
    PatientCRMOverviewView,
    PatientDetailView,
    PatientFollowUpCompleteView,
    PatientFollowUpListCreateView,
    PatientListCreateView,
    PatientLogCallView,
    PatientNoteListCreateView,
    PatientNotePinToggleView,
    PatientTimelineListView,
    PatientVitalsListCreateView,
    PracticeFollowUpQueueView,
)

app_name = 'patients'

urlpatterns = [
    # CRM Overview & Global Queue
    path('overview/', PatientCRMOverviewView.as_view(), name='crm_overview'),
    path('follow-ups/', PracticeFollowUpQueueView.as_view(), name='practice_followups'),
    path('follow-ups/<uuid:pk>/complete/', PatientFollowUpCompleteView.as_view(), name='followup_complete'),
    path('convert-lead/<uuid:lead_id>/', ConvertLeadToPatientView.as_view(), name='convert_lead'),

    # Patient Directory CRUD
    path('', PatientListCreateView.as_view(), name='patient_list_create'),
    path('<uuid:pk>/', PatientDetailView.as_view(), name='patient_detail'),

    # Patient Chart Sub-Resources
    path('<uuid:pk>/timeline/', PatientTimelineListView.as_view(), name='patient_timeline'),
    path('<uuid:pk>/notes/', PatientNoteListCreateView.as_view(), name='patient_notes'),
    path('<uuid:pk>/notes/<uuid:note_id>/pin/', PatientNotePinToggleView.as_view(), name='patient_note_pin_toggle'),
    path('<uuid:pk>/vitals/', PatientVitalsListCreateView.as_view(), name='patient_vitals'),
    path('<uuid:pk>/log-call/', PatientLogCallView.as_view(), name='patient_log_call'),
    path('<uuid:pk>/follow-ups/', PatientFollowUpListCreateView.as_view(), name='patient_followups'),
]

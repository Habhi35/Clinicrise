from django.urls import path
from whatsapp.views import (
    WhatsAppConfigView,
    WhatsAppTemplateListCreateView,
    WhatsAppTemplateDetailView,
    WhatsAppTemplatePreviewView,
    WhatsAppTemplateSeedDefaultsView,
    WhatsAppOptOutListView,
    WhatsAppOptInView,
    WhatsAppOptOutCheckView,
    WhatsAppReminderListView,
    WhatsAppReminderCancelView,
    WhatsAppReminderProcessNowView,
    WhatsAppMessageLogListView,
    WhatsAppMessageLogDetailView,
    WhatsAppMessageRetryView,
    WhatsAppAnalyticsView,
    WhatsAppTestSendView,
    WhatsAppWebhookView,
)

app_name = 'whatsapp'

urlpatterns = [
    # 1. WhatsApp Business Gateway Configuration
    path('config/', WhatsAppConfigView.as_view(), name='config'),

    # 2. Pre-approved & Custom Clinical Templates
    path('templates/', WhatsAppTemplateListCreateView.as_view(), name='template_list_create'),
    path('templates/<uuid:pk>/', WhatsAppTemplateDetailView.as_view(), name='template_detail'),
    path('templates/<uuid:pk>/preview/', WhatsAppTemplatePreviewView.as_view(), name='template_preview'),
    path('templates/seed-defaults/', WhatsAppTemplateSeedDefaultsView.as_view(), name='template_seed_defaults'),

    # 3. Opt-Out Registry & Consent Management
    path('opt-outs/', WhatsAppOptOutListView.as_view(), name='opt_out_list_create'),
    path('opt-outs/opt-in/', WhatsAppOptInView.as_view(), name='opt_in'),
    path('opt-outs/check/', WhatsAppOptOutCheckView.as_view(), name='opt_out_check'),

    # 4. Automated Reminder Queue
    path('reminders/', WhatsAppReminderListView.as_view(), name='reminder_list'),
    path('reminders/<uuid:pk>/cancel/', WhatsAppReminderCancelView.as_view(), name='reminder_cancel'),
    path('reminders/process-now/', WhatsAppReminderProcessNowView.as_view(), name='reminder_process_now'),

    # 5. Message Logs & Real-Time Delivery Tracking
    path('logs/', WhatsAppMessageLogListView.as_view(), name='message_log_list'),
    path('logs/<uuid:pk>/', WhatsAppMessageLogDetailView.as_view(), name='message_log_detail'),
    path('logs/<uuid:pk>/retry/', WhatsAppMessageRetryView.as_view(), name='message_log_retry'),
    path('analytics/', WhatsAppAnalyticsView.as_view(), name='analytics'),
    path('test-send/', WhatsAppTestSendView.as_view(), name='test_send'),

    # 6. Meta WhatsApp Cloud API Webhooks
    path('webhook/', WhatsAppWebhookView.as_view(), name='webhook_global'),
    path('webhook/<str:practice_slug_or_id>/', WhatsAppWebhookView.as_view(), name='webhook_practice'),
]

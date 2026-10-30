import uuid
from datetime import timedelta
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from practices.models import Practice, PracticeMembership
from security.permissions import RoleChecker
from security.services.audit_service import AuditService
from security.models import AuditLog

from whatsapp.models import (
    WhatsAppConfig,
    WhatsAppTemplate,
    WhatsAppOptOut,
    WhatsAppReminder,
    WhatsAppMessageLog,
    normalize_phone_number,
)
from whatsapp.serializers import (
    WhatsAppConfigSerializer,
    WhatsAppTemplateSerializer,
    WhatsAppOptOutSerializer,
    WhatsAppReminderSerializer,
    WhatsAppMessageLogSerializer,
    WhatsAppTestSendSerializer,
)
from whatsapp.services.template_service import WhatsAppTemplateService
from whatsapp.services.opt_out_service import WhatsAppOptOutService
from whatsapp.services.message_service import WhatsAppMessageService
from whatsapp.services.reminder_service import WhatsAppReminderService
from whatsapp.services.webhook_service import WhatsAppWebhookService


def _get_active_practice(request, practice_id=None):
    """Resolves active Practice tenant from middleware, header, or user membership."""
    if getattr(request, 'practice', None):
        return request.practice

    target_id = practice_id or request.headers.get('X-Practice-ID') or request.META.get('HTTP_X_PRACTICE_ID')
    if target_id:
        try:
            p_uuid = uuid.UUID(str(target_id).strip())
            membership = PracticeMembership.objects.filter(
                practice_id=p_uuid,
                user=request.user,
                is_active=True,
                practice__is_active=True
            ).select_related('practice').first()
            if membership:
                return membership.practice
        except (ValueError, TypeError):
            pass

    memberships = list(
        PracticeMembership.objects.filter(
            user=request.user,
            is_active=True,
            practice__is_active=True
        ).select_related('practice')[:2]
    )
    if len(memberships) == 1:
        return memberships[0].practice

    return None


# =====================================================================
# 1. WhatsApp Configuration Views
# =====================================================================

class WhatsAppConfigView(APIView):
    """
    Get or update WhatsApp Business settings and provider credentials.
    GET /api/whatsapp/config/
    PUT / PATCH /api/whatsapp/config/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified. Provide X-Practice-ID header."}, status=status.HTTP_400_BAD_REQUEST)

        config = WhatsAppMessageService.get_or_create_config(practice)
        serializer = WhatsAppConfigSerializer(config)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        return self.patch(request)

    def patch(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified. Provide X-Practice-ID header."}, status=status.HTTP_400_BAD_REQUEST)

        config = WhatsAppMessageService.get_or_create_config(practice)
        serializer = WhatsAppConfigSerializer(config, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            AuditService.log_action(
                practice=practice,
                action='whatsapp_config_updated',
                user=request.user,
                resource_type='WhatsAppConfig',
                resource_id=config.id,
                details=request.data,
                request=request
            )
            return Response(WhatsAppConfigSerializer(config).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# =====================================================================
# 2. Template Management Views
# =====================================================================

class WhatsAppTemplateListCreateView(APIView):
    """
    List practice templates or create custom templates.
    GET /api/whatsapp/templates/
    POST /api/whatsapp/templates/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified."}, status=status.HTTP_400_BAD_REQUEST)

        # Auto-seed defaults if practice has no templates yet
        if not WhatsAppTemplate.objects.filter(practice=practice).exists():
            WhatsAppTemplateService.seed_default_templates(practice)

        templates = WhatsAppTemplate.objects.filter(practice=practice)

        # Filters
        category = request.query_params.get('category')
        if category:
            templates = templates.filter(category=category.upper())

        language = request.query_params.get('language')
        if language:
            templates = templates.filter(language=language)

        is_active = request.query_params.get('is_active')
        if is_active is not None:
            templates = templates.filter(is_active=is_active.lower() in ('true', '1'))

        serializer = WhatsAppTemplateSerializer(templates, many=True)
        return Response({
            "count": templates.count(),
            "results": serializer.data
        }, status=status.HTTP_200_OK)

    def POST(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = WhatsAppTemplateSerializer(data=request.data)
        if serializer.is_valid():
            template = serializer.save(practice=practice)
            AuditService.log_action(
                practice=practice,
                action='whatsapp_template_created',
                user=request.user,
                resource_type='WhatsAppTemplate',
                resource_id=template.id,
                details={"template_name": template.template_name},
                request=request
            )
            return Response(WhatsAppTemplateSerializer(template).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class WhatsAppTemplateDetailView(APIView):
    """
    Retrieve, update, or deactivate a WhatsApp template.
    GET /api/whatsapp/templates/<uuid:pk>/
    PUT / PATCH /api/whatsapp/templates/<uuid:pk>/
    DELETE /api/whatsapp/templates/<uuid:pk>/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        practice = _get_active_practice(request)
        template = get_object_or_404(WhatsAppTemplate, pk=pk, practice=practice)
        return Response(WhatsAppTemplateSerializer(template).data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        return self.patch(request, pk)

    def patch(self, request, pk):
        practice = _get_active_practice(request)
        template = get_object_or_404(WhatsAppTemplate, pk=pk, practice=practice)
        serializer = WhatsAppTemplateSerializer(template, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(WhatsAppTemplateSerializer(template).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        practice = _get_active_practice(request)
        template = get_object_or_404(WhatsAppTemplate, pk=pk, practice=practice)
        if template.is_system_default:
            # Soft-deactivate default templates instead of dropping
            template.is_active = False
            template.save(update_fields=['is_active', 'updated_at'])
            return Response({"message": "System default template deactivated."}, status=status.HTTP_200_OK)
        template.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WhatsAppTemplatePreviewView(APIView):
    """
    Renders live preview of a template with sample context or custom payload.
    POST /api/whatsapp/templates/<uuid:pk>/preview/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        practice = _get_active_practice(request)
        template = get_object_or_404(WhatsAppTemplate, pk=pk, practice=practice)

        sample_context = WhatsAppTemplateService.build_sample_context(template.template_name, practice)
        custom_context = request.data.get('context', {})
        if custom_context and isinstance(custom_context, dict):
            sample_context.update(custom_context)

        rendered_text, resolved_params = WhatsAppTemplateService.render_template(template, sample_context)

        return Response({
            "template_name": template.template_name,
            "title": template.title,
            "header_text": template.header_text,
            "rendered_body": rendered_text,
            "footer_text": template.footer_text,
            "buttons": template.buttons,
            "resolved_parameters": resolved_params
        }, status=status.HTTP_200_OK)


class WhatsAppTemplateSeedDefaultsView(APIView):
    """
    Re-seeds standard clinical templates for the practice.
    POST /api/whatsapp/templates/seed-defaults/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified."}, status=status.HTTP_400_BAD_REQUEST)

        created_count = WhatsAppTemplateService.seed_default_templates(practice)
        return Response({
            "message": f"Successfully seeded default templates ({created_count} new created).",
            "created_count": created_count
        }, status=status.HTTP_200_OK)


# =====================================================================
# 3. Opt-Out Management Views
# =====================================================================

class WhatsAppOptOutListView(APIView):
    """
    List and register patient opt-outs.
    GET /api/whatsapp/opt-outs/
    POST /api/whatsapp/opt-outs/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified."}, status=status.HTTP_400_BAD_REQUEST)

        opt_outs = WhatsAppOptOut.objects.filter(practice=practice)

        search = request.query_params.get('search')
        if search:
            opt_outs = opt_outs.filter(
                Q(phone_number__icontains=search) | Q(patient_name__icontains=search)
            )

        is_opted_out = request.query_params.get('is_opted_out')
        if is_opted_out is not None:
            opt_outs = opt_outs.filter(is_opted_out=is_opted_out.lower() in ('true', '1'))

        serializer = WhatsAppOptOutSerializer(opt_outs, many=True)
        return Response({
            "total_opted_out": opt_outs.filter(is_opted_out=True).count(),
            "results": serializer.data
        }, status=status.HTTP_200_OK)

    def post(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified."}, status=status.HTTP_400_BAD_REQUEST)

        phone_number = request.data.get('phone_number')
        if not phone_number:
            return Response({"error": "phone_number is required."}, status=status.HTTP_400_BAD_REQUEST)

        reason = request.data.get('reason', WhatsAppOptOut.REASON_STAFF_MANUAL)
        reason_notes = request.data.get('reason_notes', '')
        patient_name = request.data.get('patient_name', '')
        channel = request.data.get('source_channel', WhatsAppOptOut.SOURCE_RECEPTION)

        opt_record = WhatsAppOptOutService.register_opt_out(
            practice=practice,
            phone_number=phone_number,
            reason=reason,
            source_channel=channel,
            patient_name=patient_name,
            reason_notes=reason_notes,
            performed_by=request.user,
            request=request
        )

        return Response(WhatsAppOptOutSerializer(opt_record).data, status=status.HTTP_201_CREATED)


class WhatsAppOptInView(APIView):
    """
    Re-subscribes a patient to WhatsApp communications.
    POST /api/whatsapp/opt-outs/opt-in/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified."}, status=status.HTTP_400_BAD_REQUEST)

        phone_number = request.data.get('phone_number')
        if not phone_number:
            return Response({"error": "phone_number is required."}, status=status.HTTP_400_BAD_REQUEST)

        opt_record = WhatsAppOptOutService.register_opt_in(
            practice=practice,
            phone_number=phone_number,
            source_channel=request.data.get('source_channel', WhatsAppOptOut.SOURCE_RECEPTION),
            patient_name=request.data.get('patient_name', ''),
            performed_by=request.user,
            request=request
        )

        return Response({
            "message": f"Phone number {opt_record.phone_number} successfully re-subscribed to WhatsApp messages.",
            "record": WhatsAppOptOutSerializer(opt_record).data
        }, status=status.HTTP_200_OK)


class WhatsAppOptOutCheckView(APIView):
    """
    Check if a specific phone number is currently opted out.
    GET /api/whatsapp/opt-outs/check/?phone=+919876543210
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified."}, status=status.HTTP_400_BAD_REQUEST)

        phone = request.query_params.get('phone')
        if not phone:
            return Response({"error": "phone query param required."}, status=status.HTTP_400_BAD_REQUEST)

        is_opted = WhatsAppOptOutService.is_opted_out(practice, phone)
        norm_phone = normalize_phone_number(phone)
        opt_record = WhatsAppOptOut.objects.filter(practice=practice, phone_number=norm_phone).first()

        return Response({
            "phone_number": norm_phone,
            "is_opted_out": is_opted,
            "can_receive_messages": not is_opted,
            "opt_out_record": WhatsAppOptOutSerializer(opt_record).data if opt_record else None
        }, status=status.HTTP_200_OK)


# =====================================================================
# 4. Reminders Queue Views
# =====================================================================

class WhatsAppReminderListView(APIView):
    """
    List and filter scheduled WhatsApp reminders.
    GET /api/whatsapp/reminders/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified."}, status=status.HTTP_400_BAD_REQUEST)

        reminders = WhatsAppReminder.objects.filter(practice=practice).select_related('booking', 'lead')

        status_param = request.query_params.get('status')
        if status_param:
            reminders = reminders.filter(status=status_param)

        reminder_type = request.query_params.get('reminder_type')
        if reminder_type:
            reminders = reminders.filter(reminder_type=reminder_type)

        serializer = WhatsAppReminderSerializer(reminders, many=True)
        return Response({
            "count": reminders.count(),
            "results": serializer.data
        }, status=status.HTTP_200_OK)


class WhatsAppReminderCancelView(APIView):
    """
    Cancel a pending reminder.
    POST /api/whatsapp/reminders/<uuid:pk>/cancel/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        practice = _get_active_practice(request)
        reminder = get_object_or_404(WhatsAppReminder, pk=pk, practice=practice)

        if reminder.status != WhatsAppReminder.STATUS_PENDING:
            return Response({"error": f"Cannot cancel reminder with status '{reminder.status}'."}, status=status.HTTP_400_BAD_REQUEST)

        reminder.status = WhatsAppReminder.STATUS_CANCELLED
        reminder.error_message = f"Cancelled manually by staff {request.user.full_name}"
        reminder.save(update_fields=['status', 'error_message', 'updated_at'])

        return Response({
            "message": "Reminder cancelled successfully.",
            "reminder": WhatsAppReminderSerializer(reminder).data
        }, status=status.HTTP_200_OK)


class WhatsAppReminderProcessNowView(APIView):
    """
    Manually triggers due reminder queue processing for this practice.
    POST /api/whatsapp/reminders/process-now/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified."}, status=status.HTTP_400_BAD_REQUEST)

        stats = WhatsAppReminderService.process_pending_reminders(practice=practice)
        return Response({
            "message": "Reminder processing complete.",
            "stats": stats
        }, status=status.HTTP_200_OK)


# =====================================================================
# 5. Message Logs & Analytics Views
# =====================================================================

class WhatsAppMessageLogListView(APIView):
    """
    Comprehensive delivery and audit log of all WhatsApp messages.
    GET /api/whatsapp/logs/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified."}, status=status.HTTP_400_BAD_REQUEST)

        logs = WhatsAppMessageLog.objects.filter(practice=practice).select_related('template', 'booking', 'lead')

        # Filters
        direction = request.query_params.get('direction')
        if direction:
            logs = logs.filter(direction=direction)

        status_param = request.query_params.get('status')
        if status_param:
            logs = logs.filter(status=status_param)

        recipient = request.query_params.get('recipient_phone')
        if recipient:
            logs = logs.filter(recipient_phone__icontains=recipient)

        template_name = request.query_params.get('template_name')
        if template_name:
            logs = logs.filter(template_name=template_name)

        booking_ref = request.query_params.get('booking_reference')
        if booking_ref:
            logs = logs.filter(booking__booking_reference=booking_ref)

        serializer = WhatsAppMessageLogSerializer(logs[:150], many=True)
        return Response({
            "count": logs.count(),
            "results": serializer.data
        }, status=status.HTTP_200_OK)


class WhatsAppMessageLogDetailView(APIView):
    """
    Retrieve single message delivery audit details.
    GET /api/whatsapp/logs/<uuid:pk>/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        practice = _get_active_practice(request)
        log = get_object_or_404(WhatsAppMessageLog, pk=pk, practice=practice)
        return Response(WhatsAppMessageLogSerializer(log).data, status=status.HTTP_200_OK)


class WhatsAppMessageRetryView(APIView):
    """
    Retries dispatch of a failed message.
    POST /api/whatsapp/logs/<uuid:pk>/retry/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        practice = _get_active_practice(request)
        log = get_object_or_404(WhatsAppMessageLog, pk=pk, practice=practice)

        if log.status not in [WhatsAppMessageLog.STATUS_FAILED, WhatsAppMessageLog.STATUS_BLOCKED_OPT_OUT]:
            return Response({"error": f"Message is not in a failed state (current status: {log.status})."}, status=status.HTTP_400_BAD_REQUEST)

        # Dispatch fresh retry
        new_log = WhatsAppMessageService.send_template_message(
            practice=practice,
            recipient_phone=log.recipient_phone,
            template_name=log.template_name or "appointment_confirmation_slot",
            context=log.parameters,
            recipient_name=log.recipient_name,
            booking=log.booking,
            lead=log.lead
        )

        return Response({
            "message": "Retry dispatched.",
            "new_log": WhatsAppMessageLogSerializer(new_log).data
        }, status=status.HTTP_200_OK)


class WhatsAppAnalyticsView(APIView):
    """
    Provides delivery rate, read rate, opt-out rate, and template breakdowns.
    GET /api/whatsapp/analytics/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified."}, status=status.HTTP_400_BAD_REQUEST)

        total_outbound = WhatsAppMessageLog.objects.filter(
            practice=practice,
            direction=WhatsAppMessageLog.DIRECTION_OUTBOUND
        ).count()

        status_counts = dict(
            WhatsAppMessageLog.objects.filter(
                practice=practice,
                direction=WhatsAppMessageLog.DIRECTION_OUTBOUND
            ).values('status').annotate(count=Count('id')).values_list('status', 'count')
        )

        sent_count = status_counts.get(WhatsAppMessageLog.STATUS_SENT, 0)
        delivered_count = status_counts.get(WhatsAppMessageLog.STATUS_DELIVERED, 0)
        read_count = status_counts.get(WhatsAppMessageLog.STATUS_READ, 0)
        failed_count = status_counts.get(WhatsAppMessageLog.STATUS_FAILED, 0)
        blocked_opt_out = status_counts.get(WhatsAppMessageLog.STATUS_BLOCKED_OPT_OUT, 0)

        # Successful deliveries includes delivered + read
        successful_deliveries = delivered_count + read_count
        effective_sent = total_outbound - blocked_opt_out
        delivery_rate = round((successful_deliveries / effective_sent * 100), 1) if effective_sent > 0 else 0.0
        read_rate = round((read_count / successful_deliveries * 100), 1) if successful_deliveries > 0 else 0.0

        # Opt-out metrics
        total_opted_out = WhatsAppOptOut.objects.filter(practice=practice, is_opted_out=True).count()
        total_recipients = WhatsAppMessageLog.objects.filter(practice=practice).values('recipient_phone').distinct().count()
        opt_out_rate = round((total_opted_out / total_recipients * 100), 1) if total_recipients > 0 else 0.0

        # Template breakdown
        template_breakdown = list(
            WhatsAppMessageLog.objects.filter(
                practice=practice,
                direction=WhatsAppMessageLog.DIRECTION_OUTBOUND
            )
            .values('template_name')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        # Inbound count
        inbound_count = WhatsAppMessageLog.objects.filter(
            practice=practice,
            direction=WhatsAppMessageLog.DIRECTION_INBOUND
        ).count()

        return Response({
            "total_outbound_messages": total_outbound,
            "total_inbound_messages": inbound_count,
            "status_breakdown": {
                "sent": sent_count,
                "delivered": delivered_count,
                "read": read_count,
                "failed": failed_count,
                "blocked_by_opt_out": blocked_opt_out
            },
            "metrics": {
                "delivery_rate_percent": delivery_rate,
                "read_rate_percent": read_rate,
                "opt_out_rate_percent": opt_out_rate,
                "active_opt_outs": total_opted_out
            },
            "template_breakdown": template_breakdown
        }, status=status.HTTP_200_OK)


class WhatsAppTestSendView(APIView):
    """
    Staff testing endpoint to send a live test template message.
    POST /api/whatsapp/test-send/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        practice = _get_active_practice(request)
        if not practice:
            return Response({"error": "Active practice not identified."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = WhatsAppTestSendSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        recipient_phone = serializer.validated_data['recipient_phone']
        template_name = serializer.validated_data['template_name']
        custom_ctx = serializer.validated_data.get('custom_context', {})

        context = WhatsAppTemplateService.build_sample_context(template_name, practice)
        context.update(custom_ctx)

        msg_log = WhatsAppMessageService.send_template_message(
            practice=practice,
            recipient_phone=recipient_phone,
            template_name=template_name,
            context=context,
            recipient_name="Test Staff / Patient"
        )

        return Response({
            "message": f"Test message dispatched to {recipient_phone}.",
            "log": WhatsAppMessageLogSerializer(msg_log).data
        }, status=status.HTTP_200_OK)


# =====================================================================
# 6. Webhook View (Meta WhatsApp Cloud API)
# =====================================================================

class WhatsAppWebhookView(APIView):
    """
    Public webhook receiver for Meta WhatsApp Cloud API events.
    Supports GET (Hub Challenge Verification) and POST (Event notifications).
    """
    permission_classes = [AllowAny]

    def get(self, request, practice_slug_or_id=None):
        mode = request.query_params.get('hub.mode')
        token = request.query_params.get('hub.verify_token')
        challenge = request.query_params.get('hub.challenge')

        practice = None
        if practice_slug_or_id:
            practice = Practice.objects.filter(
                Q(slug=practice_slug_or_id) | Q(id=practice_slug_or_id) if len(practice_slug_or_id) == 36 else Q(slug=practice_slug_or_id)
            ).first()

        if not practice:
            # Fallback to first practice if global webhook
            practice = Practice.objects.first()

        if not practice:
            return HttpResponse("No practice found", status=404)

        is_valid, response_body = WhatsAppWebhookService.verify_challenge(practice, mode, token, challenge)
        if is_valid:
            return HttpResponse(response_body, status=200, content_type='text/plain')
        return HttpResponse(response_body, status=403)

    def post(self, request, practice_slug_or_id=None):
        practice = None
        if practice_slug_or_id:
            practice = Practice.objects.filter(
                Q(slug=practice_slug_or_id) | Q(id=practice_slug_or_id) if len(practice_slug_or_id) == 36 else Q(slug=practice_slug_or_id)
            ).first()

        if not practice:
            practice = Practice.objects.first()

        if not practice:
            return Response({"error": "No practice associated with webhook."}, status=status.HTTP_404_NOT_FOUND)

        stats = WhatsAppWebhookService.process_webhook_payload(practice, request.data)
        return Response({"status": "received", "stats": stats}, status=status.HTTP_200_OK)

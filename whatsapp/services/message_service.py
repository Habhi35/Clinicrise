import uuid
import requests
from typing import Dict, Any, Optional
from django.conf import settings
from django.utils import timezone
from practices.models import Practice
from whatsapp.models import (
    WhatsAppConfig,
    WhatsAppTemplate,
    WhatsAppMessageLog,
    WhatsAppOptOut,
    normalize_phone_number
)
from whatsapp.services.template_service import WhatsAppTemplateService
from whatsapp.services.opt_out_service import WhatsAppOptOutService


class WhatsAppMessageService:
    """
    Core messaging dispatch engine for ClinicRise.
    Handles provider abstraction (Meta Cloud API, Twilio, Mock),
    pre-send opt-out verification, rate limiting, and delivery auditing.
    """

    @classmethod
    def get_or_create_config(cls, practice: Practice) -> WhatsAppConfig:
        """Retrieves or initializes WhatsApp configuration for the given practice."""
        config, created = WhatsAppConfig.objects.get_or_create(
            practice=practice,
            defaults={
                "provider": WhatsAppConfig.PROVIDER_MOCK,
                "display_phone_number": practice.phone_number or "+919876543210",
                "business_name": practice.name,
                "is_enabled": True,
                "auto_confirmation_enabled": True,
                "auto_reminders_enabled": True,
                "lead_auto_reply_enabled": True,
                "post_visit_review_enabled": True
            }
        )
        return config

    @classmethod
    def send_template_message(
        cls,
        practice: Practice,
        recipient_phone: str,
        template_name: str,
        context: Dict[str, Any],
        recipient_name: str = "",
        booking=None,
        lead=None,
        reminder=None,
        language: str = "en_US"
    ) -> WhatsAppMessageLog:
        """
        Dispatches a WhatsApp template message with strict opt-out validation.
        """
        norm_phone = normalize_phone_number(recipient_phone)
        config = cls.get_or_create_config(practice)
        msg_id = f"msg_{uuid.uuid4().hex}"

        # -------------------------------------------------------------
        # Guard 1: Practice WhatsApp Automation Enabled
        # -------------------------------------------------------------
        if not config.is_enabled:
            return WhatsAppMessageLog.objects.create(
                practice=practice,
                message_id=msg_id,
                direction=WhatsAppMessageLog.DIRECTION_OUTBOUND,
                recipient_phone=norm_phone,
                recipient_name=recipient_name,
                template_name=template_name,
                message_body="[Automation Disabled by Practice]",
                parameters=context,
                status=WhatsAppMessageLog.STATUS_FAILED,
                error_code="AUTOMATION_DISABLED",
                error_message="WhatsApp messaging is paused in practice settings.",
                booking=booking,
                lead=lead,
                reminder=reminder
            )

        # -------------------------------------------------------------
        # Guard 2: Recipient Opt-Out & Consent Check
        # -------------------------------------------------------------
        if WhatsAppOptOutService.is_opted_out(practice, norm_phone):
            return WhatsAppMessageLog.objects.create(
                practice=practice,
                message_id=msg_id,
                direction=WhatsAppMessageLog.DIRECTION_OUTBOUND,
                recipient_phone=norm_phone,
                recipient_name=recipient_name,
                template_name=template_name,
                message_body="[Message Blocked by Opt-Out Registry]",
                parameters=context,
                status=WhatsAppMessageLog.STATUS_BLOCKED_OPT_OUT,
                error_code="RECIPIENT_OPTED_OUT",
                error_message="Recipient has previously opted out or withdrawn WhatsApp communication consent.",
                booking=booking,
                lead=lead,
                reminder=reminder
            )

        # -------------------------------------------------------------
        # Guard 3: Daily Sending Quota Check
        # -------------------------------------------------------------
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        sent_today = WhatsAppMessageLog.objects.filter(
            practice=practice,
            direction=WhatsAppMessageLog.DIRECTION_OUTBOUND,
            sent_at__gte=today_start
        ).exclude(
            status__in=[WhatsAppMessageLog.STATUS_FAILED, WhatsAppMessageLog.STATUS_BLOCKED_OPT_OUT]
        ).count()

        if sent_today >= config.daily_send_limit:
            return WhatsAppMessageLog.objects.create(
                practice=practice,
                message_id=msg_id,
                direction=WhatsAppMessageLog.DIRECTION_OUTBOUND,
                recipient_phone=norm_phone,
                recipient_name=recipient_name,
                template_name=template_name,
                message_body="[Daily Quota Exceeded]",
                parameters=context,
                status=WhatsAppMessageLog.STATUS_FAILED,
                error_code="DAILY_LIMIT_EXCEEDED",
                error_message=f"Practice daily message limit ({config.daily_send_limit}) exceeded.",
                booking=booking,
                lead=lead,
                reminder=reminder
            )

        # -------------------------------------------------------------
        # Template Lookup & Rendering
        # -------------------------------------------------------------
        template = WhatsAppTemplate.objects.filter(
            practice=practice,
            template_name=template_name,
            language=language,
            is_active=True
        ).first()

        if not template:
            # Seed defaults if not found
            WhatsAppTemplateService.seed_default_templates(practice)
            template = WhatsAppTemplate.objects.filter(
                practice=practice,
                template_name=template_name,
                is_active=True
            ).first()

        rendered_text = ""
        resolved_params = {}
        if template:
            rendered_text, resolved_params = WhatsAppTemplateService.render_template(template, context)
        else:
            rendered_text = f"Notice from {practice.name}: " + ", ".join(f"{k}: {v}" for k, v in context.items())
            resolved_params = context

        # -------------------------------------------------------------
        # Provider Dispatch
        # -------------------------------------------------------------
        provider_msg_id = ""
        delivery_status = WhatsAppMessageLog.STATUS_SENT
        error_code = ""
        error_msg = ""

        if config.provider == WhatsAppConfig.PROVIDER_META and config.access_token and config.phone_number_id:
            try:
                # Real Meta WhatsApp Cloud API call
                url = f"https://graph.facebook.com/v19.0/{config.phone_number_id}/messages"
                headers = {
                    "Authorization": f"Bearer {config.access_token}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "messaging_product": "whatsapp",
                    "to": norm_phone.lstrip('+'),
                    "type": "text",
                    "text": {"preview_url": True, "body": rendered_text}
                }
                resp = requests.post(url, json=payload, headers=headers, timeout=10)
                if resp.status_code in (200, 201):
                    res_json = resp.json()
                    provider_msg_id = res_json.get('messages', [{}])[0].get('id', '')
                    delivery_status = WhatsAppMessageLog.STATUS_SENT
                else:
                    delivery_status = WhatsAppMessageLog.STATUS_FAILED
                    error_code = f"META_{resp.status_code}"
                    error_msg = resp.text[:500]
            except Exception as e:
                delivery_status = WhatsAppMessageLog.STATUS_FAILED
                error_code = "NETWORK_ERROR"
                error_msg = str(e)
        else:
            # Mock Simulator (instant delivery simulation for tests/dev)
            provider_msg_id = f"wamid.mock_{uuid.uuid4().hex[:16]}"
            delivery_status = WhatsAppMessageLog.STATUS_SENT

        # -------------------------------------------------------------
        # Create Message Log
        # -------------------------------------------------------------
        log = WhatsAppMessageLog.objects.create(
            practice=practice,
            message_id=msg_id,
            provider_message_id=provider_msg_id,
            direction=WhatsAppMessageLog.DIRECTION_OUTBOUND,
            recipient_phone=norm_phone,
            recipient_name=recipient_name,
            sender_phone=config.display_phone_number,
            template=template,
            template_name=template_name,
            message_body=rendered_text,
            parameters=resolved_params,
            status=delivery_status,
            booking=booking,
            lead=lead,
            reminder=reminder,
            error_code=error_code,
            error_message=error_msg,
            cost_tier=template.category.lower() if template else 'utility',
            sent_at=timezone.now()
        )

        return log

    @classmethod
    def send_custom_text(
        cls,
        practice: Practice,
        recipient_phone: str,
        message_text: str,
        recipient_name: str = "",
        booking=None,
        lead=None
    ) -> WhatsAppMessageLog:
        """
        Sends a direct text message, strictly honoring opt-out compliance.
        """
        norm_phone = normalize_phone_number(recipient_phone)
        config = cls.get_or_create_config(practice)
        msg_id = f"msg_{uuid.uuid4().hex}"

        if not config.is_enabled:
            return WhatsAppMessageLog.objects.create(
                practice=practice,
                message_id=msg_id,
                direction=WhatsAppMessageLog.DIRECTION_OUTBOUND,
                recipient_phone=norm_phone,
                recipient_name=recipient_name,
                message_body=message_text,
                status=WhatsAppMessageLog.STATUS_FAILED,
                error_code="AUTOMATION_DISABLED",
                error_message="WhatsApp messaging is disabled."
            )

        if WhatsAppOptOutService.is_opted_out(practice, norm_phone):
            return WhatsAppMessageLog.objects.create(
                practice=practice,
                message_id=msg_id,
                direction=WhatsAppMessageLog.DIRECTION_OUTBOUND,
                recipient_phone=norm_phone,
                recipient_name=recipient_name,
                message_body=message_text,
                status=WhatsAppMessageLog.STATUS_BLOCKED_OPT_OUT,
                error_code="RECIPIENT_OPTED_OUT",
                error_message="Recipient has opted out of WhatsApp messages."
            )

        provider_msg_id = f"wamid.mock_{uuid.uuid4().hex[:16]}"
        return WhatsAppMessageLog.objects.create(
            practice=practice,
            message_id=msg_id,
            provider_message_id=provider_msg_id,
            direction=WhatsAppMessageLog.DIRECTION_OUTBOUND,
            recipient_phone=norm_phone,
            recipient_name=recipient_name,
            sender_phone=config.display_phone_number,
            message_body=message_text,
            status=WhatsAppMessageLog.STATUS_SENT,
            booking=booking,
            lead=lead,
            cost_tier='utility',
            sent_at=timezone.now()
        )

    # =================================================================
    # Clinical Lifecycle Automations
    # =================================================================

    @classmethod
    def send_booking_confirmation(cls, booking) -> Optional[WhatsAppMessageLog]:
        """
        Builds healthcare context and triggers slot or token confirmation template.
        """
        config = cls.get_or_create_config(booking.practice)
        if not config.auto_confirmation_enabled or not config.is_enabled:
            return None

        # Build comprehensive context
        doctor_name = str(booking.doctor) if booking.doctor else "Attending Doctor"
        date_str = booking.appointment_date.strftime("%A, %d %b %Y") if booking.appointment_date else str(booking.preferred_date)
        clinic_name = booking.practice.name
        clinic_addr = booking.location.address if booking.location and booking.location.address else booking.practice.address
        maps_link = booking.location.google_maps_url if (booking.location and booking.location.google_maps_url) else ""

        is_token_mode = (booking.booking_mode == 'token')

        if is_token_mode:
            template_name = "appointment_confirmation_token"
            context = {
                "patient_name": booking.patient_name,
                "doctor_name": doctor_name,
                "appointment_date": date_str,
                "session_name": booking.session_name or "General OPD",
                "token_number": str(booking.token_number or "Assigned at clinic"),
                "estimated_arrival": booking.estimated_arrival_time.strftime("%I:%M %p") if booking.estimated_arrival_time else "To be announced",
                "clinic_name": clinic_name,
                "booking_reference": booking.booking_reference,
                "queue_url": f"https://clinicrise.com/queue/{booking.booking_reference}"
            }
        else:
            template_name = "appointment_confirmation_slot"
            start_str = booking.start_time.strftime("%I:%M %p") if booking.start_time else "Scheduled Slot"
            context = {
                "patient_name": booking.patient_name,
                "doctor_name": doctor_name,
                "appointment_date": date_str,
                "start_time": start_str,
                "clinic_name": clinic_name,
                "clinic_address": clinic_addr or clinic_name,
                "booking_reference": booking.booking_reference,
                "maps_link": maps_link or "https://maps.google.com"
            }

        return cls.send_template_message(
            practice=booking.practice,
            recipient_phone=booking.phone_number,
            template_name=template_name,
            context=context,
            recipient_name=booking.patient_name,
            booking=booking
        )

    @classmethod
    def send_reschedule_notice(cls, booking) -> Optional[WhatsAppMessageLog]:
        """Dispatches reschedule notice with new timing/token details."""
        config = cls.get_or_create_config(booking.practice)
        if not config.is_enabled:
            return None

        date_str = booking.appointment_date.strftime("%A, %d %b %Y") if booking.appointment_date else str(booking.preferred_date)
        time_or_token = (
            f"Token #{booking.token_number} ({booking.session_name})"
            if booking.booking_mode == 'token' and booking.token_number
            else booking.start_time.strftime("%I:%M %p") if booking.start_time
            else "Confirmed Slot"
        )

        context = {
            "patient_name": booking.patient_name,
            "doctor_name": str(booking.doctor) if booking.doctor else "Attending Doctor",
            "appointment_date": date_str,
            "time_or_token": time_or_token,
            "clinic_name": booking.practice.name,
            "booking_reference": booking.booking_reference,
            "clinic_url": f"https://clinicrise.com/track/{booking.booking_reference}"
        }

        return cls.send_template_message(
            practice=booking.practice,
            recipient_phone=booking.phone_number,
            template_name="appointment_rescheduled",
            context=context,
            recipient_name=booking.patient_name,
            booking=booking
        )

    @classmethod
    def send_cancellation_notice(cls, booking, reason: str = "") -> Optional[WhatsAppMessageLog]:
        """Dispatches cancellation notice to patient."""
        config = cls.get_or_create_config(booking.practice)
        if not config.is_enabled:
            return None

        date_str = booking.appointment_date.strftime("%A, %d %b %Y") if booking.appointment_date else str(booking.preferred_date)
        context = {
            "patient_name": booking.patient_name,
            "doctor_name": str(booking.doctor) if booking.doctor else "Attending Doctor",
            "appointment_date": date_str,
            "cancellation_reason": reason or booking.cancellation_reason or "Requested by patient",
            "clinic_phone": booking.practice.phone_number or "Reception",
            "booking_url": f"https://clinicrise.com/book/{booking.practice.slug}"
        }

        return cls.send_template_message(
            practice=booking.practice,
            recipient_phone=booking.phone_number,
            template_name="appointment_cancelled",
            context=context,
            recipient_name=booking.patient_name,
            booking=booking
        )

    @classmethod
    def send_lead_acknowledgement(cls, lead) -> Optional[WhatsAppMessageLog]:
        """Dispatches immediate welcome acknowledgment to new patient lead."""
        config = cls.get_or_create_config(lead.practice)
        if not config.lead_auto_reply_enabled or not config.is_enabled:
            return None

        context = {
            "patient_name": lead.patient_name,
            "clinic_name": lead.practice.name,
            "service_requested": lead.service_requested or "General Healthcare Enquiry",
            "clinic_phone": lead.practice.phone_number or "our reception line"
        }

        return cls.send_template_message(
            practice=lead.practice,
            recipient_phone=lead.phone_number,
            template_name="lead_welcome_acknowledgement",
            context=context,
            recipient_name=lead.patient_name,
            lead=lead
        )

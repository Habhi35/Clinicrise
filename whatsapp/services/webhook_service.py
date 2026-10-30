import uuid
from typing import Dict, Any, Tuple
from django.utils import timezone
from practices.models import Practice
from whatsapp.models import (
    WhatsAppConfig,
    WhatsAppMessageLog,
    WhatsAppOptOut,
    normalize_phone_number
)
from whatsapp.services.opt_out_service import WhatsAppOptOutService
from whatsapp.services.message_service import WhatsAppMessageService


class WhatsAppWebhookService:
    """
    Parser and processor for Meta WhatsApp Cloud API webhooks.
    Handles verification challenges, delivery receipts (sent, delivered, read, failed),
    and inbound message keyword triage (STOP, START, conversational).
    """

    @classmethod
    def verify_challenge(cls, practice: Practice, mode: str, token: str, challenge: str) -> Tuple[bool, str]:
        """
        Validates hub.verify_token against practice's webhook_verify_token.
        Returns (is_valid, challenge_or_error_message).
        """
        config = WhatsAppConfig.objects.filter(practice=practice).first()
        expected_token = config.webhook_verify_token if config else "clinicrise_verify_token"

        if mode == "subscribe" and token == expected_token:
            return True, challenge
        return False, "Verification token mismatch or invalid mode"

    @classmethod
    def process_webhook_payload(cls, practice: Practice, payload: Dict[str, Any]) -> Dict[str, int]:
        """
        Processes standard Meta WhatsApp Cloud API JSON payload.
        Handles both message status events and inbound messages.
        """
        stats = {
            "statuses_processed": 0,
            "inbound_messages": 0,
            "opt_outs_triggered": 0,
            "opt_ins_triggered": 0
        }

        entries = payload.get('entry', [])
        for entry in entries:
            changes = entry.get('changes', [])
            for change in changes:
                value = change.get('value', {})

                # -----------------------------------------------------
                # 1. Process Delivery Status Receipts
                # -----------------------------------------------------
                statuses = value.get('statuses', [])
                for st in statuses:
                    wamid = st.get('id')
                    status_name = st.get('status')  # 'sent', 'delivered', 'read', 'failed'
                    if not wamid:
                        continue

                    msg_log = WhatsAppMessageLog.objects.filter(
                        practice=practice,
                        provider_message_id=wamid
                    ).first()

                    if msg_log:
                        now = timezone.now()
                        if status_name == 'delivered':
                            msg_log.status = WhatsAppMessageLog.STATUS_DELIVERED
                            msg_log.delivered_at = now
                            msg_log.save(update_fields=['status', 'delivered_at', 'updated_at'])
                            stats["statuses_processed"] += 1
                        elif status_name == 'read':
                            msg_log.status = WhatsAppMessageLog.STATUS_READ
                            msg_log.read_at = now
                            msg_log.save(update_fields=['status', 'read_at', 'updated_at'])
                            stats["statuses_processed"] += 1
                        elif status_name == 'failed':
                            msg_log.status = WhatsAppMessageLog.STATUS_FAILED
                            msg_log.failed_at = now
                            errors = st.get('errors', [])
                            if errors:
                                msg_log.error_code = str(errors[0].get('code', 'FAILED'))
                                msg_log.error_message = str(errors[0].get('title', 'Delivery failed'))
                            msg_log.save(update_fields=['status', 'failed_at', 'error_code', 'error_message', 'updated_at'])
                            stats["statuses_processed"] += 1

                # -----------------------------------------------------
                # 2. Process Inbound Messages
                # -----------------------------------------------------
                messages = value.get('messages', [])
                for msg in messages:
                    sender_raw = msg.get('from', '')
                    sender_phone = normalize_phone_number(sender_raw)
                    wamid = msg.get('id', f"wamid.in_{uuid.uuid4().hex[:12]}")
                    msg_type = msg.get('type', 'text')

                    # Extract text content
                    text_body = ""
                    if msg_type == 'text':
                        text_body = msg.get('text', {}).get('body', '').strip()
                    elif msg_type == 'button':
                        text_body = msg.get('button', {}).get('text', '').strip()
                    elif msg_type == 'interactive':
                        interactive = msg.get('interactive', {})
                        if interactive.get('type') == 'button_reply':
                            text_body = interactive.get('button_reply', {}).get('title', '').strip()

                    if not sender_phone:
                        continue

                    stats["inbound_messages"] += 1

                    # Log inbound message
                    config = WhatsAppConfig.objects.filter(practice=practice).first()
                    inbound_log = WhatsAppMessageLog.objects.create(
                        practice=practice,
                        message_id=f"in_{uuid.uuid4().hex}",
                        provider_message_id=wamid,
                        direction=WhatsAppMessageLog.DIRECTION_INBOUND,
                        recipient_phone=config.display_phone_number if config else practice.phone_number,
                        sender_phone=sender_phone,
                        message_body=text_body,
                        status=WhatsAppMessageLog.STATUS_DELIVERED,
                        sent_at=timezone.now()
                    )

                    # -------------------------------------------------
                    # 3. Compliance Keyword Detection
                    # -------------------------------------------------
                    action = WhatsAppOptOutService.detect_keyword(text_body)

                    if action == 'opt_out':
                        WhatsAppOptOutService.register_opt_out(
                            practice=practice,
                            phone_number=sender_phone,
                            reason=WhatsAppOptOut.REASON_KEYWORD_STOP,
                            source_channel=WhatsAppOptOut.SOURCE_WHATSAPP
                        )
                        stats["opt_outs_triggered"] += 1

                        # Send mandatory compliance confirmation receipt
                        ack_text = WhatsAppOptOutService.get_opt_out_acknowledgment(practice.name)
                        WhatsAppMessageService.send_custom_text(
                            practice=practice,
                            recipient_phone=sender_phone,
                            message_text=ack_text
                        )

                    elif action == 'opt_in':
                        WhatsAppOptOutService.register_opt_in(
                            practice=practice,
                            phone_number=sender_phone,
                            source_channel=WhatsAppOptOut.SOURCE_WHATSAPP
                        )
                        stats["opt_ins_triggered"] += 1

                        # Send resubscription welcome message
                        ack_text = WhatsAppOptOutService.get_opt_in_acknowledgment(practice.name)
                        WhatsAppMessageService.send_custom_text(
                            practice=practice,
                            recipient_phone=sender_phone,
                            message_text=ack_text
                        )

                    else:
                        # Non-keyword conversational message: Link to Leads or Bookings
                        try:
                            from leads.models import Lead, LeadActivity
                            lead = Lead.objects.filter(practice=practice, phone_number=sender_phone).first()
                            if lead:
                                LeadActivity.objects.create(
                                    practice=practice,
                                    lead=lead,
                                    activity_type=LeadActivity.TYPE_WHATSAPP,
                                    note=f"Inbound WhatsApp: {text_body}"
                                )
                                inbound_log.lead = lead
                                inbound_log.save(update_fields=['lead'])
                        except Exception:
                            pass

                        try:
                            from bookings.models import BookingRequest, BookingTimeline
                            booking = BookingRequest.objects.filter(
                                practice=practice,
                                phone_number=sender_phone
                            ).exclude(status__in=['completed', 'cancelled', 'rejected']).first()
                            if booking:
                                BookingTimeline.objects.create(
                                    practice=practice,
                                    booking=booking,
                                    action='whatsapp_inbound',
                                    note=f"Patient WhatsApp message: {text_body}"
                                )
                                inbound_log.booking = booking
                                inbound_log.save(update_fields=['booking'])
                        except Exception:
                            pass

        return stats

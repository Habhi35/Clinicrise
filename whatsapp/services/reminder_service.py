from datetime import datetime, time, timedelta
from typing import Dict, Any, List, Optional
from django.db.models import Q
from django.utils import timezone
from practices.models import Practice
from whatsapp.models import WhatsAppConfig, WhatsAppReminder, WhatsAppMessageLog
from whatsapp.services.message_service import WhatsAppMessageService
from whatsapp.services.opt_out_service import WhatsAppOptOutService


class WhatsAppReminderService:
    """
    Intelligent scheduling and execution engine for automated WhatsApp reminders.
    Supports 24h & 2h appointment alerts, token updates, lead follow-ups,
    and post-consultation Google review requests.
    """

    @classmethod
    def schedule_booking_reminders(cls, booking) -> List[WhatsAppReminder]:
        """
        Calculates and schedules 24-hour and 2-hour reminders for a confirmed booking.
        Cancels any outdated pending reminders for this booking before rescheduling.
        """
        config = WhatsAppMessageService.get_or_create_config(booking.practice)
        if not config.auto_reminders_enabled or not config.is_enabled:
            return []

        # Cancel existing pending reminders for this booking (e.g. on reschedule)
        WhatsAppReminder.objects.filter(
            booking=booking,
            status=WhatsAppReminder.STATUS_PENDING
        ).update(
            status=WhatsAppReminder.STATUS_CANCELLED,
            error_message="Cancelled: Booking rescheduled or refreshed"
        )

        appointment_date = booking.appointment_date or booking.preferred_date
        if not appointment_date:
            return []

        # Determine consultation target datetime
        start_time = booking.start_time or time(9, 30)
        # Combine naive date & time, then make aware with current timezone
        target_datetime = timezone.make_aware(
            datetime.combine(appointment_date, start_time),
            timezone.get_current_timezone()
        )
        now = timezone.now()

        created_reminders = []

        # 1. 24-Hour Advance Reminder (1 day before at 10:00 AM or 24h prior)
        t_24h = target_datetime - timedelta(hours=24)
        if t_24h > now:
            rem_24 = WhatsAppReminder.objects.create(
                practice=booking.practice,
                booking=booking,
                reminder_type=WhatsAppReminder.TYPE_APPT_24H,
                scheduled_for=t_24h,
                status=WhatsAppReminder.STATUS_PENDING
            )
            created_reminders.append(rem_24)

        # 2. 2-Hour Immediate Reminder
        t_2h = target_datetime - timedelta(hours=2)
        if t_2h > now:
            rem_2 = WhatsAppReminder.objects.create(
                practice=booking.practice,
                booking=booking,
                reminder_type=WhatsAppReminder.TYPE_APPT_2H,
                scheduled_for=t_2h,
                status=WhatsAppReminder.STATUS_PENDING
            )
            created_reminders.append(rem_2)

        return created_reminders

    @classmethod
    def schedule_post_visit_review(cls, booking, delay_hours: int = 2) -> Optional[WhatsAppReminder]:
        """
        Schedules a post-visit review reminder with GBP review link
        once an appointment is marked completed.
        """
        config = WhatsAppMessageService.get_or_create_config(booking.practice)
        if not config.post_visit_review_enabled or not config.is_enabled:
            return None

        # Cancel any previous review requests for this booking
        WhatsAppReminder.objects.filter(
            booking=booking,
            reminder_type=WhatsAppReminder.TYPE_POST_VISIT_REVIEW,
            status=WhatsAppReminder.STATUS_PENDING
        ).update(status=WhatsAppReminder.STATUS_CANCELLED)

        scheduled_time = timezone.now() + timedelta(hours=delay_hours)
        return WhatsAppReminder.objects.create(
            practice=booking.practice,
            booking=booking,
            reminder_type=WhatsAppReminder.TYPE_POST_VISIT_REVIEW,
            scheduled_for=scheduled_time,
            status=WhatsAppReminder.STATUS_PENDING
        )

    @classmethod
    def schedule_lead_follow_up(cls, lead, delay_hours: int = 24) -> Optional[WhatsAppReminder]:
        """Schedules follow-up reminder for uncontacted leads."""
        config = WhatsAppMessageService.get_or_create_config(lead.practice)
        if not config.is_enabled:
            return None

        scheduled_time = timezone.now() + timedelta(hours=delay_hours)
        return WhatsAppReminder.objects.create(
            practice=lead.practice,
            lead=lead,
            reminder_type=WhatsAppReminder.TYPE_LEAD_FOLLOW_UP,
            scheduled_for=scheduled_time,
            status=WhatsAppReminder.STATUS_PENDING
        )

    @classmethod
    def process_pending_reminders(cls, practice: Optional[Practice] = None, batch_limit: int = 100) -> Dict[str, int]:
        """
        Batch processing runner intended for cron or on-demand execution.
        Evaluates due reminders, validates appointment status and consent, and dispatches.
        """
        now = timezone.now()
        qs = WhatsAppReminder.objects.filter(
            status=WhatsAppReminder.STATUS_PENDING,
            scheduled_for__lte=now
        ).select_related('practice', 'booking', 'lead')

        if practice:
            qs = qs.filter(practice=practice)

        due_reminders = list(qs[:batch_limit])
        stats = {
            "processed": 0,
            "sent": 0,
            "cancelled": 0,
            "skipped_opt_out": 0,
            "failed": 0
        }

        for rem in due_reminders:
            stats["processed"] += 1
            practice_obj = rem.practice

            # ---------------------------------------------------------
            # Appointment Reminders
            # ---------------------------------------------------------
            if rem.booking:
                booking = rem.booking

                # Check if booking is still confirmed
                if booking.status in ['cancelled', 'rejected', 'no_show']:
                    rem.status = WhatsAppReminder.STATUS_CANCELLED
                    rem.error_message = f"Booking was {booking.status}"
                    rem.save(update_fields=['status', 'error_message', 'updated_at'])
                    stats["cancelled"] += 1
                    continue

                # Check opt-out
                if WhatsAppOptOutService.is_opted_out(practice_obj, booking.phone_number):
                    rem.status = WhatsAppReminder.STATUS_SKIPPED_OPT_OUT
                    rem.error_message = "Patient opted out of WhatsApp messaging"
                    rem.save(update_fields=['status', 'error_message', 'updated_at'])
                    stats["skipped_opt_out"] += 1
                    continue

                # Build context
                doctor_name = str(booking.doctor) if booking.doctor else "Attending Doctor"
                date_str = booking.appointment_date.strftime("%A, %d %b %Y") if booking.appointment_date else str(booking.preferred_date)
                time_or_token = (
                    f"Token #{booking.token_number} ({booking.session_name})"
                    if booking.booking_mode == 'token' and booking.token_number
                    else booking.start_time.strftime("%I:%M %p") if booking.start_time
                    else "Scheduled Slot"
                )

                if rem.reminder_type == WhatsAppReminder.TYPE_APPT_24H:
                    template_name = "appointment_reminder_24h"
                    context = {
                        "patient_name": booking.patient_name,
                        "doctor_name": doctor_name,
                        "appointment_date": date_str,
                        "time_or_token": time_or_token,
                        "clinic_name": practice_obj.name,
                        "clinic_address": booking.location.address if booking.location else practice_obj.address
                    }
                elif rem.reminder_type == WhatsAppReminder.TYPE_APPT_2H:
                    template_name = "appointment_reminder_2h"
                    context = {
                        "patient_name": booking.patient_name,
                        "doctor_name": doctor_name,
                        "clinic_name": practice_obj.name,
                        "time_or_token": time_or_token,
                        "clinic_address": booking.location.address if booking.location else practice_obj.address,
                        "booking_reference": booking.booking_reference,
                        "maps_link": booking.location.google_maps_url if (booking.location and booking.location.google_maps_url) else ""
                    }
                elif rem.reminder_type == WhatsAppReminder.TYPE_POST_VISIT_REVIEW:
                    template_name = "post_visit_review_request"
                    review_url = "https://search.google.com"
                    try:
                        from gbp.services.gbp_service import GBPService
                        profile = GBPService.get_or_create_profile(practice_obj)
                        review_url = profile.google_review_short_link or review_url
                    except Exception:
                        pass
                    context = {
                        "patient_name": booking.patient_name,
                        "clinic_name": practice_obj.name,
                        "doctor_name": doctor_name,
                        "google_review_url": review_url
                    }
                else:
                    template_name = "appointment_reminder_24h"
                    context = {
                        "patient_name": booking.patient_name,
                        "doctor_name": doctor_name,
                        "appointment_date": date_str,
                        "time_or_token": time_or_token,
                        "clinic_name": practice_obj.name
                    }

                msg_log = WhatsAppMessageService.send_template_message(
                    practice=practice_obj,
                    recipient_phone=booking.phone_number,
                    template_name=template_name,
                    context=context,
                    recipient_name=booking.patient_name,
                    booking=booking,
                    reminder=rem
                )

                if msg_log.status in [WhatsAppMessageLog.STATUS_SENT, WhatsAppMessageLog.STATUS_DELIVERED, WhatsAppMessageLog.STATUS_READ]:
                    rem.status = WhatsAppReminder.STATUS_SENT
                    rem.sent_at = timezone.now()
                    rem.save(update_fields=['status', 'sent_at', 'updated_at'])
                    stats["sent"] += 1
                elif msg_log.status == WhatsAppMessageLog.STATUS_BLOCKED_OPT_OUT:
                    rem.status = WhatsAppReminder.STATUS_SKIPPED_OPT_OUT
                    rem.error_message = msg_log.error_message
                    rem.save(update_fields=['status', 'error_message', 'updated_at'])
                    stats["skipped_opt_out"] += 1
                else:
                    rem.status = WhatsAppReminder.STATUS_FAILED
                    rem.error_message = msg_log.error_message
                    rem.save(update_fields=['status', 'error_message', 'updated_at'])
                    stats["failed"] += 1

            # ---------------------------------------------------------
            # Lead Follow-Up Reminders
            # ---------------------------------------------------------
            elif rem.lead:
                lead = rem.lead

                if lead.status in ['converted', 'lost', 'junk']:
                    rem.status = WhatsAppReminder.STATUS_CANCELLED
                    rem.error_message = f"Lead was {lead.status}"
                    rem.save(update_fields=['status', 'error_message', 'updated_at'])
                    stats["cancelled"] += 1
                    continue

                if WhatsAppOptOutService.is_opted_out(practice_obj, lead.phone_number):
                    rem.status = WhatsAppReminder.STATUS_SKIPPED_OPT_OUT
                    rem.error_message = "Lead opted out of WhatsApp messaging"
                    rem.save(update_fields=['status', 'error_message', 'updated_at'])
                    stats["skipped_opt_out"] += 1
                    continue

                context = {
                    "patient_name": lead.patient_name,
                    "clinic_name": practice_obj.name,
                    "service_requested": lead.service_requested or "Consultation",
                    "clinic_phone": practice_obj.phone_number or "Reception"
                }

                msg_log = WhatsAppMessageService.send_template_message(
                    practice=practice_obj,
                    recipient_phone=lead.phone_number,
                    template_name="lead_welcome_acknowledgement",
                    context=context,
                    recipient_name=lead.patient_name,
                    lead=lead,
                    reminder=rem
                )

                if msg_log.status in [WhatsAppMessageLog.STATUS_SENT, WhatsAppMessageLog.STATUS_DELIVERED, WhatsAppMessageLog.STATUS_READ]:
                    rem.status = WhatsAppReminder.STATUS_SENT
                    rem.sent_at = timezone.now()
                    rem.save(update_fields=['status', 'sent_at', 'updated_at'])
                    stats["sent"] += 1
                else:
                    rem.status = WhatsAppReminder.STATUS_FAILED
                    rem.error_message = msg_log.error_message
                    rem.save(update_fields=['status', 'error_message', 'updated_at'])
                    stats["failed"] += 1

        return stats

from datetime import timedelta
from django.db.models import Count, Q
from django.utils import timezone
from practices.models import DoctorProfile, Practice, PracticeService
from leads.models import Lead, LeadActivity
from bookings.models import (
    BookingRequest,
    BookingTimeline,
    DoctorSessionCapacity,
    PracticeLocation,
    generate_booking_reference,
)
from .capacity_service import CapacityService


class BookingService:
    """
    Core management service for Patient Booking Requests,
    clinic confirmations, token assignment, and queue workflows.
    """

    @classmethod
    def create_booking(cls, practice: Practice, data: dict, user=None, source: str = 'website') -> BookingRequest:
        """
        Creates a new BookingRequest, runs initial capacity checks,
        and optionally auto-confirms if enabled.
        """
        location = data.get('location')
        doctor = data.get('doctor')
        service = data.get('service')
        preferred_date = data.get('preferred_date')
        booking_mode = data.get('booking_mode')

        # If booking_mode not specified, check doctor's default capacity setting
        if not booking_mode and doctor:
            cap_config = DoctorSessionCapacity.objects.filter(practice=practice, doctor=doctor).first()
            booking_mode = cap_config.booking_mode if cap_config else BookingRequest.SCHEDULING_MODE_SLOT
        elif not booking_mode:
            booking_mode = BookingRequest.SCHEDULING_MODE_SLOT

        session_name = data.get('session_name', '')
        start_time = data.get('start_time')
        end_time = data.get('end_time')

        # Run capacity check
        capacity_res = CapacityService.check_capacity(
            practice=practice,
            doctor=doctor,
            appointment_date=preferred_date,
            booking_mode=booking_mode,
            session_name=session_name,
            start_time=start_time,
            end_time=end_time
        )

        # Check if doctor has auto-confirm enabled
        auto_confirm = False
        if doctor:
            cap_config = DoctorSessionCapacity.objects.filter(
                practice=practice,
                doctor=doctor,
                session_name=session_name or 'General OPD'
            ).first()
            if cap_config and cap_config.auto_confirm and capacity_res.get('available'):
                auto_confirm = True

        # Generate unique reference
        ref = generate_booking_reference()
        while BookingRequest.objects.filter(booking_reference=ref).exists():
            ref = generate_booking_reference()

        booking = BookingRequest.objects.create(
            practice=practice,
            booking_reference=ref,
            location=location,
            doctor=doctor,
            service=service,
            patient_name=data.get('patient_name', '').strip(),
            phone_number=data.get('phone_number', '').strip(),
            email=data.get('email', '').strip(),
            gender=data.get('gender', ''),
            age=data.get('age'),
            date_of_birth=data.get('date_of_birth'),
            patient_type=data.get('patient_type', BookingRequest.TYPE_NEW),
            consultation_mode=data.get('consultation_mode', BookingRequest.MODE_IN_PERSON),
            preferred_date=preferred_date,
            preferred_time_window=data.get('preferred_time_window', BookingRequest.WINDOW_ANY),
            chief_complaint=data.get('chief_complaint', '').strip(),
            patient_notes=data.get('patient_notes', '').strip(),
            booking_mode=booking_mode,
            appointment_date=preferred_date,
            session_name=session_name or capacity_res.get('session_name', ''),
            start_time=start_time,
            end_time=end_time,
            source=source,
            consent_given=data.get('consent_given', True),
            consent_timestamp=timezone.now(),
            status=BookingRequest.STATUS_CONFIRMED if auto_confirm else BookingRequest.STATUS_REQUESTED
        )

        if auto_confirm:
            booking.confirmed_at = timezone.now()
            if booking_mode == BookingRequest.SCHEDULING_MODE_TOKEN:
                booking.token_number = capacity_res.get('next_token', 1)
            booking.save()

        # Log timeline
        BookingTimeline.objects.create(
            practice=practice,
            booking=booking,
            performed_by=user,
            action='auto_confirmed' if auto_confirm else 'requested',
            note=(
                f"Booking request created via {dict(BookingRequest.SOURCE_CHOICES).get(source, source)}. "
                f"Mode: {booking.get_booking_mode_display()}. "
                f"{'Auto-confirmed with Token #' + str(booking.token_number) if auto_confirm and booking.token_number else ''}"
            )
        )

        # Seamlessly sync with Practice Lead CRM
        try:
            lead = Lead.objects.create(
                practice=practice,
                patient_name=booking.patient_name,
                phone_number=booking.phone_number,
                email=booking.email,
                preferred_date=booking.preferred_date,
                service_requested=service.name if service else "",
                doctor_requested=getattr(doctor.user, 'full_name', '') if doctor else "",
                message=f"Booking Request [{booking.booking_reference}] - {booking.chief_complaint or 'Consultation'}",
                status=Lead.STATUS_APPOINTMENT_SCHEDULED if auto_confirm else Lead.STATUS_NEW,
                priority=Lead.PRIORITY_HIGH,
                source=Lead.SOURCE_WEBSITE_FORM if source == 'website' else Lead.SOURCE_MANUAL,
                consent_given=booking.consent_given,
            )
            booking.lead = lead
            booking.save(update_fields=['lead'])
        except Exception:
            pass

        return booking

    @classmethod
    def confirm_booking(
        cls,
        booking: BookingRequest,
        user=None,
        confirmed_date=None,
        start_time=None,
        end_time=None,
        token_number=None,
        session_name=None,
        clinic_notes=""
    ) -> BookingRequest:
        """
        Confirms a booking request with capacity validation,
        allocating either a precise time slot or sequential token number.
        """
        target_date = confirmed_date or booking.appointment_date or booking.preferred_date
        target_mode = booking.booking_mode

        # Check capacity before confirming
        capacity_res = CapacityService.check_capacity(
            practice=booking.practice,
            doctor=booking.doctor,
            appointment_date=target_date,
            booking_mode=target_mode,
            session_name=session_name or booking.session_name,
            start_time=start_time or booking.start_time,
            end_time=end_time or booking.end_time,
            exclude_booking_id=booking.id
        )

        if not capacity_res.get('available'):
            raise ValueError(capacity_res.get('reason', 'Selected slot or session has no capacity available.'))

        booking.status = BookingRequest.STATUS_CONFIRMED
        booking.confirmed_at = timezone.now()
        booking.confirmed_by = user
        booking.appointment_date = target_date

        if clinic_notes:
            booking.clinic_notes = clinic_notes

        if target_mode == BookingRequest.SCHEDULING_MODE_TOKEN:
            booking.session_name = session_name or capacity_res.get('session_name') or booking.session_name
            booking.token_number = token_number or capacity_res.get('next_token') or 1
        else:
            if start_time:
                booking.start_time = start_time
            if end_time:
                booking.end_time = end_time

        booking.save()

        # Update associated lead status if exists
        if booking.lead and booking.lead.status in [Lead.STATUS_NEW, Lead.STATUS_CONTACTED]:
            booking.lead.status = Lead.STATUS_APPOINTMENT_SCHEDULED
            booking.lead.save(update_fields=['status', 'updated_at'])

        # Log timeline
        mode_info = f"Token #{booking.token_number} ({booking.session_name})" if target_mode == BookingRequest.SCHEDULING_MODE_TOKEN else f"Slot {booking.start_time}"
        BookingTimeline.objects.create(
            practice=booking.practice,
            booking=booking,
            performed_by=user,
            action='confirmed',
            note=f"Booking confirmed by {getattr(user, 'full_name', str(user)) if user else 'Clinic'}. {mode_info} on {booking.appointment_date}."
        )

        # Sync with Patient CRM
        try:
            from patients.services.patient_service import PatientService
            from patients.models import PatientTimeline
            patient, _ = PatientService.get_or_create_patient(
                practice=booking.practice,
                phone_number=booking.phone_number,
                name=booking.patient_name,
                email=booking.email,
                gender=booking.gender,
                source='website_booking' if booking.source == 'website' else 'walk_in',
                performed_by=user,
                role='receptionist'
            )
            PatientService.log_timeline_event(
                patient=patient,
                event_type=PatientTimeline.EVENT_BOOKING_CONFIRMED,
                title="Appointment Confirmed",
                description=f"Appointment confirmed on {booking.appointment_date}.",
                performed_by=user,
                performer_role='receptionist',
                metadata={"booking_reference": booking.booking_reference, "booking_id": str(booking.id)}
            )
        except Exception:
            pass

        # Trigger automated WhatsApp confirmation & reminders
        try:
            from whatsapp.services.message_service import WhatsAppMessageService
            from whatsapp.services.reminder_service import WhatsAppReminderService
            WhatsAppMessageService.send_booking_confirmation(booking)
            WhatsAppReminderService.schedule_booking_reminders(booking)
        except Exception:
            pass

        return booking

    @classmethod
    def reschedule_booking(
        cls,
        booking: BookingRequest,
        user=None,
        new_date=None,
        new_start_time=None,
        new_end_time=None,
        new_session=None,
        reason=""
    ) -> BookingRequest:
        """
        Reschedules an appointment to a new date/slot/session with capacity verification.
        """
        old_date = booking.appointment_date
        old_mode_info = f"Token #{booking.token_number}" if booking.booking_mode == BookingRequest.SCHEDULING_MODE_TOKEN else f"{booking.start_time}"

        # Capacity check on new slot/session
        capacity_res = CapacityService.check_capacity(
            practice=booking.practice,
            doctor=booking.doctor,
            appointment_date=new_date,
            booking_mode=booking.booking_mode,
            session_name=new_session or booking.session_name,
            start_time=new_start_time,
            end_time=new_end_time,
            exclude_booking_id=booking.id
        )

        if not capacity_res.get('available'):
            raise ValueError(capacity_res.get('reason', 'Reschedule target date/slot is unavailable.'))

        booking.appointment_date = new_date
        booking.status = BookingRequest.STATUS_RESCHEDULED

        if booking.booking_mode == BookingRequest.SCHEDULING_MODE_TOKEN:
            booking.session_name = new_session or capacity_res.get('session_name') or booking.session_name
            booking.token_number = capacity_res.get('next_token', 1)
        else:
            if new_start_time:
                booking.start_time = new_start_time
            if new_end_time:
                booking.end_time = new_end_time

        booking.save()

        BookingTimeline.objects.create(
            practice=booking.practice,
            booking=booking,
            performed_by=user,
            action='rescheduled',
            note=f"Rescheduled from {old_date} ({old_mode_info}) to {new_date}. Reason: {reason or 'Clinic / Patient reschedule request'}."
        )

        # Trigger automated WhatsApp reschedule notice & refreshed reminders
        try:
            from whatsapp.services.message_service import WhatsAppMessageService
            from whatsapp.services.reminder_service import WhatsAppReminderService
            WhatsAppMessageService.send_reschedule_notice(booking)
            WhatsAppReminderService.schedule_booking_reminders(booking)
        except Exception:
            pass

        return booking

    @classmethod
    def cancel_booking(cls, booking: BookingRequest, user=None, reason: str = "") -> BookingRequest:
        """Cancels an appointment and frees up the slot/token."""
        booking.status = BookingRequest.STATUS_CANCELLED
        booking.cancelled_at = timezone.now()
        booking.cancellation_reason = reason.strip() or "Cancelled by patient or clinic."
        booking.save(update_fields=['status', 'cancelled_at', 'cancellation_reason', 'updated_at'])

        BookingTimeline.objects.create(
            practice=booking.practice,
            booking=booking,
            performed_by=user,
            action='cancelled',
            note=f"Cancelled. Reason: {booking.cancellation_reason}"
        )

        # Trigger automated WhatsApp cancellation notice & cancel reminders
        try:
            from whatsapp.services.message_service import WhatsAppMessageService
            from whatsapp.models import WhatsAppReminder
            WhatsAppMessageService.send_cancellation_notice(booking, reason=booking.cancellation_reason)
            WhatsAppReminder.objects.filter(booking=booking, status=WhatsAppReminder.STATUS_PENDING).update(
                status=WhatsAppReminder.STATUS_CANCELLED,
                error_message="Booking cancelled"
            )
        except Exception:
            pass

        return booking

    @classmethod
    def reject_booking(cls, booking: BookingRequest, user=None, reason: str = "") -> BookingRequest:
        """Declines an unconfirmed booking request."""
        booking.status = BookingRequest.STATUS_REJECTED
        booking.rejection_reason = reason.strip() or "Declined by clinic (unavailable slot or medical scope mismatch)."
        booking.save(update_fields=['status', 'rejection_reason', 'updated_at'])

        BookingTimeline.objects.create(
            practice=booking.practice,
            booking=booking,
            performed_by=user,
            action='rejected',
            note=f"Booking request declined. Reason: {booking.rejection_reason}"
        )
        return booking

    @classmethod
    def update_visit_status(cls, booking: BookingRequest, new_status: str, user=None, notes: str = "") -> BookingRequest:
        """Updates clinical visit status: checked_in, in_consultation, or completed."""
        booking.status = new_status
        if notes:
            booking.clinic_notes = f"{booking.clinic_notes}\n{notes}".strip()
        booking.save()

        BookingTimeline.objects.create(
            practice=booking.practice,
            booking=booking,
            performed_by=user,
            action=new_status,
            note=notes or f"Visit status updated to {booking.get_status_display()}."
        )

        # Sync visit status with Patient CRM
        try:
            from patients.services.patient_service import PatientService
            from patients.models import PatientTimeline
            patient, _ = PatientService.get_or_create_patient(
                practice=booking.practice,
                phone_number=booking.phone_number,
                name=booking.patient_name,
            )
            if new_status == BookingRequest.STATUS_CHECKED_IN:
                PatientService.log_timeline_event(
                    patient=patient,
                    event_type=PatientTimeline.EVENT_PATIENT_CHECKED_IN,
                    title="Patient Checked In at Frontdesk",
                    description=f"Patient checked in for appointment {booking.booking_reference}.",
                    performed_by=user,
                    performer_role='receptionist',
                    metadata={"booking_reference": booking.booking_reference}
                )
            elif new_status == BookingRequest.STATUS_IN_CONSULTATION:
                PatientService.log_timeline_event(
                    patient=patient,
                    event_type=PatientTimeline.EVENT_CONSULTATION_STARTED,
                    title="In Consultation Room",
                    description=f"Consultation in progress with {getattr(booking.doctor.user, 'full_name', '') if booking.doctor else 'Doctor'}.",
                    performed_by=user,
                    performer_role='assistant',
                    metadata={"booking_reference": booking.booking_reference}
                )
            elif new_status == BookingRequest.STATUS_COMPLETED:
                patient.total_visits_count += 1
                patient.last_visit_date = booking.appointment_date or timezone.now().date()
                patient.save(update_fields=['total_visits_count', 'last_visit_date', 'updated_at'])
                PatientService.log_timeline_event(
                    patient=patient,
                    event_type=PatientTimeline.EVENT_CONSULTATION_COMPLETED,
                    title="Consultation Completed",
                    description=f"Consultation completed. Total visits: {patient.total_visits_count}.",
                    performed_by=user,
                    performer_role='doctor',
                    metadata={"booking_reference": booking.booking_reference}
                )
        except Exception:
            pass

        # If visit completed, schedule Google review reminder
        if new_status == BookingRequest.STATUS_COMPLETED:
            try:
                from whatsapp.services.reminder_service import WhatsAppReminderService
                WhatsAppReminderService.schedule_post_visit_review(booking)
            except Exception:
                pass

        return booking

    @classmethod
    def get_booking_stats(cls, practice: Practice) -> dict:
        """Returns dashboard metrics for appointments and queues."""
        today = timezone.now().date()
        qs = BookingRequest.objects.filter(practice=practice)

        # Status breakdown
        status_counts = dict(qs.values_list('status').annotate(count=Count('id')))

        today_qs = qs.filter(appointment_date=today)
        today_total = today_qs.count()
        today_confirmed = today_qs.filter(status=BookingRequest.STATUS_CONFIRMED).count()
        today_checked_in = today_qs.filter(status=BookingRequest.STATUS_CHECKED_IN).count()
        today_completed = today_qs.filter(status=BookingRequest.STATUS_COMPLETED).count()

        # Consultation mode breakdown
        mode_counts = dict(qs.values_list('consultation_mode').annotate(count=Count('id')))

        # Token vs Slot counts
        sched_mode_counts = dict(qs.values_list('booking_mode').annotate(count=Count('id')))

        return {
            "total_bookings": qs.count(),
            "pending_confirmation_count": status_counts.get(BookingRequest.STATUS_REQUESTED, 0),
            "confirmed_count": status_counts.get(BookingRequest.STATUS_CONFIRMED, 0),
            "completed_count": status_counts.get(BookingRequest.STATUS_COMPLETED, 0),
            "cancelled_count": status_counts.get(BookingRequest.STATUS_CANCELLED, 0),
            "rejected_count": status_counts.get(BookingRequest.STATUS_REJECTED, 0),
            "today": {
                "date": str(today),
                "total": today_total,
                "confirmed": today_confirmed,
                "checked_in_waiting": today_checked_in,
                "completed": today_completed,
            },
            "by_consultation_mode": {
                "in_person": mode_counts.get(BookingRequest.MODE_IN_PERSON, 0),
                "video": mode_counts.get(BookingRequest.MODE_VIDEO, 0),
                "phone": mode_counts.get(BookingRequest.MODE_PHONE, 0),
                "home_visit": mode_counts.get(BookingRequest.MODE_HOME_VISIT, 0),
            },
            "by_scheduling_mode": {
                "slot": sched_mode_counts.get(BookingRequest.SCHEDULING_MODE_SLOT, 0),
                "token": sched_mode_counts.get(BookingRequest.SCHEDULING_MODE_TOKEN, 0),
            }
        }

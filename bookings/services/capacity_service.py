import datetime
from datetime import time, timedelta
from django.db.models import Count, Q
from django.utils import timezone
from practices.models import DoctorProfile, DoctorSchedule, Practice
from bookings.models import BookingRequest, DoctorSessionCapacity, PracticeLocation


class CapacityService:
    """
    High-integrity capacity engine for medical practices.
    Handles schedule validation, time-slot collision checks,
    and session/token queue quota management.
    """

    @classmethod
    def get_doctor_schedule_for_date(cls, practice: Practice, doctor: DoctorProfile, target_date: datetime.date):
        """Fetches active schedule shifts for a doctor on a given day of the week."""
        # Python weekday: Monday=0, Sunday=6
        day_of_week = target_date.weekday()
        return DoctorSchedule.objects.filter(
            practice=practice,
            doctor=doctor,
            day_of_week=day_of_week,
            is_active=True
        ).order_by('start_time')

    @classmethod
    def check_capacity(
        cls,
        practice: Practice,
        doctor: DoctorProfile = None,
        appointment_date: datetime.date = None,
        booking_mode: str = BookingRequest.SCHEDULING_MODE_SLOT,
        session_name: str = "",
        start_time: time = None,
        end_time: time = None,
        exclude_booking_id = None
    ) -> dict:
        """
        Validates appointment availability against doctor schedules,
        maximum session tokens, and slot conflicts.
        """
        if not appointment_date:
            return {"available": False, "reason": "Appointment date is required."}

        # If no doctor assigned yet (general practice queue)
        if not doctor:
            return {
                "available": True,
                "booking_mode": booking_mode,
                "message": "Practice-wide request, awaiting doctor allocation."
            }

        # 1. Schedule existence check
        schedules = cls.get_doctor_schedule_for_date(practice, doctor, appointment_date)
        if not schedules.exists():
            day_name = appointment_date.strftime('%A')
            doc_name = getattr(doctor.user, 'full_name', str(doctor.user))
            return {
                "available": False,
                "reason": f"Dr. {doc_name} is not scheduled to consult on {day_name}s."
            }

        # 2. Session / Token Mode Capacity Check
        if booking_mode == BookingRequest.SCHEDULING_MODE_TOKEN:
            active_schedule = schedules.first()
            target_session = session_name.strip() or active_schedule.session_name or "General OPD"

            # Check custom capacity configuration
            capacity_config = DoctorSessionCapacity.objects.filter(
                practice=practice,
                doctor=doctor,
                session_name=target_session
            ).first()
            max_tokens = capacity_config.max_tokens_per_session if capacity_config else 25

            # Count existing active bookings for this doctor and session on this date
            booked_qs = BookingRequest.objects.filter(
                practice=practice,
                doctor=doctor,
                appointment_date=appointment_date,
                session_name=target_session,
                booking_mode=BookingRequest.SCHEDULING_MODE_TOKEN
            ).exclude(
                status__in=[BookingRequest.STATUS_CANCELLED, BookingRequest.STATUS_REJECTED]
            )

            if exclude_booking_id:
                booked_qs = booked_qs.exclude(id=exclude_booking_id)

            current_tokens = booked_qs.count()

            if current_tokens >= max_tokens:
                return {
                    "available": False,
                    "booking_mode": BookingRequest.SCHEDULING_MODE_TOKEN,
                    "session_name": target_session,
                    "current_tokens": current_tokens,
                    "max_tokens": max_tokens,
                    "reason": f"OPD session '{target_session}' has reached its maximum quota of {max_tokens} tokens."
                }

            next_token = current_tokens + 1
            remaining = max_tokens - current_tokens

            return {
                "available": True,
                "booking_mode": BookingRequest.SCHEDULING_MODE_TOKEN,
                "session_name": target_session,
                "current_tokens": current_tokens,
                "max_tokens": max_tokens,
                "next_token": next_token,
                "remaining_tokens": remaining,
                "message": f"Capacity available. Next in queue: Token #{next_token}."
            }

        # 3. Exact Time-Slot Mode Capacity Check
        else:
            if not start_time:
                # If only date is chosen without a slot, confirm doctor works that day
                return {
                    "available": True,
                    "booking_mode": BookingRequest.SCHEDULING_MODE_SLOT,
                    "message": "Doctor is available on this date. Select an available time slot."
                }

            # Check if start_time falls within any active schedule shift
            fits_schedule = False
            for sched in schedules:
                if sched.start_time <= start_time < sched.end_time:
                    fits_schedule = True
                    break

            if not fits_schedule:
                return {
                    "available": False,
                    "booking_mode": BookingRequest.SCHEDULING_MODE_SLOT,
                    "reason": f"Selected time {start_time.strftime('%H:%M')} is outside the doctor's consulting hours."
                }

            # Check collision with existing active bookings
            booked_conflict = BookingRequest.objects.filter(
                practice=practice,
                doctor=doctor,
                appointment_date=appointment_date,
                start_time=start_time,
                booking_mode=BookingRequest.SCHEDULING_MODE_SLOT
            ).exclude(
                status__in=[BookingRequest.STATUS_CANCELLED, BookingRequest.STATUS_REJECTED]
            )

            if exclude_booking_id:
                booked_conflict = booked_conflict.exclude(id=exclude_booking_id)

            if booked_conflict.exists():
                return {
                    "available": False,
                    "booking_mode": BookingRequest.SCHEDULING_MODE_SLOT,
                    "reason": f"Time slot {start_time.strftime('%H:%M')} is already booked for this doctor."
                }

            return {
                "available": True,
                "booking_mode": BookingRequest.SCHEDULING_MODE_SLOT,
                "slot": f"{start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M') if end_time else ''}",
                "message": "Time slot is available."
            }

    @classmethod
    def get_availability_overview(
        cls,
        practice: Practice,
        doctor: DoctorProfile,
        target_date: datetime.date
    ) -> dict:
        """
        Returns full availability snapshot for a doctor on a specific date,
        including generated time slots (with is_booked flag) and session token queues.
        """
        schedules = cls.get_doctor_schedule_for_date(practice, doctor, target_date)
        if not schedules.exists():
            return {
                "date": target_date,
                "is_available": False,
                "reason": f"No working schedule on {target_date.strftime('%A')}.",
                "sessions": [],
                "time_slots": []
            }

        # Check existing bookings for that day
        existing_bookings = BookingRequest.objects.filter(
            practice=practice,
            doctor=doctor,
            appointment_date=target_date
        ).exclude(
            status__in=[BookingRequest.STATUS_CANCELLED, BookingRequest.STATUS_REJECTED]
        )

        booked_start_times = set(
            b.start_time for b in existing_bookings if b.start_time
        )

        # Build Session/Token overview
        sessions_data = []
        for sched in schedules:
            session_name = sched.session_name or "General OPD"
            capacity_config = DoctorSessionCapacity.objects.filter(
                practice=practice,
                doctor=doctor,
                session_name=session_name
            ).first()
            max_tokens = capacity_config.max_tokens_per_session if capacity_config else 25

            token_count = existing_bookings.filter(
                session_name=session_name,
                booking_mode=BookingRequest.SCHEDULING_MODE_TOKEN
            ).count()

            sessions_data.append({
                "session_name": session_name,
                "start_time": sched.start_time.strftime('%H:%M'),
                "end_time": sched.end_time.strftime('%H:%M'),
                "current_tokens": token_count,
                "max_tokens": max_tokens,
                "remaining_tokens": max(0, max_tokens - token_count),
                "is_full": token_count >= max_tokens,
                "next_token": token_count + 1 if token_count < max_tokens else None
            })

        # Build Time-Slots overview (15 or 30 min intervals)
        all_slots = []
        for sched in schedules:
            interval_mins = sched.slot_duration_minutes or 15
            current_dt = datetime.datetime.combine(target_date, sched.start_time)
            end_dt = datetime.datetime.combine(target_date, sched.end_time)

            while current_dt + timedelta(minutes=interval_mins) <= end_dt:
                slot_start = current_dt.time()
                slot_end = (current_dt + timedelta(minutes=interval_mins)).time()
                is_booked = slot_start in booked_start_times

                all_slots.append({
                    "start_time": slot_start.strftime('%H:%M'),
                    "end_time": slot_end.strftime('%H:%M'),
                    "session_name": sched.session_name,
                    "is_available": not is_booked
                })
                current_dt += timedelta(minutes=interval_mins)

        return {
            "date": target_date,
            "day_of_week": target_date.strftime('%A'),
            "is_available": True,
            "sessions": sessions_data,
            "time_slots": all_slots
        }

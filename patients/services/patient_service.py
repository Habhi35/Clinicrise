import logging
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from patients.models import (
    Patient,
    PatientFollowUp,
    PatientNote,
    PatientTimeline,
    PatientVitals,
    normalize_patient_phone,
)

logger = logging.getLogger(__name__)


class PatientService:
    """
    Core domain service managing the patient lifecycle, clinical notes,
    vitals recorded by assistants, receptionist follow-up tasks, and unified timeline auditing.
    """

    @classmethod
    def get_or_create_patient(
        cls,
        practice,
        phone_number: str,
        name: str = "",
        email: str = "",
        gender: str = "unspecified",
        source: str = "walk_in",
        performed_by=None,
        role: str = ""
    ) -> tuple[Patient, bool]:
        """
        Idempotently resolves or registers a patient by normalized phone number.
        """
        normalized_phone = normalize_patient_phone(phone_number)
        patient = Patient.objects.filter(practice=practice, phone_number=normalized_phone).first()

        if patient:
            # Update missing attributes if supplied
            updated_fields = []
            if not patient.first_name and name:
                parts = name.strip().split(' ', 1)
                patient.first_name = parts[0]
                patient.last_name = parts[1] if len(parts) > 1 else ""
                updated_fields.extend(['first_name', 'last_name'])
            if not patient.email and email:
                patient.email = email
                updated_fields.append('email')
            if patient.gender == Patient.GENDER_UNSPECIFIED and gender != 'unspecified':
                patient.gender = gender
                updated_fields.append('gender')

            if updated_fields:
                patient.save(update_fields=updated_fields + ['updated_at'])
            return patient, False

        # Create new patient
        name_parts = name.strip().split(' ', 1) if name else ["Unnamed", ""]
        first_name = name_parts[0] or "Patient"
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        patient = Patient.objects.create(
            practice=practice,
            phone_number=normalized_phone,
            first_name=first_name,
            last_name=last_name,
            email=email or "",
            gender=gender,
            source=source,
        )

        cls.log_timeline_event(
            patient=patient,
            event_type=PatientTimeline.EVENT_PATIENT_CREATED,
            title="Patient Profile Created",
            description=f"Patient {patient.full_name} registered via {patient.get_source_display()}.",
            performed_by=performed_by,
            performer_role=role or "frontdesk",
            metadata={"source": source, "phone": normalized_phone}
        )

        return patient, True

    @classmethod
    @transaction.atomic
    def register_patient(cls, practice, data: dict, performed_by=None, role: str = "") -> Patient:
        """
        Explicitly registers a new patient with complete demographic and clinical fields.
        """
        phone = data.get('phone_number', '')
        normalized_phone = normalize_patient_phone(phone)

        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        if not first_name and data.get('full_name'):
            parts = data['full_name'].strip().split(' ', 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ""

        patient = Patient.objects.create(
            practice=practice,
            first_name=first_name or "New Patient",
            last_name=last_name,
            phone_number=normalized_phone,
            email=data.get('email', ''),
            gender=data.get('gender', Patient.GENDER_UNSPECIFIED),
            date_of_birth=data.get('date_of_birth'),
            age=data.get('age'),
            blood_group=data.get('blood_group', 'unknown'),
            address=data.get('address', ''),
            city=data.get('city', ''),
            postal_code=data.get('postal_code', ''),
            emergency_contact_name=data.get('emergency_contact_name', ''),
            emergency_contact_phone=data.get('emergency_contact_phone', ''),
            emergency_contact_relation=data.get('emergency_contact_relation', ''),
            allergies=data.get('allergies', ''),
            chronic_conditions=data.get('chronic_conditions', []),
            medical_alerts=data.get('medical_alerts', ''),
            tags=data.get('tags', []),
            source=data.get('source', Patient.SOURCE_WALK_IN),
            preferred_language=data.get('preferred_language', 'English'),
            primary_doctor_id=data.get('primary_doctor_id'),
        )

        cls.log_timeline_event(
            patient=patient,
            event_type=PatientTimeline.EVENT_PATIENT_CREATED,
            title="Patient Registered",
            description=f"Patient {patient.full_name} ({patient.patient_id}) registered at clinic.",
            performed_by=performed_by,
            performer_role=role or "receptionist",
            metadata={"patient_id": patient.patient_id, "allergies": bool(patient.allergies)}
        )

        return patient

    @classmethod
    @transaction.atomic
    def record_vitals(
        cls,
        patient: Patient,
        vitals_data: dict,
        recorded_by=None,
        role: str = "assistant",
        booking=None
    ) -> PatientVitals:
        """
        Records clinical vitals (BP, pulse, temp, SpO2, weight, height, BMI) by clinical assistant or nurse.
        """
        vitals = PatientVitals.objects.create(
            practice=patient.practice,
            patient=patient,
            recorded_by=recorded_by,
            booking=booking,
            blood_pressure_systolic=vitals_data.get('blood_pressure_systolic'),
            blood_pressure_diastolic=vitals_data.get('blood_pressure_diastolic'),
            pulse_bpm=vitals_data.get('pulse_bpm'),
            temperature_fahrenheit=vitals_data.get('temperature_fahrenheit'),
            oxygen_saturation_spo2=vitals_data.get('oxygen_saturation_spo2'),
            respiratory_rate=vitals_data.get('respiratory_rate'),
            weight_kg=vitals_data.get('weight_kg'),
            height_cm=vitals_data.get('height_cm'),
            blood_sugar_fasting=vitals_data.get('blood_sugar_fasting'),
            blood_sugar_random=vitals_data.get('blood_sugar_random'),
            notes=vitals_data.get('notes', ''),
        )

        # Build readable clinical summary
        parts = []
        if vitals.blood_pressure_systolic and vitals.blood_pressure_diastolic:
            parts.append(f"BP: {vitals.blood_pressure_systolic}/{vitals.blood_pressure_diastolic} mmHg")
        if vitals.pulse_bpm:
            parts.append(f"Pulse: {vitals.pulse_bpm} bpm")
        if vitals.temperature_fahrenheit:
            parts.append(f"Temp: {vitals.temperature_fahrenheit} °F")
        if vitals.oxygen_saturation_spo2:
            parts.append(f"SpO2: {vitals.oxygen_saturation_spo2}%")
        if vitals.weight_kg:
            parts.append(f"Weight: {vitals.weight_kg} kg")
        if vitals.bmi:
            parts.append(f"BMI: {vitals.bmi}")

        summary = ", ".join(parts) if parts else "Vitals recorded"
        if vitals.notes:
            summary += f" | Remarks: {vitals.notes}"

        cls.log_timeline_event(
            patient=patient,
            event_type=PatientTimeline.EVENT_VITALS_RECORDED,
            title="Vitals Recorded by Clinical Assistant",
            description=summary,
            performed_by=recorded_by,
            performer_role=role or "assistant",
            metadata={
                "vitals_id": str(vitals.id),
                "bp_systolic": vitals.blood_pressure_systolic,
                "bp_diastolic": vitals.blood_pressure_diastolic,
                "pulse": vitals.pulse_bpm,
                "spo2": vitals.oxygen_saturation_spo2,
            }
        )

        return vitals

    @classmethod
    @transaction.atomic
    def add_note(
        cls,
        patient: Patient,
        note_text: str,
        category: str = PatientNote.CATEGORY_GENERAL,
        author=None,
        role: str = "receptionist",
        is_pinned: bool = False
    ) -> PatientNote:
        """
        Adds a categorized note (frontdesk intake, clinical assistant prep, doctor consultation, follow-up).
        """
        note = PatientNote.objects.create(
            practice=patient.practice,
            patient=patient,
            author=author,
            author_role=role,
            category=category,
            note=note_text.strip(),
            is_pinned=is_pinned,
            pinned_at=timezone.now() if is_pinned else None,
            pinned_by=author if is_pinned else None,
        )

        title_map = {
            PatientNote.CATEGORY_FRONTDESK: "Frontdesk / Reception Note Added",
            PatientNote.CATEGORY_CLINICAL_PREP: "Clinical Prep Note by Assistant",
            PatientNote.CATEGORY_DOCTOR: "Doctor Consultation Note Added",
            PatientNote.CATEGORY_FOLLOW_UP: "Follow-up Call Outcome Logged",
            PatientNote.CATEGORY_GENERAL: "Clinical Note Added",
        }
        title = title_map.get(category, "Clinical Note Added")
        if is_pinned:
            title += " [PINNED ALERT]"

        cls.log_timeline_event(
            patient=patient,
            event_type=PatientTimeline.EVENT_CLINICAL_NOTE,
            title=title,
            description=note.note,
            performed_by=author,
            performer_role=role,
            metadata={"note_id": str(note.id), "category": category, "is_pinned": is_pinned}
        )

        return note

    @classmethod
    @transaction.atomic
    def schedule_follow_up(
        cls,
        patient: Patient,
        data: dict,
        created_by=None,
        role: str = "receptionist",
        booking=None
    ) -> PatientFollowUp:
        """
        Schedules a follow-up task for receptionists, assistants, or doctors.
        """
        due_date = data.get('due_date')
        if isinstance(due_date, str):
            due_date = timezone.datetime.fromisoformat(due_date.replace('Z', '+00:00'))

        follow_up = PatientFollowUp.objects.create(
            practice=patient.practice,
            patient=patient,
            booking=booking,
            created_by=created_by,
            assigned_to_id=data.get('assigned_to_id') or (created_by.id if created_by else None),
            follow_up_type=data.get('follow_up_type', PatientFollowUp.TYPE_POST_CONSULTATION),
            priority=data.get('priority', PatientFollowUp.PRIORITY_MEDIUM),
            due_date=due_date,
            title=data.get('title', 'Routine Patient Follow-Up'),
            instructions=data.get('instructions', ''),
        )

        cls.log_timeline_event(
            patient=patient,
            event_type=PatientTimeline.EVENT_FOLLOW_UP_SCHEDULED,
            title=f"Follow-up Scheduled: {follow_up.title}",
            description=f"Due on {follow_up.due_date.strftime('%Y-%m-%d %H:%M')}. Type: {follow_up.get_follow_up_type_display()}. Priority: {follow_up.get_priority_display()}.",
            performed_by=created_by,
            performer_role=role,
            metadata={
                "follow_up_id": str(follow_up.id),
                "type": follow_up.follow_up_type,
                "priority": follow_up.priority,
            }
        )

        return follow_up

    @classmethod
    @transaction.atomic
    def complete_follow_up(
        cls,
        follow_up: PatientFollowUp,
        outcome_notes: str,
        completed_by=None,
        role: str = "receptionist"
    ) -> PatientFollowUp:
        """
        Marks a follow-up task completed, records the outcome, and logs to timeline and notes.
        """
        follow_up.complete(user=completed_by, outcome_notes=outcome_notes)

        # Automatically record a follow-up note
        cls.add_note(
            patient=follow_up.patient,
            note_text=f"Follow-up completed: {follow_up.title}\nOutcome: {outcome_notes}",
            category=PatientNote.CATEGORY_FOLLOW_UP,
            author=completed_by,
            role=role,
            is_pinned=False
        )

        cls.log_timeline_event(
            patient=follow_up.patient,
            event_type=PatientTimeline.EVENT_FOLLOW_UP_COMPLETED,
            title=f"Follow-up Completed: {follow_up.title}",
            description=outcome_notes,
            performed_by=completed_by,
            performer_role=role,
            metadata={"follow_up_id": str(follow_up.id), "completed_at": follow_up.completed_at.isoformat()}
        )

        return follow_up

    @classmethod
    @transaction.atomic
    def log_phone_call(
        cls,
        patient: Patient,
        call_type: str = "outgoing",
        outcome: str = "answered",
        notes: str = "",
        performed_by=None,
        role: str = "receptionist"
    ) -> PatientTimeline:
        """
        Logs a phone call touchpoint by frontdesk receptionists.
        """
        desc = f"Call Type: {call_type.title()} | Outcome: {outcome.title()}"
        if notes:
            desc += f"\nNotes: {notes}"

        # Add frontdesk note
        cls.add_note(
            patient=patient,
            note_text=f"Phone Call Logged ({call_type.title()} - {outcome.title()}): {notes}",
            category=PatientNote.CATEGORY_FRONTDESK,
            author=performed_by,
            role=role
        )

        return cls.log_timeline_event(
            patient=patient,
            event_type=PatientTimeline.EVENT_PHONE_CALL,
            title=f"Phone Call Logged ({call_type.title()} - {outcome.title()})",
            description=desc,
            performed_by=performed_by,
            performer_role=role,
            metadata={"call_type": call_type, "outcome": outcome}
        )

    @classmethod
    @transaction.atomic
    def convert_lead_to_patient(cls, lead, performed_by=None, role: str = "receptionist") -> Patient:
        """
        Converts an omnichannel prospective lead into a full registered patient record.
        """
        patient, created = cls.get_or_create_patient(
            practice=lead.practice,
            phone_number=lead.phone_number,
            name=lead.patient_name,
            email=lead.email,
            source=Patient.SOURCE_LEAD_CONVERSION,
            performed_by=performed_by,
            role=role
        )

        patient.converted_from_lead = lead
        patient.save(update_fields=['converted_from_lead', 'updated_at'])

        # Update lead state to converted
        lead.status = 'converted'
        lead.save(update_fields=['status', 'updated_at'])

        cls.log_timeline_event(
            patient=patient,
            event_type=PatientTimeline.EVENT_PATIENT_CREATED,
            title="Converted from Prospective Lead",
            description=f"Patient converted from Lead inquiry #{lead.id}. Message: {lead.message or 'N/A'}",
            performed_by=performed_by,
            performer_role=role,
            metadata={"lead_id": str(lead.id), "lead_source": lead.source}
        )

        return patient

    @classmethod
    def log_timeline_event(
        cls,
        patient: Patient,
        event_type: str,
        title: str,
        description: str = "",
        performed_by=None,
        performer_role: str = "",
        metadata: dict = None
    ) -> PatientTimeline:
        """
        Creates an entry on the patient's unified audit timeline.
        """
        return PatientTimeline.objects.create(
            practice=patient.practice,
            patient=patient,
            performed_by=performed_by,
            performer_role=performer_role or "",
            event_type=event_type,
            title=title,
            description=description,
            metadata=metadata or {},
        )

    @classmethod
    def get_practice_crm_overview(cls, practice) -> dict:
        """
        Returns practice CRM dashboard metrics (patient counts, follow-ups queue, vitals trends).
        """
        now = timezone.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_today = start_of_today + timedelta(days=1)

        total_patients = Patient.objects.filter(practice=practice, status=Patient.STATUS_ACTIVE).count()
        new_this_month = Patient.objects.filter(
            practice=practice,
            status=Patient.STATUS_ACTIVE,
            created_at__gte=start_of_month
        ).count()

        pending_followups = PatientFollowUp.objects.filter(
            practice=practice,
            status__in=[PatientFollowUp.STATUS_PENDING, PatientFollowUp.STATUS_IN_PROGRESS]
        )
        total_pending_followups = pending_followups.count()
        due_today_followups = pending_followups.filter(
            due_date__gte=start_of_today,
            due_date__lt=end_of_today
        ).count()
        overdue_followups = pending_followups.filter(due_date__lt=start_of_today).count()

        pinned_alerts_count = PatientNote.objects.filter(
            practice=practice,
            is_pinned=True
        ).count()

        return {
            "total_active_patients": total_patients,
            "new_patients_this_month": new_this_month,
            "pending_followups_count": total_pending_followups,
            "followups_due_today": due_today_followups,
            "followups_overdue": overdue_followups,
            "pinned_clinical_alerts_count": pinned_alerts_count,
        }

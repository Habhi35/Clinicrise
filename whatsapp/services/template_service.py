import re
from typing import Dict, Any, Tuple
from whatsapp.models import WhatsAppTemplate


class WhatsAppTemplateService:
    """
    Template management, standard clinical template seeding,
    and dynamic parameter rendering engine.
    """

    DEFAULT_TEMPLATES = [
        {
            "template_name": "appointment_confirmation_slot",
            "title": "Appointment Confirmation (Time-Slot Mode)",
            "category": WhatsAppTemplate.CATEGORY_UTILITY,
            "language": "en_US",
            "header_type": WhatsAppTemplate.HEADER_TEXT,
            "header_text": "Appointment Confirmed",
            "body_text": (
                "Hello {{1}}, your appointment with {{2}} is confirmed for {{3}} at {{4}}.\n\n"
                "Clinic: {{5}}\n"
                "Address: {{6}}\n"
                "Reference: {{7}}\n\n"
                "Please arrive 10 minutes early. Need directions or changes? Use the buttons below."
            ),
            "footer_text": "Reply STOP to unsubscribe",
            "buttons": [
                {"type": "URL", "text": "View Directions", "url": "{{maps_url}}"},
                {"type": "QUICK_REPLY", "text": "Reschedule"},
                {"type": "QUICK_REPLY", "text": "Cancel"}
            ],
            "variable_mapping": {
                "1": "patient_name",
                "2": "doctor_name",
                "3": "appointment_date",
                "4": "start_time",
                "5": "clinic_name",
                "6": "clinic_address",
                "7": "booking_reference",
                "maps_url": "maps_link"
            }
        },
        {
            "template_name": "appointment_confirmation_token",
            "title": "Appointment Confirmation (OPD Token Mode)",
            "category": WhatsAppTemplate.CATEGORY_UTILITY,
            "language": "en_US",
            "header_type": WhatsAppTemplate.HEADER_TEXT,
            "header_text": "OPD Token Confirmed",
            "body_text": (
                "Hello {{1}}, your consultation queue token with {{2}} is confirmed.\n\n"
                "Date: {{3}}\n"
                "Session: {{4}}\n"
                "Token Number: #{{5}}\n"
                "Est. Arrival: {{6}}\n\n"
                "Clinic: {{7}}\n"
                "Reference: {{8}}\n\n"
                "Track live queue status using the link below."
            ),
            "footer_text": "Reply STOP to unsubscribe",
            "buttons": [
                {"type": "URL", "text": "Live Queue Status", "url": "{{queue_url}}"},
                {"type": "QUICK_REPLY", "text": "Opt Out"}
            ],
            "variable_mapping": {
                "1": "patient_name",
                "2": "doctor_name",
                "3": "appointment_date",
                "4": "session_name",
                "5": "token_number",
                "6": "estimated_arrival",
                "7": "clinic_name",
                "8": "booking_reference",
                "queue_url": "queue_url"
            }
        },
        {
            "template_name": "appointment_reminder_24h",
            "title": "24-Hour Advance Appointment Reminder",
            "category": WhatsAppTemplate.CATEGORY_UTILITY,
            "language": "en_US",
            "header_type": WhatsAppTemplate.HEADER_TEXT,
            "header_text": "Appointment Reminder",
            "body_text": (
                "Hi {{1}}, reminder that you have an appointment with {{2}} tomorrow, {{3}} at {{4}}.\n\n"
                "Clinic: {{5}}\n"
                "Location: {{6}}\n\n"
                "Please confirm if you will be attending or reply to reschedule."
            ),
            "footer_text": "Reply STOP to unsubscribe",
            "buttons": [
                {"type": "QUICK_REPLY", "text": "Confirm Attending"},
                {"type": "QUICK_REPLY", "text": "Need Reschedule"}
            ],
            "variable_mapping": {
                "1": "patient_name",
                "2": "doctor_name",
                "3": "appointment_date",
                "4": "time_or_token",
                "5": "clinic_name",
                "6": "clinic_address"
            }
        },
        {
            "template_name": "appointment_reminder_2h",
            "title": "2-Hour Immediate Consultation Reminder",
            "category": WhatsAppTemplate.CATEGORY_UTILITY,
            "language": "en_US",
            "header_type": WhatsAppTemplate.HEADER_TEXT,
            "header_text": "Consultation Starting Soon",
            "body_text": (
                "Hi {{1}}, your consultation with {{2}} at {{3}} is scheduled in 2 hours (at {{4}}).\n\n"
                "Address: {{5}}\n"
                "Booking Reference: {{6}}\n\n"
                "Safe travels! Tap below for Google Maps directions."
            ),
            "footer_text": "Reply STOP to unsubscribe",
            "buttons": [
                {"type": "URL", "text": "Get Directions", "url": "{{maps_url}}"}
            ],
            "variable_mapping": {
                "1": "patient_name",
                "2": "doctor_name",
                "3": "clinic_name",
                "4": "time_or_token",
                "5": "clinic_address",
                "6": "booking_reference",
                "maps_url": "maps_link"
            }
        },
        {
            "template_name": "appointment_rescheduled",
            "title": "Appointment Rescheduled Notice",
            "category": WhatsAppTemplate.CATEGORY_UTILITY,
            "language": "en_US",
            "header_type": WhatsAppTemplate.HEADER_TEXT,
            "header_text": "Appointment Rescheduled",
            "body_text": (
                "Hello {{1}}, your appointment with {{2}} has been rescheduled.\n\n"
                "New Date: {{3}}\n"
                "New Time / Token: {{4}}\n"
                "Clinic: {{5}}\n"
                "Reference: {{6}}\n\n"
                "If this time does not work for you, please contact the clinic."
            ),
            "footer_text": "Reply STOP to unsubscribe",
            "buttons": [
                {"type": "URL", "text": "Contact Clinic", "url": "{{clinic_url}}"}
            ],
            "variable_mapping": {
                "1": "patient_name",
                "2": "doctor_name",
                "3": "appointment_date",
                "4": "time_or_token",
                "5": "clinic_name",
                "6": "booking_reference",
                "clinic_url": "clinic_url"
            }
        },
        {
            "template_name": "appointment_cancelled",
            "title": "Appointment Cancelled Notice",
            "category": WhatsAppTemplate.CATEGORY_UTILITY,
            "language": "en_US",
            "header_type": WhatsAppTemplate.HEADER_TEXT,
            "header_text": "Appointment Cancelled",
            "body_text": (
                "Hello {{1}}, your appointment with {{2}} on {{3}} has been cancelled.\n\n"
                "Reason: {{4}}\n\n"
                "To book a new appointment or speak to reception, tap below or call {{5}}."
            ),
            "footer_text": "Reply STOP to unsubscribe",
            "buttons": [
                {"type": "URL", "text": "Book New Visit", "url": "{{booking_url}}"}
            ],
            "variable_mapping": {
                "1": "patient_name",
                "2": "doctor_name",
                "3": "appointment_date",
                "4": "cancellation_reason",
                "5": "clinic_phone",
                "booking_url": "booking_url"
            }
        },
        {
            "template_name": "lead_welcome_acknowledgement",
            "title": "Lead / Enquiry Welcome Acknowledgement",
            "category": WhatsAppTemplate.CATEGORY_UTILITY,
            "language": "en_US",
            "header_type": WhatsAppTemplate.HEADER_TEXT,
            "header_text": "Enquiry Received",
            "body_text": (
                "Hello {{1}}, thank you for contacting {{2}}!\n\n"
                "We have received your enquiry regarding {{3}}. Our patient coordinator will contact you shortly.\n\n"
                "If urgent, you can call us directly at {{4}}."
            ),
            "footer_text": "Reply STOP to unsubscribe",
            "buttons": [
                {"type": "QUICK_REPLY", "text": "Opt Out"}
            ],
            "variable_mapping": {
                "1": "patient_name",
                "2": "clinic_name",
                "3": "service_requested",
                "4": "clinic_phone"
            }
        },
        {
            "template_name": "post_visit_review_request",
            "title": "Post-Consultation Google Review Request",
            "category": WhatsAppTemplate.CATEGORY_MARKETING,
            "language": "en_US",
            "header_type": WhatsAppTemplate.HEADER_TEXT,
            "header_text": "How Was Your Visit?",
            "body_text": (
                "Dear {{1}}, thank you for visiting {{2}} for your consultation with {{3}}! We hope you received compassionate care.\n\n"
                "Could you take 30 seconds to share your review on Google? It helps others find trusted healthcare in our community:\n"
                "{{4}}\n\n"
                "— Team {{2}}"
            ),
            "footer_text": "Reply STOP to unsubscribe",
            "buttons": [
                {"type": "URL", "text": "Write a Review", "url": "{{google_review_url}}"},
                {"type": "QUICK_REPLY", "text": "Opt Out"}
            ],
            "variable_mapping": {
                "1": "patient_name",
                "2": "clinic_name",
                "3": "doctor_name",
                "4": "google_review_url",
                "google_review_url": "google_review_url"
            }
        }
    ]

    @classmethod
    def seed_default_templates(cls, practice) -> int:
        """
        Seeds standard clinical templates for a practice if they do not exist yet.
        Returns the number of templates created.
        """
        created_count = 0
        for tpl_data in cls.DEFAULT_TEMPLATES:
            obj, created = WhatsAppTemplate.objects.get_or_create(
                practice=practice,
                template_name=tpl_data['template_name'],
                language=tpl_data['language'],
                defaults={
                    "title": tpl_data['title'],
                    "category": tpl_data['category'],
                    "header_type": tpl_data['header_type'],
                    "header_text": tpl_data['header_text'],
                    "body_text": tpl_data['body_text'],
                    "footer_text": tpl_data['footer_text'],
                    "buttons": tpl_data['buttons'],
                    "variable_mapping": tpl_data['variable_mapping'],
                    "is_active": True,
                    "is_system_default": True,
                    "meta_status": WhatsAppTemplate.STATUS_APPROVED
                }
            )
            if created:
                created_count += 1
        return created_count

    @classmethod
    def render_template(cls, template: WhatsAppTemplate, context: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """
        Replaces indexed {{1}}, {{2}} and named {{variable}} placeholders with context values.
        Returns rendered text and resolved parameters dict.
        """
        body = template.body_text
        mapping = template.variable_mapping or {}
        resolved_params = {}

        # 1. Resolve indexed variables (e.g. {{1}} -> mapping["1"] -> context value)
        for index_str, key in mapping.items():
            if index_str.isdigit():
                val = str(context.get(key, ''))
                resolved_params[index_str] = val
                body = body.replace(f"{{{{{index_str}}}}}", val)

        # 2. Resolve named variables directly (e.g. {{patient_name}})
        for key, val in context.items():
            token = f"{{{{{key}}}}}"
            if token in body:
                body = body.replace(token, str(val or ''))
                resolved_params[key] = str(val or '')

        # 3. Clean up any remaining unresolved {{...}} placeholders with fallback
        body = re.sub(r'\{\{[^\}]+\}\}', '', body)

        return body.strip(), resolved_params

    @classmethod
    def build_sample_context(cls, template_name: str, practice=None) -> Dict[str, Any]:
        """Provides realistic sample healthcare context for template preview and validation."""
        clinic_name = practice.name if practice else "City Medical & Dental Care"
        return {
            "patient_name": "Meera Nambiar",
            "doctor_name": "Dr. Rajesh Sharma, MD",
            "appointment_date": "2026-10-28",
            "start_time": "10:30 AM",
            "session_name": "Morning General OPD",
            "token_number": "14",
            "estimated_arrival": "10:15 AM",
            "time_or_token": "10:30 AM (Token #14)",
            "clinic_name": clinic_name,
            "clinic_address": "Road No 36, Jubilee Hills, Hyderabad",
            "clinic_phone": "+919876543210",
            "booking_reference": "CR-202610-8F9A",
            "service_requested": "Dental Cleaning & Consultation",
            "cancellation_reason": "Patient requested cancellation due to travel",
            "maps_link": "https://maps.google.com/?q=Apollo+Dental+Hyderabad",
            "queue_url": "https://clinicrise.com/queue/CR-202610-8F9A",
            "booking_url": "https://clinicrise.com/book",
            "clinic_url": "https://clinicrise.com",
            "google_review_url": "https://search.google.com/local/writereview?placeid=ChIJ_sample"
        }

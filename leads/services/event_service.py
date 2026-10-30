from django.utils import timezone
from practices.models import Practice
from leads.models import ClickEvent, Lead, LeadActivity


class EventTrackingService:
    """
    Service for recording call clicks, WhatsApp chats, and CTA clicks.
    Optionally converts click events into actionable leads when phone numbers are provided.
    """

    @classmethod
    def track_click(cls, practice: Practice, data: dict, request=None, website=None):
        """
        Records a ClickEvent and optionally links or creates a Lead.
        """
        ip_address = None
        user_agent = ""
        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0].strip()
            else:
                ip_address = request.META.get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_AGENT', '')

        event_type = data.get('event_type')
        phone_number = (data.get('phone_number') or '').strip()
        patient_name = (data.get('patient_name') or '').strip()

        lead = None
        # If visitor provided their phone number before initiating Call/WhatsApp:
        if phone_number:
            source = (
                Lead.SOURCE_CALL_CLICK if event_type == ClickEvent.TYPE_CALL_CLICK
                else Lead.SOURCE_WHATSAPP_CLICK if event_type == ClickEvent.TYPE_WHATSAPP_CLICK
                else Lead.SOURCE_WEBSITE_FORM
            )

            consent_text = (
                f"Consent provided during {event_type.replace('_', ' ').title()} "
                f"on {practice.name} clinic site."
            )

            lead = Lead.objects.create(
                practice=practice,
                website=website,
                patient_name=patient_name or f"Visitor ({phone_number[-4:] if len(phone_number)>=4 else phone_number})",
                phone_number=phone_number,
                service_requested=data.get('service_name', ''),
                doctor_requested=data.get('doctor_name', ''),
                status=Lead.STATUS_NEW,
                priority=Lead.PRIORITY_HIGH if event_type in [ClickEvent.TYPE_CALL_CLICK, ClickEvent.TYPE_WHATSAPP_CLICK] else Lead.PRIORITY_MEDIUM,
                source=source,
                source_url=data.get('page_url', ''),
                referrer=data.get('referrer', ''),
                utm_source=data.get('utm_source', ''),
                utm_medium=data.get('utm_medium', ''),
                utm_campaign=data.get('utm_campaign', ''),
                device_type=data.get('device_type', ''),
                ip_address=ip_address,
                user_agent=user_agent,
                consent_given=data.get('consent_given', True),
                consent_timestamp=timezone.now(),
                consent_text=consent_text,
                consent_ip_address=ip_address,
                whatsapp_opt_in=True,
                call_opt_in=True,
            )

            LeadActivity.objects.create(
                practice=practice,
                lead=lead,
                activity_type=LeadActivity.TYPE_STATUS_CHANGE,
                previous_status="",
                new_status=Lead.STATUS_NEW,
                note=f"High-intent lead created via {dict(ClickEvent.EVENT_CHOICES).get(event_type, event_type)}.",
                metadata={"target_phone": data.get('target_phone')}
            )

        event = ClickEvent.objects.create(
            practice=practice,
            website=website,
            event_type=event_type,
            target_phone=data.get('target_phone', ''),
            doctor_id=data.get('doctor_id'),
            doctor_name=data.get('doctor_name', ''),
            service_name=data.get('service_name', ''),
            page_url=data.get('page_url', ''),
            referrer=data.get('referrer', ''),
            utm_source=data.get('utm_source', ''),
            utm_medium=data.get('utm_medium', ''),
            utm_campaign=data.get('utm_campaign', ''),
            visitor_id=data.get('visitor_id', ''),
            ip_address=ip_address,
            user_agent=user_agent,
            device_type=data.get('device_type', ''),
            lead=lead
        )

        return event, lead

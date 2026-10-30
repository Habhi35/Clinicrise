import uuid
from datetime import timedelta
from django.db.models import Count, Q
from django.utils import timezone
from practices.models import Practice
from websites.models import ClinicWebsite, CustomDomain
from leads.models import Lead, LeadActivity, ClickEvent


class LeadService:
    """
    Core business service handling Lead lifecycle, enquiry ingestion,
    consent management, status transitions, and CRM inbox analytics.
    """

    @classmethod
    def resolve_practice_and_website(cls, identifier: str):
        """
        Resolves a Practice (and optional ClinicWebsite) from:
        1. Practice UUID
        2. Practice slug (e.g. 'city-dental-care-a1b2')
        3. Custom live domain (e.g. 'www.citydental.com')
        4. Free subdomain (e.g. 'citydental')
        """
        clean_target = identifier.strip().lower()

        # 1. Try Practice UUID
        try:
            target_uuid = uuid.UUID(clean_target)
            practice = Practice.objects.filter(id=target_uuid, is_active=True).first()
            if practice:
                website = ClinicWebsite.objects.filter(practice=practice).first()
                return practice, website
        except (ValueError, TypeError):
            pass

        # 2. Try Practice slug
        practice = Practice.objects.filter(slug=clean_target, is_active=True).first()
        if practice:
            website = ClinicWebsite.objects.filter(practice=practice).first()
            return practice, website

        # 3. Try Custom Domain
        custom_domain = (
            CustomDomain.objects.filter(domain=clean_target, status=CustomDomain.STATUS_ACTIVE)
            .select_related('website__practice')
            .first()
        )
        if custom_domain and custom_domain.website:
            return custom_domain.website.practice, custom_domain.website

        # 4. Try Website Subdomain
        website = (
            ClinicWebsite.objects.filter(subdomain=clean_target)
            .select_related('practice')
            .first()
        )
        if website:
            return website.practice, website

        return None, None

    @classmethod
    def create_lead_from_enquiry(cls, practice: Practice, data: dict, request=None, website=None) -> Lead:
        """
        Ingests a public enquiry form into a new Lead with consent audit logging.
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

        consent_text = data.get('consent_text') or (
            f"I agree to receive communications regarding my enquiry via Phone, WhatsApp, SMS and Email "
            f"from {practice.name} and the healthcare team."
        )

        lead = Lead.objects.create(
            practice=practice,
            website=website,
            patient_name=data.get('patient_name', '').strip(),
            phone_number=data.get('phone_number', '').strip(),
            email=data.get('email', '').strip(),
            preferred_date=data.get('preferred_date'),
            preferred_time_slot=data.get('preferred_time_slot', '').strip(),
            service_requested=data.get('service_requested', '').strip(),
            doctor_requested=data.get('doctor_requested', '').strip(),
            message=data.get('message', '').strip(),
            status=Lead.STATUS_NEW,
            priority=Lead.PRIORITY_MEDIUM,
            is_read=False,
            source=Lead.SOURCE_WEBSITE_FORM,
            source_url=data.get('source_url', ''),
            referrer=data.get('referrer', ''),
            utm_source=data.get('utm_source', ''),
            utm_medium=data.get('utm_medium', ''),
            utm_campaign=data.get('utm_campaign', ''),
            utm_term=data.get('utm_term', ''),
            utm_content=data.get('utm_content', ''),
            device_type=data.get('device_type', ''),
            ip_address=ip_address,
            user_agent=user_agent,
            consent_given=data.get('consent_given', True),
            consent_timestamp=timezone.now(),
            consent_text=consent_text,
            consent_ip_address=ip_address,
            whatsapp_opt_in=data.get('whatsapp_opt_in', True),
            call_opt_in=data.get('call_opt_in', True),
            sms_opt_in=data.get('sms_opt_in', True),
            email_opt_in=data.get('email_opt_in', True),
        )

        # Create initial audit activity
        LeadActivity.objects.create(
            practice=practice,
            lead=lead,
            activity_type=LeadActivity.TYPE_STATUS_CHANGE,
            previous_status="",
            new_status=Lead.STATUS_NEW,
            note=f"Enquiry form submitted by {lead.patient_name} via {website.title if website else 'clinic website'}.",
            metadata={
                "ip_address": ip_address,
                "preferred_date": str(lead.preferred_date) if lead.preferred_date else None,
                "service": lead.service_requested,
            }
        )

        # Trigger automated WhatsApp welcome acknowledgment & follow-up reminder
        if lead.whatsapp_opt_in:
            try:
                from whatsapp.services.message_service import WhatsAppMessageService
                from whatsapp.services.reminder_service import WhatsAppReminderService
                WhatsAppMessageService.send_lead_acknowledgement(lead)
                WhatsAppReminderService.schedule_lead_follow_up(lead)
            except Exception:
                pass

        return lead

    create_lead = create_lead_from_enquiry

    @classmethod
    def update_lead_status(
        cls,
        lead: Lead,
        new_status: str,
        performed_by=None,
        note: str = "",
        follow_up_date=None,
        lost_reason: str = ""
    ) -> Lead:
        """
        Executes a status transition, updating timestamps and recording an activity entry.
        """
        old_status = lead.status
        lead.status = new_status

        update_fields = ['status', 'updated_at']

        if new_status == Lead.STATUS_CONTACTED and not lead.last_contacted_at:
            lead.last_contacted_at = timezone.now()
            update_fields.append('last_contacted_at')

        if follow_up_date is not None:
            lead.follow_up_date = follow_up_date
            update_fields.append('follow_up_date')

        if lost_reason:
            lead.lost_reason = lost_reason
            update_fields.append('lost_reason')

        lead.save(update_fields=update_fields)

        # Log transition into timeline
        note_text = note.strip() or f"Status changed from '{lead.get_status_display()}' to '{dict(Lead.STATUS_CHOICES).get(new_status, new_status)}'."
        LeadActivity.objects.create(
            practice=lead.practice,
            lead=lead,
            performed_by=performed_by,
            activity_type=LeadActivity.TYPE_STATUS_CHANGE,
            previous_status=old_status,
            new_status=new_status,
            note=note_text,
            metadata={
                "lost_reason": lost_reason,
                "follow_up_date": str(follow_up_date) if follow_up_date else None
            }
        )

        return lead

    @classmethod
    def update_consent(cls, lead: Lead, data: dict, performed_by=None) -> Lead:
        """
        Updates consent preferences or processes consent withdrawal.
        """
        if data.get('consent_withdrawn'):
            lead.withdraw_consent(
                reason=data.get('consent_withdrawn_reason', 'Patient requested consent revocation'),
                performed_by=performed_by
            )
            return lead

        updated_fields = ['updated_at']
        notes = []

        for field in ['whatsapp_opt_in', 'call_opt_in', 'sms_opt_in', 'email_opt_in']:
            if field in data and getattr(lead, field) != data[field]:
                setattr(lead, field, data[field])
                updated_fields.append(field)
                notes.append(f"{field.replace('_', ' ').capitalize()}: {'Enabled' if data[field] else 'Disabled'}")

        if len(updated_fields) > 1:
            lead.save(update_fields=updated_fields)
            LeadActivity.objects.create(
                practice=lead.practice,
                lead=lead,
                performed_by=performed_by,
                activity_type=LeadActivity.TYPE_CONSENT_CHANGE,
                note=f"Consent updated: {', '.join(notes)}"
            )

        return lead

    @classmethod
    def get_inbox_metrics(cls, practice: Practice) -> dict:
        """
        Aggregates lead inbox counters, pipeline breakdown, conversion rates,
        and click events for dashboard analytics.
        """
        now = timezone.now()
        start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_of_week = start_of_today - timedelta(days=now.weekday())
        start_of_month = start_of_today.replace(day=1)

        qs = Lead.objects.filter(practice=practice)

        # Status counts
        status_counts = dict(
            qs.values_list('status').annotate(count=Count('id'))
        )

        total_leads = qs.count()
        new_leads = status_counts.get(Lead.STATUS_NEW, 0)
        contacted_leads = status_counts.get(Lead.STATUS_CONTACTED, 0)
        in_discussion_leads = status_counts.get(Lead.STATUS_IN_DISCUSSION, 0)
        appointment_scheduled_leads = status_counts.get(Lead.STATUS_APPOINTMENT_SCHEDULED, 0)
        converted_leads = status_counts.get(Lead.STATUS_CONVERTED, 0)
        lost_leads = status_counts.get(Lead.STATUS_LOST, 0)
        junk_leads = status_counts.get(Lead.STATUS_JUNK, 0)

        unread_count = qs.filter(is_read=False).count()

        # Conversion Rate = (converted / total) * 100
        conversion_rate = round((converted_leads / total_leads * 100), 2) if total_leads > 0 else 0.0

        # Time-based counts
        leads_today = qs.filter(created_at__gte=start_of_today).count()
        leads_this_week = qs.filter(created_at__gte=start_of_week).count()
        leads_this_month = qs.filter(created_at__gte=start_of_month).count()

        # Breakdown by Source
        source_breakdown = dict(
            qs.values_list('source').annotate(count=Count('id'))
        )

        # Click Events Metrics
        click_events_qs = ClickEvent.objects.filter(practice=practice)
        total_call_clicks = click_events_qs.filter(event_type=ClickEvent.TYPE_CALL_CLICK).count()
        total_whatsapp_clicks = click_events_qs.filter(event_type=ClickEvent.TYPE_WHATSAPP_CLICK).count()
        total_clicks_today = click_events_qs.filter(created_at__gte=start_of_today).count()

        return {
            "total_leads": total_leads,
            "unread_count": unread_count,
            "conversion_rate_percentage": conversion_rate,
            "pipeline": {
                "new": new_leads,
                "contacted": contacted_leads,
                "in_discussion": in_discussion_leads,
                "appointment_scheduled": appointment_scheduled_leads,
                "converted": converted_leads,
                "lost": lost_leads,
                "junk": junk_leads,
            },
            "time_stats": {
                "today": leads_today,
                "this_week": leads_this_week,
                "this_month": leads_this_month,
            },
            "source_breakdown": {
                "website_form": source_breakdown.get(Lead.SOURCE_WEBSITE_FORM, 0),
                "whatsapp_click": source_breakdown.get(Lead.SOURCE_WHATSAPP_CLICK, 0),
                "call_click": source_breakdown.get(Lead.SOURCE_CALL_CLICK, 0),
                "manual": source_breakdown.get(Lead.SOURCE_MANUAL, 0),
                "campaign": source_breakdown.get(Lead.SOURCE_CAMPAIGN, 0),
                "referral": source_breakdown.get(Lead.SOURCE_REFERRAL, 0),
                "other": source_breakdown.get(Lead.SOURCE_OTHER, 0),
            },
            "click_events": {
                "total_call_clicks": total_call_clicks,
                "total_whatsapp_clicks": total_whatsapp_clicks,
                "total_clicks_today": total_clicks_today,
            }
        }

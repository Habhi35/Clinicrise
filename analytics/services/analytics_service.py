import datetime
from datetime import timedelta
from django.db.models import Count, Q
from django.utils import timezone
from practices.models import Practice
from websites.models import ClinicWebsite, CustomDomain
from leads.models import ClickEvent, Lead
from bookings.models import BookingRequest
from analytics.models import WebsiteVisit
from analytics.services.traffic_parser import TrafficParser


class AnalyticsService:
    """
    Core analytics aggregation and reporting engine.
    Computes unified practice analytics:
    - Website visits & pageviews
    - Traffic sources & UTM campaign attribution
    - Phone calls & WhatsApp click events
    - Patient enquiries & CRM conversion
    - Appointment booking requests & queue metrics
    - End-to-end patient acquisition funnel
    - Timeseries trend charts
    """

    @classmethod
    def resolve_date_range(cls, preset: str = '30d', date_from: str = None, date_to: str = None) -> tuple[datetime.datetime, datetime.datetime, datetime.datetime, datetime.datetime, str]:
        """
        Calculates (current_start, current_end, prev_start, prev_end, preset_label).
        All returned datetimes are timezone-aware.
        """
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if date_from and date_to:
            try:
                dt_from = datetime.datetime.strptime(date_from.strip(), "%Y-%m-%d")
                dt_to = datetime.datetime.strptime(date_to.strip(), "%Y-%m-%d")
                current_start = timezone.make_aware(dt_from.replace(hour=0, minute=0, second=0, microsecond=0))
                current_end = timezone.make_aware(dt_to.replace(hour=23, minute=59, second=59, microsecond=999999))
                delta = current_end - current_start
                prev_end = current_start - timedelta(microseconds=1)
                prev_start = prev_end - delta
                return current_start, current_end, prev_start, prev_end, 'custom'
            except (ValueError, TypeError):
                pass

        p = (preset or '30d').lower().strip()
        if p == 'today':
            current_start = today_start
            current_end = now
            prev_start = current_start - timedelta(days=1)
            prev_end = current_start - timedelta(microseconds=1)
            preset_name = 'today'
        elif p == 'yesterday':
            current_start = today_start - timedelta(days=1)
            current_end = today_start - timedelta(microseconds=1)
            prev_start = current_start - timedelta(days=1)
            prev_end = current_start - timedelta(microseconds=1)
            preset_name = 'yesterday'
        elif p == '7d':
            current_start = today_start - timedelta(days=6)
            current_end = now
            prev_start = current_start - timedelta(days=7)
            prev_end = current_start - timedelta(microseconds=1)
            preset_name = '7d'
        elif p == 'this_month':
            current_start = today_start.replace(day=1)
            current_end = now
            # Previous month same days
            last_day_prev_month = current_start - timedelta(days=1)
            prev_start = last_day_prev_month.replace(day=1)
            prev_end = current_start - timedelta(microseconds=1)
            preset_name = 'this_month'
        elif p == 'this_year':
            current_start = today_start.replace(month=1, day=1)
            current_end = now
            prev_start = current_start.replace(year=current_start.year - 1)
            prev_end = current_start - timedelta(microseconds=1)
            preset_name = 'this_year'
        else:  # Default: 30d
            current_start = today_start - timedelta(days=29)
            current_end = now
            prev_start = current_start - timedelta(days=30)
            prev_end = current_start - timedelta(microseconds=1)
            preset_name = '30d'

        return current_start, current_end, prev_start, prev_end, preset_name

    @classmethod
    def record_visit(cls, practice: Practice, raw_data: dict, request=None, website=None) -> WebsiteVisit:
        """
        Parses traffic channels and records a WebsiteVisit instance.
        """
        # Discover practice domain & website subdomains
        own_domains = {practice.slug, 'clinicrise.com', 'localhost'}
        if website:
            if website.subdomain:
                own_domains.add(f"{website.subdomain}.clinicrise.com")
            for cd in website.custom_domains.all():
                own_domains.add(cd.domain.lower())
        else:
            # Query all domains of this practice
            websites = ClinicWebsite.objects.filter(practice=practice)
            for w in websites:
                if w.subdomain:
                    own_domains.add(f"{w.subdomain}.clinicrise.com")
                for cd in w.custom_domains.all():
                    own_domains.add(cd.domain.lower())

        parsed = TrafficParser.parse_visit_data(raw_data, request=request, own_domains=own_domains)

        today = timezone.now().date()
        visitor_id = parsed['visitor_id']
        is_unique_daily = True
        if visitor_id:
            exists = WebsiteVisit.objects.filter(
                practice=practice,
                visitor_id=visitor_id,
                created_at__date=today
            ).exists()
            is_unique_daily = not exists

        visit = WebsiteVisit.objects.create(
            practice=practice,
            website=website,
            visitor_id=visitor_id,
            session_id=parsed['session_id'],
            page_url=parsed['page_url'],
            page_path=parsed['page_path'],
            page_title=parsed['page_title'],
            referrer=parsed['referrer'],
            referrer_domain=parsed['referrer_domain'],
            traffic_channel=parsed['traffic_channel'],
            traffic_source=parsed['traffic_source'],
            utm_source=parsed['utm_source'],
            utm_medium=parsed['utm_medium'],
            utm_campaign=parsed['utm_campaign'],
            utm_term=parsed['utm_term'],
            utm_content=parsed['utm_content'],
            device_type=parsed['device_type'],
            browser=parsed['browser'],
            os=parsed['os'],
            ip_address=parsed['ip_address'],
            user_agent=parsed['user_agent'],
            is_unique_daily=is_unique_daily
        )
        return visit

    @classmethod
    def get_analytics_overview(
        cls,
        practice: Practice,
        website: ClinicWebsite = None,
        preset: str = '30d',
        date_from: str = None,
        date_to: str = None
    ) -> dict:
        """
        Aggregates complete basic analytics for the practice:
        - Website visits & unique visitors
        - Traffic sources & channel breakdown
        - Calls & WhatsApp clicks
        - Enquiries (leads) & pipeline
        - Bookings & confirmation rates
        - Conversion funnel
        - Daily timeseries data for graphs
        """
        start, end, prev_start, prev_end, preset_name = cls.resolve_date_range(
            preset=preset, date_from=date_from, date_to=date_to
        )

        # Base querysets filtered by practice & date range
        visits_qs = WebsiteVisit.objects.filter(practice=practice, created_at__range=(start, end))
        prev_visits_qs = WebsiteVisit.objects.filter(practice=practice, created_at__range=(prev_start, prev_end))

        clicks_qs = ClickEvent.objects.filter(practice=practice, created_at__range=(start, end))
        prev_clicks_qs = ClickEvent.objects.filter(practice=practice, created_at__range=(prev_start, prev_end))

        leads_qs = Lead.objects.filter(practice=practice, created_at__range=(start, end))
        prev_leads_qs = Lead.objects.filter(practice=practice, created_at__range=(prev_start, prev_end))

        bookings_qs = BookingRequest.objects.filter(practice=practice, created_at__range=(start, end))
        prev_bookings_qs = BookingRequest.objects.filter(practice=practice, created_at__range=(prev_start, prev_end))

        if website:
            visits_qs = visits_qs.filter(website=website)
            prev_visits_qs = prev_visits_qs.filter(website=website)
            clicks_qs = clicks_qs.filter(website=website)
            prev_clicks_qs = prev_clicks_qs.filter(website=website)
            leads_qs = leads_qs.filter(website=website)
            prev_leads_qs = prev_leads_qs.filter(website=website)

        # -------------------------------------------------------------
        # 1. WEBSITE VISITS
        # -------------------------------------------------------------
        total_visits = visits_qs.count()
        prev_total_visits = prev_visits_qs.count()

        # Unique visitors count
        unique_visitors = visits_qs.exclude(visitor_id="").values('visitor_id').distinct().count()
        if unique_visitors == 0 and total_visits > 0:
            unique_visitors = total_visits

        prev_unique_visitors = prev_visits_qs.exclude(visitor_id="").values('visitor_id').distinct().count()

        pageviews_per_visitor = round(total_visits / unique_visitors, 2) if unique_visitors > 0 else 1.0

        # -------------------------------------------------------------
        # 2. CALLS & WHATSAPP CLICKS
        # -------------------------------------------------------------
        total_calls = clicks_qs.filter(event_type=ClickEvent.TYPE_CALL_CLICK).count()
        prev_total_calls = prev_clicks_qs.filter(event_type=ClickEvent.TYPE_CALL_CLICK).count()

        total_whatsapp_clicks = clicks_qs.filter(event_type=ClickEvent.TYPE_WHATSAPP_CLICK).count()
        prev_total_whatsapp = prev_clicks_qs.filter(event_type=ClickEvent.TYPE_WHATSAPP_CLICK).count()

        total_booking_cta_clicks = clicks_qs.filter(event_type=ClickEvent.TYPE_BOOKING_CTA).count()
        total_directions_clicks = clicks_qs.filter(event_type=ClickEvent.TYPE_DIRECTIONS).count()

        total_interactions = total_calls + total_whatsapp_clicks + total_booking_cta_clicks

        # -------------------------------------------------------------
        # 3. PATIENT ENQUIRIES (LEADS)
        # -------------------------------------------------------------
        total_enquiries = leads_qs.count()
        prev_total_enquiries = prev_leads_qs.count()

        unread_enquiries = leads_qs.filter(is_read=False).count()
        converted_enquiries = leads_qs.filter(status=Lead.STATUS_CONVERTED).count()
        enquiry_conversion_rate = round((converted_enquiries / total_enquiries * 100), 2) if total_enquiries > 0 else 0.0

        enquiries_by_status = dict(leads_qs.values_list('status').annotate(count=Count('id')))
        enquiries_by_source = dict(leads_qs.values_list('source').annotate(count=Count('id')))

        # -------------------------------------------------------------
        # 4. BOOKINGS & APPOINTMENTS
        # -------------------------------------------------------------
        total_bookings = bookings_qs.count()
        prev_total_bookings = prev_bookings_qs.count()

        confirmed_bookings = bookings_qs.filter(status=BookingRequest.STATUS_CONFIRMED).count()
        completed_bookings = bookings_qs.filter(status=BookingRequest.STATUS_COMPLETED).count()
        cancelled_bookings = bookings_qs.filter(status=BookingRequest.STATUS_CANCELLED).count()
        pending_bookings = bookings_qs.filter(status=BookingRequest.STATUS_REQUESTED).count()

        booking_confirmation_rate = round((confirmed_bookings / total_bookings * 100), 2) if total_bookings > 0 else 0.0

        bookings_by_consultation_mode = dict(bookings_qs.values_list('consultation_mode').annotate(count=Count('id')))
        bookings_by_scheduling_mode = dict(bookings_qs.values_list('booking_mode').annotate(count=Count('id')))

        # -------------------------------------------------------------
        # 5. TRAFFIC SOURCES & CHANNELS BREAKDOWN
        # -------------------------------------------------------------
        channel_counts = dict(visits_qs.values_list('traffic_channel').annotate(count=Count('id')))
        channels_summary = {}
        for code, label in WebsiteVisit.CHANNEL_CHOICES:
            cnt = channel_counts.get(code, 0)
            pct = round((cnt / total_visits * 100), 2) if total_visits > 0 else 0.0
            channels_summary[code] = {
                "name": label,
                "count": cnt,
                "percentage": pct
            }

        # Top individual sources (Google, Instagram, WhatsApp, Direct, etc.)
        top_sources_raw = visits_qs.values('traffic_source').annotate(count=Count('id')).order_by('-count')[:8]
        top_sources = [
            {
                "source": item['traffic_source'] or 'Direct / Other',
                "count": item['count'],
                "percentage": round((item['count'] / total_visits * 100), 2) if total_visits > 0 else 0.0
            }
            for item in top_sources_raw if item['traffic_source']
        ]

        # Top UTM campaigns
        top_campaigns_raw = visits_qs.exclude(utm_campaign="").values('utm_campaign', 'utm_source').annotate(count=Count('id')).order_by('-count')[:5]
        top_campaigns = [
            {
                "campaign": item['utm_campaign'],
                "source": item['utm_source'] or 'unknown',
                "count": item['count']
            }
            for item in top_campaigns_raw
        ]

        # Top Referrer Domains
        top_referrers_raw = visits_qs.exclude(referrer_domain="").values('referrer_domain').annotate(count=Count('id')).order_by('-count')[:6]
        top_referrers = [
            {"domain": item['referrer_domain'], "count": item['count']}
            for item in top_referrers_raw
        ]

        # -------------------------------------------------------------
        # 6. DEVICE BREAKDOWN
        # -------------------------------------------------------------
        device_counts = dict(visits_qs.values_list('device_type').annotate(count=Count('id')))
        device_summary = {
            "mobile": {
                "count": device_counts.get(WebsiteVisit.DEVICE_MOBILE, 0),
                "percentage": round((device_counts.get(WebsiteVisit.DEVICE_MOBILE, 0) / total_visits * 100), 2) if total_visits > 0 else 0.0
            },
            "desktop": {
                "count": device_counts.get(WebsiteVisit.DEVICE_DESKTOP, 0),
                "percentage": round((device_counts.get(WebsiteVisit.DEVICE_DESKTOP, 0) / total_visits * 100), 2) if total_visits > 0 else 0.0
            },
            "tablet": {
                "count": device_counts.get(WebsiteVisit.DEVICE_TABLET, 0),
                "percentage": round((device_counts.get(WebsiteVisit.DEVICE_TABLET, 0) / total_visits * 100), 2) if total_visits > 0 else 0.0
            }
        }

        # -------------------------------------------------------------
        # 7. TOP VISITED PAGES
        # -------------------------------------------------------------
        top_pages_raw = visits_qs.values('page_path', 'page_title').annotate(
            visits=Count('id'),
            unique=Count('visitor_id', distinct=True)
        ).order_by('-visits')[:10]
        top_pages = [
            {
                "path": item['page_path'] or '/',
                "title": item['page_title'] or 'Page',
                "visits": item['visits'],
                "unique_visitors": item['unique'] or item['visits']
            }
            for item in top_pages_raw
        ]

        # -------------------------------------------------------------
        # 8. CONVERSION FUNNEL
        # -------------------------------------------------------------
        # Funnel Stages:
        # Stage 1: Website Visits (Traffic)
        # Stage 2: Interactions (Call + WhatsApp + CTA Clicks)
        # Stage 3: Enquiries & Bookings (High-intent Leads submitted)
        # Stage 4: Confirmed Patients (Confirmed bookings + Converted leads)
        funnel_interactions = total_interactions
        funnel_enquiries_bookings = total_enquiries + total_bookings
        funnel_confirmed = confirmed_bookings + converted_enquiries

        visit_to_interaction_rate = round((funnel_interactions / total_visits * 100), 2) if total_visits > 0 else 0.0
        visit_to_lead_rate = round((funnel_enquiries_bookings / total_visits * 100), 2) if total_visits > 0 else 0.0
        lead_to_confirmed_rate = round((funnel_confirmed / funnel_enquiries_bookings * 100), 2) if funnel_enquiries_bookings > 0 else 0.0
        overall_conversion_rate = round((funnel_confirmed / total_visits * 100), 2) if total_visits > 0 else 0.0

        funnel = {
            "stages": [
                {
                    "stage": 1,
                    "name": "Website Visits",
                    "count": total_visits,
                    "drop_off_percentage": 0.0
                },
                {
                    "stage": 2,
                    "name": "High-Intent Actions (Calls & WhatsApp)",
                    "count": funnel_interactions,
                    "conversion_from_visits_percentage": visit_to_interaction_rate
                },
                {
                    "stage": 3,
                    "name": "Enquiries & Bookings Submitted",
                    "count": funnel_enquiries_bookings,
                    "conversion_from_visits_percentage": visit_to_lead_rate
                },
                {
                    "stage": 4,
                    "name": "Confirmed Appointments & Patients",
                    "count": funnel_confirmed,
                    "conversion_from_leads_percentage": lead_to_confirmed_rate,
                    "overall_conversion_percentage": overall_conversion_rate
                }
            ],
            "conversion_rates": {
                "visit_to_interaction": visit_to_interaction_rate,
                "visit_to_lead": visit_to_lead_rate,
                "lead_to_confirmed": lead_to_confirmed_rate,
                "overall_conversion": overall_conversion_rate
            }
        }

        # -------------------------------------------------------------
        # 9. TIMESERIES TRENDS (DAILY BREAKDOWN)
        # -------------------------------------------------------------
        timeseries = cls._build_daily_timeseries(
            start_date=start.date(),
            end_date=end.date(),
            visits_qs=visits_qs,
            clicks_qs=clicks_qs,
            leads_qs=leads_qs,
            bookings_qs=bookings_qs
        )

        # -------------------------------------------------------------
        # 10. GROWTH / DELTA PERCENTAGES
        # -------------------------------------------------------------
        growth = {
            "visits": cls._calc_growth(total_visits, prev_total_visits),
            "calls": cls._calc_growth(total_calls, prev_total_calls),
            "whatsapp_clicks": cls._calc_growth(total_whatsapp_clicks, prev_total_whatsapp),
            "enquiries": cls._calc_growth(total_enquiries, prev_total_enquiries),
            "bookings": cls._calc_growth(total_bookings, prev_total_bookings),
        }

        return {
            "period": {
                "preset": preset_name,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "days": (end.date() - start.date()).days + 1
            },
            "summary": {
                "website_visits": total_visits,
                "unique_visitors": unique_visitors,
                "pageviews_per_visitor": pageviews_per_visitor,
                "calls": total_calls,
                "whatsapp_clicks": total_whatsapp_clicks,
                "total_clicks": total_interactions,
                "enquiries": total_enquiries,
                "unread_enquiries": unread_enquiries,
                "bookings": total_bookings,
                "confirmed_bookings": confirmed_bookings,
                "completed_bookings": completed_bookings,
            },
            "growth_vs_previous_period": growth,
            "traffic_sources": {
                "channels": channels_summary,
                "top_sources": top_sources,
                "top_campaigns": top_campaigns,
                "top_referrers": top_referrers
            },
            "calls_and_whatsapp": {
                "total_calls": total_calls,
                "total_whatsapp_clicks": total_whatsapp_clicks,
                "total_booking_cta_clicks": total_booking_cta_clicks,
                "total_directions_clicks": total_directions_clicks,
                "ratio_whatsapp_to_calls": round(total_whatsapp_clicks / total_calls, 2) if total_calls > 0 else (total_whatsapp_clicks if total_whatsapp_clicks > 0 else 1.0)
            },
            "enquiries": {
                "total": total_enquiries,
                "unread": unread_enquiries,
                "conversion_rate_percentage": enquiry_conversion_rate,
                "by_status": enquiries_by_status,
                "by_source": enquiries_by_source
            },
            "bookings": {
                "total": total_bookings,
                "confirmed": confirmed_bookings,
                "completed": completed_bookings,
                "cancelled": cancelled_bookings,
                "pending": pending_bookings,
                "confirmation_rate_percentage": booking_confirmation_rate,
                "by_consultation_mode": bookings_by_consultation_mode,
                "by_scheduling_mode": bookings_by_scheduling_mode
            },
            "conversion_funnel": funnel,
            "device_breakdown": device_summary,
            "top_pages": top_pages,
            "timeseries": timeseries
        }

    @staticmethod
    def _calc_growth(current: int, previous: int) -> float:
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return round(((current - previous) / previous) * 100, 2)

    @classmethod
    def _build_daily_timeseries(
        cls,
        start_date: datetime.date,
        end_date: datetime.date,
        visits_qs,
        clicks_qs,
        leads_qs,
        bookings_qs
    ) -> list[dict]:
        """Generates continuous daily data points for trend line charts."""
        # Aggregate by created_at__date
        visit_map = dict(
            visits_qs.values('created_at__date').annotate(count=Count('id')).values_list('created_at__date', 'count')
        )
        call_map = dict(
            clicks_qs.filter(event_type=ClickEvent.TYPE_CALL_CLICK)
            .values('created_at__date').annotate(count=Count('id')).values_list('created_at__date', 'count')
        )
        whatsapp_map = dict(
            clicks_qs.filter(event_type=ClickEvent.TYPE_WHATSAPP_CLICK)
            .values('created_at__date').annotate(count=Count('id')).values_list('created_at__date', 'count')
        )
        lead_map = dict(
            leads_qs.values('created_at__date').annotate(count=Count('id')).values_list('created_at__date', 'count')
        )
        booking_map = dict(
            bookings_qs.values('created_at__date').annotate(count=Count('id')).values_list('created_at__date', 'count')
        )
        confirmed_booking_map = dict(
            bookings_qs.filter(status=BookingRequest.STATUS_CONFIRMED)
            .values('created_at__date').annotate(count=Count('id')).values_list('created_at__date', 'count')
        )

        results = []
        cur = start_date
        # Limit timeseries points to max 90 days to maintain fast payload size
        step_days = 1
        delta_days = (end_date - start_date).days
        if delta_days > 90:
            step_days = 7  # Group weekly if range exceeds 3 months

        while cur <= end_date:
            date_str = cur.strftime("%Y-%m-%d")
            results.append({
                "date": date_str,
                "visits": visit_map.get(cur, 0),
                "calls": call_map.get(cur, 0),
                "whatsapp_clicks": whatsapp_map.get(cur, 0),
                "enquiries": lead_map.get(cur, 0),
                "bookings": booking_map.get(cur, 0),
                "confirmed_bookings": confirmed_booking_map.get(cur, 0),
            })
            cur += timedelta(days=step_days)

        return results

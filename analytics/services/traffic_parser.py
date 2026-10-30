import re
from urllib.parse import parse_qs, urlparse
from analytics.models import WebsiteVisit


class TrafficParser:
    """
    Intelligent attribution engine that inspects HTTP Referrers,
    UTM query parameters, and User-Agents to classify traffic channels,
    sources, and devices for clinical practice analytics.
    """

    SEARCH_ENGINES = {
        'google': 'Google',
        'bing': 'Bing',
        'yahoo': 'Yahoo',
        'duckduckgo': 'DuckDuckGo',
        'ecosia': 'Ecosia',
        'baidu': 'Baidu',
        'yandex': 'Yandex',
        'ask.com': 'Ask',
    }

    SOCIAL_NETWORKS = {
        'instagram': 'Instagram',
        'facebook': 'Facebook',
        'fb.com': 'Facebook',
        'twitter': 'Twitter / X',
        't.co': 'Twitter / X',
        'x.com': 'Twitter / X',
        'linkedin': 'LinkedIn',
        'youtube': 'YouTube',
        'youtu.be': 'YouTube',
        'pinterest': 'Pinterest',
        'reddit': 'Reddit',
        'tiktok': 'TikTok',
        'threads.net': 'Threads',
    }

    PAID_MEDIUMS = {'cpc', 'ppc', 'paid', 'paidsocial', 'cpm', 'display', 'search_ad', 'banner'}

    @classmethod
    def parse_visit_data(cls, raw_data: dict, request=None, own_domains=None) -> dict:
        """
        Extracts and normalizes traffic channels, sources, devices,
        and clean paths from input and request headers.
        """
        own_domains = set(own_domains or [])
        page_url = raw_data.get('page_url') or (request.build_absolute_uri() if request else '')
        referrer = raw_data.get('referrer') or (request.META.get('HTTP_REFERER', '') if request else '')
        user_agent = raw_data.get('user_agent') or (request.META.get('HTTP_USER_AGENT', '') if request else '')

        # 1. Parse URL query parameters if not provided in top-level payload
        parsed_page = urlparse(page_url) if page_url else None
        query_params = parse_qs(parsed_page.query) if parsed_page else {}

        utm_source = (raw_data.get('utm_source') or query_params.get('utm_source', [''])[0]).strip()
        utm_medium = (raw_data.get('utm_medium') or query_params.get('utm_medium', [''])[0]).strip().lower()
        utm_campaign = (raw_data.get('utm_campaign') or query_params.get('utm_campaign', [''])[0]).strip()
        utm_term = (raw_data.get('utm_term') or query_params.get('utm_term', [''])[0]).strip()
        utm_content = (raw_data.get('utm_content') or query_params.get('utm_content', [''])[0]).strip()

        # Check for Google Click ID or Facebook Click ID
        gclid = query_params.get('gclid', [''])[0]
        fbclid = query_params.get('fbclid', [''])[0]

        # 2. Extract Referrer Domain
        referrer_domain = ""
        if referrer:
            try:
                parsed_ref = urlparse(referrer)
                referrer_domain = (parsed_ref.netloc or parsed_ref.path.split('/')[0]).lower()
                # Strip port if present
                if ':' in referrer_domain:
                    referrer_domain = referrer_domain.split(':')[0]
            except Exception:
                referrer_domain = ""

        # 3. Classify Traffic Channel & Source Name
        traffic_channel, traffic_source = cls.classify_channel(
            referrer=referrer,
            referrer_domain=referrer_domain,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            gclid=gclid,
            fbclid=fbclid,
            own_domains=own_domains
        )

        # 4. Detect Device Type, Browser & OS
        device_type = raw_data.get('device_type')
        if not device_type or device_type == WebsiteVisit.DEVICE_UNKNOWN:
            device_type = cls.detect_device(user_agent)

        browser, os_name = cls.detect_browser_os(user_agent)

        # 5. Normalized Page Path
        page_path = raw_data.get('page_path')
        if not page_path and parsed_page:
            page_path = parsed_page.path or '/'
        elif not page_path:
            page_path = '/'

        # Clean IP Address
        ip_address = None
        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0].strip()
            else:
                ip_address = request.META.get('REMOTE_ADDR')

        return {
            'page_url': page_url,
            'page_path': page_path,
            'page_title': raw_data.get('page_title', '').strip(),
            'referrer': referrer,
            'referrer_domain': referrer_domain,
            'traffic_channel': traffic_channel,
            'traffic_source': traffic_source,
            'utm_source': utm_source,
            'utm_medium': utm_medium,
            'utm_campaign': utm_campaign,
            'utm_term': utm_term,
            'utm_content': utm_content,
            'device_type': device_type,
            'browser': browser,
            'os': os_name,
            'ip_address': ip_address or raw_data.get('ip_address'),
            'user_agent': user_agent,
            'visitor_id': (raw_data.get('visitor_id') or '').strip(),
            'session_id': (raw_data.get('session_id') or '').strip(),
        }

    @classmethod
    def classify_channel(
        cls,
        referrer: str,
        referrer_domain: str,
        utm_source: str,
        utm_medium: str,
        utm_campaign: str,
        gclid: str,
        fbclid: str,
        own_domains: set
    ) -> tuple[str, str]:
        """
        Returns (channel_code, display_source_name).
        """
        ref_lower = referrer.lower()
        ref_domain = referrer_domain.lower()
        src_lower = utm_source.lower()

        # Check for Paid Ads (gclid, explicit cpc/ppc medium, or ad network sources)
        if utm_medium in cls.PAID_MEDIUMS or gclid or (fbclid and utm_medium in ['cpc', 'ad', 'paid']):
            channel = WebsiteVisit.CHANNEL_PAID_AD
            source = utm_source or ('Google Ads' if gclid else 'Paid Ad Campaign')
            return channel, source

        # Check for WhatsApp
        if 'whatsapp' in ref_lower or 'wa.me' in ref_lower or src_lower in ['whatsapp', 'wa']:
            return WebsiteVisit.CHANNEL_WHATSAPP, 'WhatsApp'

        # Check for Social Media
        for key, name in cls.SOCIAL_NETWORKS.items():
            if key in ref_domain or key in src_lower:
                return WebsiteVisit.CHANNEL_SOCIAL, name

        if utm_medium in ['social', 'sm', 'social-media']:
            return WebsiteVisit.CHANNEL_SOCIAL, utm_source or 'Social Media'

        # Check for Organic Search Engines
        for key, name in cls.SEARCH_ENGINES.items():
            if key in ref_domain:
                return WebsiteVisit.CHANNEL_ORGANIC_SEARCH, name

        if src_lower in ['google', 'bing', 'yahoo', 'duckduckgo'] and not utm_medium:
            return WebsiteVisit.CHANNEL_ORGANIC_SEARCH, src_lower.capitalize()

        # Check for Email
        if utm_medium == 'email' or 'mail' in ref_domain:
            return WebsiteVisit.CHANNEL_EMAIL, utm_source or 'Email'

        # Check for Custom Marketing Campaign
        if utm_campaign or (utm_source and utm_source.lower() not in ['direct', 'none']):
            return WebsiteVisit.CHANNEL_CAMPAIGN, utm_source or 'Marketing Campaign'

        # Check for Internal / Direct
        if not referrer or ref_domain in own_domains or 'localhost' in ref_domain or '127.0.0.1' in ref_domain:
            return WebsiteVisit.CHANNEL_DIRECT, 'Direct'

        # External Referral Link
        return WebsiteVisit.CHANNEL_REFERRAL, ref_domain or 'Referral'

    @classmethod
    def detect_device(cls, user_agent: str) -> str:
        """Determines mobile, tablet, or desktop from user agent."""
        if not user_agent:
            return WebsiteVisit.DEVICE_DESKTOP

        ua = user_agent.lower()
        if 'ipad' in ua or 'tablet' in ua or ('android' in ua and 'mobile' not in ua):
            return WebsiteVisit.DEVICE_TABLET
        if 'mobile' in ua or 'iphone' in ua or 'android' in ua or 'blackberry' in ua or 'windows phone' in ua:
            return WebsiteVisit.DEVICE_MOBILE
        return WebsiteVisit.DEVICE_DESKTOP

    @classmethod
    def detect_browser_os(cls, user_agent: str) -> tuple[str, str]:
        """Detects browser and OS friendly name."""
        if not user_agent:
            return '', ''

        ua = user_agent.lower()

        # Browser
        browser = 'Other'
        if 'edg/' in ua:
            browser = 'Edge'
        elif 'chrome' in ua and 'safari' in ua:
            browser = 'Chrome'
        elif 'safari' in ua and 'chrome' not in ua:
            browser = 'Safari'
        elif 'firefox' in ua:
            browser = 'Firefox'
        elif 'opera' in ua or 'opr/' in ua:
            browser = 'Opera'

        # OS
        os_name = 'Other'
        if 'windows' in ua:
            os_name = 'Windows'
        elif 'macintosh' in ua or 'mac os' in ua:
            os_name = 'macOS'
        elif 'iphone' in ua or 'ipad' in ua:
            os_name = 'iOS'
        elif 'android' in ua:
            os_name = 'Android'
        elif 'linux' in ua:
            os_name = 'Linux'

        return browser, os_name

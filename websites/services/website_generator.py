import uuid
from django.utils.text import slugify
from django.utils import timezone
from practices.models import (
    DoctorProfile,
    DoctorSchedule,
    Practice,
    PracticeImage,
    PracticeMembership,
    PracticeService,
)
from websites.models import ClinicWebsite, WebsitePage


class WebsiteGenerationService:
    """
    Automated Website Generation Engine for ClinicRise.
    Synthesizes practice tenant details, doctor credentials, services, timings,
    and photos into a high-converting, modern clinic website.
    """

    COLOR_PALETTES = {
        ClinicWebsite.TEMPLATE_MODERN_MINIMAL: {'primary': '#0D9488', 'secondary': '#0F172A', 'font': 'Inter'},
        ClinicWebsite.TEMPLATE_CLINICAL_CLEAN: {'primary': '#0284C7', 'secondary': '#1E293B', 'font': 'Plus Jakarta Sans'},
        ClinicWebsite.TEMPLATE_PEDIATRIC_WARM: {'primary': '#EA580C', 'secondary': '#1E1B4B', 'font': 'Outfit'},
        ClinicWebsite.TEMPLATE_DENTAL_BRIGHT: {'primary': '#06B6D4', 'secondary': '#0F172A', 'font': 'Inter'},
        ClinicWebsite.TEMPLATE_LUXURY_WELLNESS: {'primary': '#8B5CF6', 'secondary': '#1E1B4B', 'font': 'Playfair Display'},
        ClinicWebsite.TEMPLATE_DARK_PREMIUM: {'primary': '#38BDF8', 'secondary': '#090D16', 'font': 'Plus Jakarta Sans'},
    }

    @classmethod
    def generate_for_practice(cls, practice, template_style=None, subdomain=None, auto_publish=True):
        """
        Generate complete website with Home, About, Services, and Contact pages for a practice.
        """
        # Determine subdomain
        if not subdomain:
            base_subdomain = slugify(practice.name).replace('_', '-')
            if not base_subdomain:
                base_subdomain = f"clinic-{str(practice.id)[:8]}"
            subdomain = base_subdomain

        # Ensure subdomain uniqueness
        existing_site = ClinicWebsite.objects.filter(subdomain=subdomain).exclude(practice=practice).first()
        if existing_site:
            subdomain = f"{subdomain}-{str(uuid.uuid4())[:6]}"

        # Auto-select template if not specified
        if not template_style:
            c_type = getattr(practice, 'clinic_type', '')
            if c_type == 'dental_clinic' or 'dental' in practice.name.lower():
                template_style = ClinicWebsite.TEMPLATE_DENTAL_BRIGHT
            elif 'pediatric' in practice.name.lower() or 'child' in practice.name.lower():
                template_style = ClinicWebsite.TEMPLATE_PEDIATRIC_WARM
            elif c_type in ['polyclinic', 'hospital_opd']:
                template_style = ClinicWebsite.TEMPLATE_CLINICAL_CLEAN
            elif c_type == 'diagnostic_center':
                template_style = ClinicWebsite.TEMPLATE_MODERN_MINIMAL
            else:
                template_style = ClinicWebsite.TEMPLATE_MODERN_MINIMAL

        palette = cls.COLOR_PALETTES.get(template_style, cls.COLOR_PALETTES[ClinicWebsite.TEMPLATE_MODERN_MINIMAL])

        # Fetch practice data
        doctors_qs = DoctorProfile.objects.filter(
            user__practice_memberships__practice=practice,
            user__practice_memberships__is_active=True
        ).distinct()

        services_qs = PracticeService.objects.filter(practice=practice, is_active=True).order_by('name')
        schedules_qs = DoctorSchedule.objects.filter(practice=practice, is_active=True).order_by('day_of_week', 'start_time')
        images_qs = PracticeImage.objects.filter(practice=practice).order_by('order', '-created_at')

        # 1. Create or update ClinicWebsite
        website, created = ClinicWebsite.objects.update_or_create(
            practice=practice,
            defaults={
                'title': practice.name,
                'tagline': practice.tagline or f"Premier Clinical Care & Consultation in {practice.city or 'your region'}",
                'subdomain': subdomain,
                'template_style': template_style,
                'primary_color': palette['primary'],
                'secondary_color': palette['secondary'],
                'font_family': palette['font'],
                'logo_url': getattr(practice, 'logo_display_url', None) or practice.logo_url or '',
                'contact_phone': practice.phone_number or '',
                'contact_email': practice.email or '',
                'footer_text': f"© {timezone.now().year} {practice.name}. All rights reserved.",
                'meta_title': f"{practice.name} | Doctor Consultation & Healthcare in {practice.city or 'India'}",
                'meta_description': practice.about[:160] if practice.about else f"Book appointment at {practice.name}. Expert doctors, modern clinical services, and compassionate care.",
            }
        )

        # 2. Build structured page content blocks
        cls._create_or_update_home_page(website, practice, doctors_qs, services_qs, schedules_qs, images_qs, auto_publish)
        cls._create_or_update_about_page(website, practice, doctors_qs, auto_publish)
        cls._create_or_update_services_page(website, practice, services_qs, auto_publish)
        cls._create_or_update_contact_page(website, practice, schedules_qs, auto_publish)

        if auto_publish:
            website.publish_all()

        return website

    @classmethod
    def _create_or_update_home_page(cls, website, practice, doctors_qs, services_qs, schedules_qs, images_qs, auto_publish):
        """Construct Home page with all rich sections."""
        # Doctors payload
        doctors_data = []
        for doc in doctors_qs:
            doctors_data.append({
                "id": str(doc.id),
                "name": f"{doc.title or 'Dr.'} {doc.user.full_name}",
                "specialization": doc.specialization,
                "qualifications": doc.qualifications,
                "experience_years": f"{doc.experience_years}+ Years Experience" if doc.experience_years else "Experienced Specialist",
                "bio": doc.bio,
                "photo_url": doc.photo_display_url,
                "consultation_fee": f"{practice.currency} {doc.default_consultation_fee}",
            })

        # Services payload
        services_data = []
        for s in services_qs[:6]:  # Top 6 on homepage
            services_data.append({
                "id": str(s.id),
                "name": s.name,
                "category": s.get_category_display(),
                "description": s.description or f"Comprehensive clinical care and professional consultation.",
                "duration": f"{s.duration_minutes} Mins",
                "price": f"{practice.currency} {s.price}",
            })

        # Schedule payload
        timings_data = []
        for sch in schedules_qs:
            timings_data.append({
                "day": sch.get_day_of_week_display(),
                "session": sch.session_name,
                "time": f"{sch.start_time.strftime('%I:%M %p')} - {sch.end_time.strftime('%I:%M %p')}",
            })

        # Gallery payload
        gallery_data = []
        for img in images_qs[:8]:
            gallery_data.append({
                "image_url": img.image_url,
                "caption": img.caption or img.get_image_type_display(),
                "type": img.image_type,
            })

        sections = [
            {
                "id": "hero-section",
                "type": "hero",
                "headline": f"Compassionate, World-Class Healthcare at {practice.name}",
                "subheadline": practice.tagline or f"Providing individualized clinical excellence, preventative care, and specialized medical treatments in {practice.city}.",
                "badge": "Accepting New Patients Today",
                "cta_primary": {"text": "Book Appointment", "link": "#appointment"},
                "cta_secondary": {"text": "Explore Services", "link": "/services"},
                "hero_image_url": getattr(images_qs.first(), 'image_url', None) or "https://images.unsplash.com/photo-1629909613654-28e377c37b09?auto=format&fit=crop&w=1200&q=80",
                "trust_stats": [
                    {"label": "Patient Satisfaction", "value": "98%"},
                    {"label": "Clinical Experience", "value": "15+ Yrs"},
                    {"label": "Verified Specialists", "value": "100%"},
                ]
            },
            {
                "id": "about-section",
                "type": "about",
                "title": f"Why Choose {practice.name}?",
                "subtitle": "Patient-centric care powered by modern diagnostic standards",
                "content": practice.about or f"At {practice.name}, our mission is to deliver comprehensive, compassionate, and personalized healthcare to each patient who walks through our doors. Equipped with advanced facilities in {practice.city}, our expert practitioners treat every condition with precision and empathy.",
                "address": f"{practice.address}, {practice.landmark or ''}, {practice.city}, {practice.state} {practice.postal_code}".strip(", "),
                "features": [
                    "Zero Waiting Times with Pre-booked Appointments",
                    "Digitized Prescriptions & Health Records",
                    "Hygienic, State-of-the-art Clinical Facilities",
                    "Transparent Pricing & Direct Specialist Care"
                ]
            },
            {
                "id": "services-section",
                "type": "services_list",
                "title": "Specialized Treatments & Clinical Services",
                "subtitle": "Discover our comprehensive range of general and specialized medical services",
                "services": services_data,
                "view_all_link": "/services"
            },
            {
                "id": "doctors-section",
                "type": "doctor_roster",
                "title": "Meet Our Medical Practitioners",
                "subtitle": "Dedicated specialists focused on delivering exceptional patient outcomes",
                "doctors": doctors_data
            },
            {
                "id": "timings-section",
                "type": "schedule_timings",
                "title": "Clinic Hours & Consultation Timetable",
                "subtitle": "Plan your visit conveniently during our active clinic shifts",
                "emergency_note": f"For medical emergencies, please call {practice.phone_number or 'our frontdesk'}.",
                "timings": timings_data
            },
            {
                "id": "testimonials-section",
                "type": "testimonials",
                "title": "Real Experiences from Our Patients",
                "subtitle": "Trusted by hundreds of families in our local community",
                "testimonials": [
                    {
                        "patient_name": "Rohan Mehra",
                        "comment": f"The consultation at {practice.name} was incredibly thorough. The doctor listened attentively and explained everything clearly.",
                        "rating": 5,
                        "treatment": "General Consultation"
                    },
                    {
                        "patient_name": "Sunita Rao",
                        "comment": "Extremely clean clinic and very professional staff. Zero waiting time and excellent post-consultation guidance.",
                        "rating": 5,
                        "treatment": "Specialist Visit"
                    }
                ]
            },
            {
                "id": "gallery-section",
                "type": "gallery",
                "title": "Clinic Facilities & Environment",
                "subtitle": "A calm, modern, and sterile healing atmosphere",
                "images": gallery_data
            },
            {
                "id": "contact-section",
                "type": "contact_map",
                "title": "Get in Touch & Book an Appointment",
                "subtitle": f"Located conveniently in {practice.city}. Reach out to schedule your visit.",
                "phone": practice.phone_number,
                "email": practice.email,
                "address": practice.address,
                "city": practice.city,
                "state": practice.state,
                "postal_code": practice.postal_code,
                "landmark": practice.landmark
            }
        ]

        draft_content = {"sections": sections}

        page, _ = WebsitePage.objects.update_or_create(
            website=website,
            slug='home',
            defaults={
                'title': 'Home',
                'is_homepage': True,
                'page_type': WebsitePage.PAGE_TYPE_HOME,
                'is_in_navigation': True,
                'is_in_footer': True,
                'nav_order': 1,
                'meta_title': f"{practice.name} - Official Clinic Website",
                'meta_description': f"Welcome to {practice.name}. Schedule appointment with qualified specialists in {practice.city}.",
                'draft_content': draft_content,
            }
        )

        if auto_publish:
            page.publish()

        return page

    @classmethod
    def _create_or_update_about_page(cls, website, practice, doctors_qs, auto_publish):
        """Construct dedicated About Us page."""
        sections = [
            {
                "id": "about-hero",
                "type": "page_header",
                "title": f"About {practice.name}",
                "subtitle": "Our commitment to high quality, empathetic, and evidence-based patient care."
            },
            {
                "id": "about-story",
                "type": "narrative",
                "title": "Our Clinical Heritage & Philosophy",
                "body": practice.about or f"{practice.name} was established to bring modern medical standards and compassionate clinical consultation to {practice.city}. We believe in holistic wellness, patient education, and ethical medicine."
            },
            {
                "id": "about-doctors",
                "type": "doctor_detailed_list",
                "title": "Our Practitioners & Qualifications",
                "doctors": [
                    {
                        "name": f"{d.title or 'Dr.'} {d.user.full_name}",
                        "specialization": d.specialization,
                        "qualifications": d.qualifications,
                        "registration_number": d.medical_license_number,
                        "registration_council": d.registration_council or "Medical Council",
                        "experience_years": d.experience_years,
                        "bio": d.bio,
                        "photo_url": d.photo_display_url
                    }
                    for d in doctors_qs
                ]
            }
        ]

        page, _ = WebsitePage.objects.update_or_create(
            website=website,
            slug='about',
            defaults={
                'title': 'About Us',
                'is_homepage': False,
                'page_type': WebsitePage.PAGE_TYPE_ABOUT,
                'is_in_navigation': True,
                'is_in_footer': True,
                'nav_order': 2,
                'meta_title': f"About {practice.name} | Doctors & Clinical Mission",
                'meta_description': f"Learn about {practice.name}, our medical practitioners, certifications, and healthcare values.",
                'draft_content': {"sections": sections},
            }
        )

        if auto_publish:
            page.publish()

        return page

    @classmethod
    def _create_or_update_services_page(cls, website, practice, services_qs, auto_publish):
        """Construct dedicated Treatments & Services page."""
        services_list = []
        for s in services_qs:
            services_list.append({
                "id": str(s.id),
                "name": s.name,
                "category": s.get_category_display(),
                "description": s.description or "Professional medical evaluation and evidence-based care.",
                "duration_minutes": s.duration_minutes,
                "price": f"{practice.currency} {s.price}",
                "is_teleconsultation": s.is_teleconsultation
            })

        sections = [
            {
                "id": "services-hero",
                "type": "page_header",
                "title": "Treatments & Clinical Services",
                "subtitle": f"Specialized medical services offered at {practice.name}."
            },
            {
                "id": "services-catalog",
                "type": "services_catalog",
                "currency": practice.currency,
                "services": services_list
            }
        ]

        page, _ = WebsitePage.objects.update_or_create(
            website=website,
            slug='services',
            defaults={
                'title': 'Services',
                'is_homepage': False,
                'page_type': WebsitePage.PAGE_TYPE_SERVICES,
                'is_in_navigation': True,
                'is_in_footer': True,
                'nav_order': 3,
                'meta_title': f"Services & Treatments | {practice.name}",
                'meta_description': f"Browse medical services and consultation fees at {practice.name}.",
                'draft_content': {"sections": sections},
            }
        )

        if auto_publish:
            page.publish()

        return page

    @classmethod
    def _create_or_update_contact_page(cls, website, practice, schedules_qs, auto_publish):
        """Construct dedicated Contact Us page."""
        timings_list = [
            {
                "day": sch.get_day_of_week_display(),
                "session": sch.session_name,
                "time": f"{sch.start_time.strftime('%I:%M %p')} - {sch.end_time.strftime('%I:%M %p')}"
            }
            for sch in schedules_qs
        ]

        sections = [
            {
                "id": "contact-hero",
                "type": "page_header",
                "title": "Contact & Location",
                "subtitle": "Reach out to us, book an appointment, or visit our clinic."
            },
            {
                "id": "contact-details",
                "type": "contact_info",
                "phone": practice.phone_number,
                "email": practice.email,
                "website": practice.website,
                "address": practice.address,
                "city": practice.city,
                "state": practice.state,
                "postal_code": practice.postal_code,
                "country": practice.country,
                "landmark": practice.landmark,
                "timings": timings_list
            }
        ]

        page, _ = WebsitePage.objects.update_or_create(
            website=website,
            slug='contact',
            defaults={
                'title': 'Contact Us',
                'is_homepage': False,
                'page_type': WebsitePage.PAGE_TYPE_CONTACT,
                'is_in_navigation': True,
                'is_in_footer': True,
                'nav_order': 4,
                'meta_title': f"Contact & Location | {practice.name}",
                'meta_description': f"Contact details, address, clinic hours, and directions for {practice.name} in {practice.city}.",
                'draft_content': {"sections": sections},
            }
        )

        if auto_publish:
            page.publish()

        return page

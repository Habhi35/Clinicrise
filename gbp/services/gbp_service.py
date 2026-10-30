from practices.models import (
    DoctorProfile,
    DoctorSchedule,
    Practice,
    PracticeImage,
    PracticeService,
)
from bookings.models import PracticeLocation
from websites.models import ClinicWebsite, CustomDomain
from gbp.models import GBPProfileChecklist


class GBPService:
    """
    Core engine for Google Business Profile (GBP) checklist evaluation,
    progress scoring, and automated local SEO setup synthesis.
    """

    PRIMARY_CATEGORIES = {
        'dental_clinic': 'Dental Clinic',
        'polyclinic': 'Medical Clinic',
        'solo_clinic': 'Doctor',
        'hospital_opd': 'General Hospital',
        'diagnostic_center': 'Diagnostic Center',
        'telehealth': 'Medical Center',
    }

    DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    @classmethod
    def get_or_create_profile(cls, practice: Practice) -> GBPProfileChecklist:
        """Retrieves or provisions the GBPProfileChecklist instance for the practice."""
        profile, _ = GBPProfileChecklist.objects.get_or_create(practice=practice)
        return profile

    @classmethod
    def get_or_create_review_link(cls, practice: Practice) -> str:
        """Retrieves or synthesizes the direct Google review shortcut link for the practice."""
        profile = cls.get_or_create_profile(practice)
        return profile.google_review_link or (
            f"https://search.google.com/local/writereview?placeid={profile.google_maps_place_id}"
            if profile.google_maps_place_id else f"https://maps.google.com/?q={practice.name}+{practice.city}"
        )

    @classmethod
    def evaluate_checklist(cls, practice: Practice) -> dict:
        """
        Evaluates the 10-point Google Business Profile setup checklist.
        Combines dynamic system checks (DB records) and manual user confirmations.
        """
        profile = cls.get_or_create_profile(practice)
        manual_done = set(profile.manual_completed_items or [])

        # Gather relevant clinic context
        website = ClinicWebsite.objects.filter(practice=practice).first()
        services_count = PracticeService.objects.filter(practice=practice, is_active=True).count()
        doctors = list(DoctorProfile.objects.filter(
            user__practice_memberships__practice=practice,
            user__practice_memberships__is_active=True
        ).distinct())
        schedules_count = DoctorSchedule.objects.filter(practice=practice, is_active=True).count()
        images_count = PracticeImage.objects.filter(practice=practice).count()

        items = []

        # -------------------------------------------------------------
        # Item 1: Business Name
        # -------------------------------------------------------------
        name_valid = bool(practice.name and len(practice.name.strip()) >= 3)
        items.append({
            "key": "business_name",
            "category": "Profile Essentials",
            "title": "Clinic Name & Branding",
            "description": "Accurate, official legal clinic name compliant with Google guidelines (no keyword stuffing).",
            "is_completed": name_valid or ('business_name' in manual_done),
            "priority": "high",
            "current_value": practice.name,
            "recommendation": "Use your real-world clinic signage name (e.g. 'Apollo Dental Care').",
        })

        # -------------------------------------------------------------
        # Item 2: Primary & Secondary Categories
        # -------------------------------------------------------------
        primary_cat = profile.primary_category or cls.PRIMARY_CATEGORIES.get(practice.clinic_type, 'Medical Clinic')
        has_categories = bool(primary_cat)
        items.append({
            "key": "categories",
            "category": "Profile Essentials",
            "title": "Primary & Secondary Categories",
            "description": "Google category indicating your exact medical specialty to appear in relevant 'near me' local searches.",
            "is_completed": has_categories or ('categories' in manual_done),
            "priority": "high",
            "current_value": primary_cat,
            "recommendation": f"Set Primary Category to '{primary_cat}' and add specialty secondary categories.",
        })

        # -------------------------------------------------------------
        # Item 3: Physical Address & Location
        # -------------------------------------------------------------
        address_valid = bool(practice.address and practice.city and (practice.postal_code or practice.state))
        items.append({
            "key": "location_address",
            "category": "Profile Essentials",
            "title": "Address & Map Pin Precision",
            "description": "Consistent physical street address, building/suite number, landmark, and postal code matching official records.",
            "is_completed": address_valid or ('location_address' in manual_done),
            "priority": "high",
            "current_value": f"{practice.address}, {practice.city}" if practice.address else "Incomplete",
            "recommendation": "Ensure your street address and postal code exactly match your signage and municipal license.",
        })

        # -------------------------------------------------------------
        # Item 4: Phone & Contact
        # -------------------------------------------------------------
        has_phone = bool(practice.phone_number and len(practice.phone_number.strip()) >= 8)
        items.append({
            "key": "phone_and_contact",
            "category": "Profile Essentials",
            "title": "Local Phone Number & WhatsApp",
            "description": "Direct clinic phone line for incoming patient inquiries and one-click calls.",
            "is_completed": has_phone or ('phone_and_contact' in manual_done),
            "priority": "high",
            "current_value": practice.phone_number or "Missing",
            "recommendation": "Use a direct landline or dedicated clinic mobile number that is answered during OPD hours.",
        })

        # -------------------------------------------------------------
        # Item 5: Operating Hours & OPD Shifts
        # -------------------------------------------------------------
        hours_configured = schedules_count > 0 or ('operating_hours' in manual_done)
        items.append({
            "key": "operating_hours",
            "category": "Patient Experience",
            "title": "Consultation Hours & Split Shifts",
            "description": "Up-to-date weekly operating hours including morning and evening OPD shifts.",
            "is_completed": hours_configured,
            "priority": "high",
            "current_value": f"{schedules_count} doctor shift schedules active" if schedules_count > 0 else "Not configured",
            "recommendation": "Add your morning and evening consultation shifts so patients know when walk-ins and bookings are accepted.",
        })

        # -------------------------------------------------------------
        # Item 6: Website & Appointment Booking Link
        # -------------------------------------------------------------
        has_website_link = bool(website and website.is_published) or ('website_and_appointment_links' in manual_done)
        website_url = website.public_url if website else ""
        items.append({
            "key": "website_and_appointment_links",
            "category": "Patient Experience",
            "title": "Website URL & Appointment Deep-Link",
            "description": "Direct link to your live clinic website and online appointment booking engine.",
            "is_completed": has_website_link,
            "priority": "high",
            "current_value": website_url or "Website not yet published",
            "recommendation": "Link your live ClinicRise website and add the dedicated appointment booking link.",
        })

        # -------------------------------------------------------------
        # Item 7: Clinic Photos & Exterior Signage
        # -------------------------------------------------------------
        has_photos = images_count >= 3 or ('clinic_photos' in manual_done)
        items.append({
            "key": "clinic_photos",
            "category": "Visuals & Branding",
            "title": "High-Quality Clinic Photos (Min. 5)",
            "description": "Clear exterior building facade with signage, reception lounge, consultation desks, and modern medical equipment.",
            "is_completed": has_photos,
            "priority": "medium",
            "current_value": f"{images_count} practice photos uploaded",
            "recommendation": "Upload at least 5 photos: exterior with street view, reception desk, consultation room, and team portrait.",
        })

        # -------------------------------------------------------------
        # Item 8: Treatments & Services Catalog
        # -------------------------------------------------------------
        has_services = services_count >= 1 or ('services_menu' in manual_done)
        items.append({
            "key": "services_menu",
            "category": "Visuals & Branding",
            "title": "Treatments & Services Menu",
            "description": "List of medical procedures and consultation services with transparent fee estimates and descriptions.",
            "is_completed": has_services,
            "priority": "medium",
            "current_value": f"{services_count} clinical services registered",
            "recommendation": "Add your primary treatments and consultations so patients can view services directly on Google Maps.",
        })

        # -------------------------------------------------------------
        # Item 9: Healthcare Attributes & Accessibility
        # -------------------------------------------------------------
        attributes_done = bool(profile.has_wheelchair_accessible_entrance and profile.accepts_upi_payments) or ('attributes_accessibility' in manual_done)
        items.append({
            "key": "attributes_accessibility",
            "category": "Patient Experience",
            "title": "Accessibility & Payment Attributes",
            "description": "Highlight wheelchair accessibility, payment methods accepted (UPI, Credit Cards), and appointment policies.",
            "is_completed": attributes_done,
            "priority": "medium",
            "current_value": "Wheelchair accessible, UPI/Cards accepted",
            "recommendation": "Enable wheelchair access attributes and payment options in Google Business settings.",
        })

        # -------------------------------------------------------------
        # Item 10: Verification & Google Review Strategy
        # -------------------------------------------------------------
        is_verified = (profile.verification_status == GBPProfileChecklist.STATUS_VERIFIED) or bool(profile.google_review_link) or ('verification_and_reviews' in manual_done)
        items.append({
            "key": "verification_and_reviews",
            "category": "Reputation & Growth",
            "title": "Google Verification & Review Link",
            "description": "Complete Google verification and generate your 5-star review shortcut link for patient feedback.",
            "is_completed": is_verified,
            "priority": "high",
            "current_value": profile.get_verification_status_display(),
            "recommendation": "Complete Google verification (video or postcard) and save your Google review shortcut link.",
        })

        # -------------------------------------------------------------
        # Progress Calculation
        # -------------------------------------------------------------
        total_count = len(items)
        completed_count = sum(1 for it in items if it['is_completed'])
        score = round((completed_count / total_count * 100), 1)

        if score == 100:
            status_level = "Fully Optimized & Ready"
            badge_color = "#10B981"
        elif score >= 70:
            status_level = "Well Optimized (Minor Gaps)"
            badge_color = "#3B82F6"
        elif score >= 40:
            status_level = "In Progress"
            badge_color = "#F59E0B"
        else:
            status_level = "Needs Setup"
            badge_color = "#EF4444"

        next_steps = [it for it in items if not it['is_completed']]

        return {
            "practice_id": str(practice.id),
            "practice_name": practice.name,
            "progress": {
                "total_items": total_count,
                "completed_items": completed_count,
                "completion_percentage": score,
                "status_level": status_level,
                "badge_color": badge_color,
                "verification_status": profile.verification_status,
                "verification_status_display": profile.get_verification_status_display(),
            },
            "checklist": items,
            "next_priorities": [
                {"key": ns['key'], "title": ns['title'], "action": ns['recommendation']}
                for ns in next_steps[:3]
            ]
        }

    @classmethod
    def generate_setup_information(cls, practice: Practice) -> dict:
        """
        Synthesizes ready-to-copy-paste, SEO-optimized GBP setup assets:
        - Primary & Secondary categories
        - 750-character SEO business description
        - Standard formatted NAP
        - Structured operating hours
        - Services catalog
        - Google review shortcut link & post-consultation templates
        - Ready-to-publish Google post
        """
        profile = cls.get_or_create_profile(practice)
        website = ClinicWebsite.objects.filter(practice=practice).first()
        services = list(PracticeService.objects.filter(practice=practice, is_active=True))
        doctors = list(DoctorProfile.objects.filter(
            user__practice_memberships__practice=practice,
            user__practice_memberships__is_active=True
        ).distinct())
        schedules = list(DoctorSchedule.objects.filter(practice=practice, is_active=True))
        images = list(PracticeImage.objects.filter(practice=practice))

        # 1. Categories
        primary_cat = profile.primary_category or cls.PRIMARY_CATEGORIES.get(practice.clinic_type, 'Medical Clinic')
        secondary_cats = profile.secondary_categories or cls._suggest_secondary_categories(practice, services)

        # 2. Optimized 750-char Description
        description = profile.custom_description or cls._build_seo_description(practice, doctors, services)

        # 3. Formatted NAP
        address_parts = [p.strip() for p in [practice.address, practice.landmark, practice.city, practice.state] if p and p.strip()]
        if practice.postal_code:
            address_parts.append(f"PIN: {practice.postal_code}")
        if practice.country:
            address_parts.append(practice.country)

        single_line_address = ", ".join(address_parts) if address_parts else "Address to be updated"

        # 4. URLs
        website_url = website.public_url if website else f"https://{practice.slug}.clinicrise.com"
        appointment_url = f"{website_url}#appointment"

        # 5. Operating Hours
        hours_data = cls._format_operating_hours(schedules)

        # 6. Services Catalog
        services_catalog = [
            {
                "name": s.name,
                "category": s.get_category_display() if hasattr(s, 'get_category_display') else s.category,
                "price": f"{practice.currency} {s.price}" if s.price else "Fee on Consultation",
                "description": s.description or f"Professional {s.name} provided by experienced medical team at {practice.name}."
            }
            for s in services
        ]

        # 7. Review Shortcut & Messaging Templates
        review_url = profile.google_review_link or (
            f"https://search.google.com/local/writereview?placeid={profile.google_maps_place_id}"
            if profile.google_maps_place_id else f"https://maps.google.com/?q={practice.name}+{practice.city}"
        )

        doctor_names = ", ".join([d.full_name for d in doctors[:2]]) or "our medical team"
        whatsapp_review_template = (
            f"Dear Patient, thank you for visiting {practice.name}! "
            f"We hope your consultation with {doctor_names} was pleasant. "
            f"Could you take 30 seconds to share your feedback on Google? It helps others find trusted care:\n"
            f"{review_url}\n"
            f"— Team {practice.name}"
        )

        sms_review_template = (
            f"Thank you for choosing {practice.name}. "
            f"Please share your review on Google: {review_url}"
        )

        # 8. Welcome Announcement Google Post
        specialties_list = ", ".join([s.name for s in services[:4]]) or "comprehensive healthcare"
        welcome_post = {
            "title": f"Welcome to {practice.name} - Quality Healthcare in {practice.city}",
            "body": (
                f"We are proud to serve the community in {practice.city} with advanced medical care! "
                f"Led by experienced practitioners, {practice.name} offers specialized treatments including {specialties_list}. "
                f"We follow the highest clinical sterilization standards and offer seamless online appointment booking. "
                f"Visit us at {practice.address or practice.city} or book your appointment today."
            ),
            "call_to_action": "BOOK",
            "cta_url": appointment_url,
        }

        # 9. Photos Upload Checklist
        photos_guide = [
            {"type": "Exterior Signage", "recommendation": "Building exterior showing main entrance and clinic name board during daylight."},
            {"type": "Reception & Waiting Area", "recommendation": "Clean, welcoming patient seating lounge and frontdesk."},
            {"type": "Consultation Room", "recommendation": "Doctor consultation chamber, desk, and clinical examination couch."},
            {"type": "Medical Equipment", "recommendation": "Modern diagnostics, dental chairs, or advanced treatment machinery."},
            {"type": "Team Portrait", "recommendation": "Doctors and nursing/reception staff in professional clinical attire."},
        ]

        return {
            "business_identity": {
                "business_name": practice.name,
                "primary_category": primary_cat,
                "secondary_categories": secondary_cats,
                "clinic_type": practice.clinic_type,
            },
            "seo_description": {
                "text": description,
                "character_count": len(description),
                "max_limit": 750,
            },
            "nap_contact": {
                "business_name": practice.name,
                "phone_number": practice.phone_number,
                "whatsapp_number": website.whatsapp_number if website else practice.phone_number,
                "email": practice.email,
                "single_line_address": single_line_address,
                "street_address": practice.address,
                "landmark": practice.landmark,
                "city": practice.city,
                "state": practice.state,
                "postal_code": practice.postal_code,
                "country": practice.country,
                "google_maps_url": profile.google_maps_url or (website.google_maps_url if website else ""),
                "google_maps_place_id": profile.google_maps_place_id,
            },
            "online_links": {
                "website_url": website_url,
                "appointment_booking_url": appointment_url,
                "google_review_url": review_url,
            },
            "operating_hours": hours_data,
            "services_catalog": services_catalog,
            "attributes": {
                "has_wheelchair_accessible_entrance": profile.has_wheelchair_accessible_entrance,
                "has_wheelchair_accessible_restroom": profile.has_wheelchair_accessible_restroom,
                "requires_appointments": profile.requires_appointments,
                "accepts_upi_payments": profile.accepts_upi_payments,
                "accepts_credit_cards": profile.accepts_credit_cards,
            },
            "review_strategy": {
                "review_url": review_url,
                "whatsapp_template": whatsapp_review_template,
                "sms_template": sms_review_template,
            },
            "welcome_post": welcome_post,
            "photos_guide": photos_guide,
        }

    @classmethod
    def _suggest_secondary_categories(cls, practice: Practice, services: list) -> list:
        """Suggests relevant secondary Google categories based on practice specialties."""
        suggestions = set()
        c_type = practice.clinic_type

        if c_type == 'dental_clinic':
            suggestions.update(['Cosmetic Dentist', 'Orthodontist', 'Pediatric Dentist', 'Dental Implants Periodontist', 'Emergency Dental Service'])
        elif c_type == 'polyclinic':
            suggestions.update(['General Practitioner', 'Pediatrician', 'Consultant Physician', 'Diagnostic Center'])
        elif c_type == 'diagnostic_center':
            suggestions.update(['Medical Diagnostic Imaging Center', 'Blood Testing Service', 'Pathology Laboratory'])

        # Inspect service names
        for s in services:
            s_name = s.name.lower()
            if 'implant' in s_name:
                suggestions.add('Dental Implants Periodontist')
            if 'brace' in s_name or 'aligner' in s_name:
                suggestions.add('Orthodontist')
            if 'skin' in s_name or 'derma' in s_name:
                suggestions.add('Dermatologist')
            if 'child' in s_name or 'pedia' in s_name:
                suggestions.add('Pediatrician')
            if 'physio' in s_name:
                suggestions.add('Physiotherapist')

        return sorted(list(suggestions))[:6]

    @classmethod
    def _build_seo_description(cls, practice: Practice, doctors: list, services: list) -> str:
        """Builds a high-converting, 750-character Google Business Profile description."""
        city = practice.city or "the city"
        landmark_str = f" conveniently located near {practice.landmark}" if practice.landmark else ""

        lead_doctor = doctors[0] if doctors else None
        doctor_str = ""
        if lead_doctor:
            doctor_str = f" Led by {lead_doctor.full_name} ({lead_doctor.qualification or lead_doctor.specialization}),"

        service_names = [s.name for s in services[:4]]
        specialties_str = f" specializing in {', '.join(service_names)}," if service_names else ""

        desc = (
            f"{practice.name} is a premier healthcare facility in {city},{landmark_str}."
            f"{doctor_str} our team provides compassionate, evidence-based clinical care{specialties_str} "
            f"and personalized treatment plans. "
            f"We maintain strict sterilization standards, modern diagnostic technology, and comfortable outpatient facilities. "
            f"Walk-ins and scheduled appointments welcome. Book online or call us today to schedule your consultation."
        )

        # Ensure fits within Google's 750 character limit
        return desc[:745]

    @classmethod
    def _format_operating_hours(cls, schedules: list) -> dict:
        """Formats schedules into structured Google Business Profile hours."""
        if not schedules:
            return {
                "summary": "Monday - Saturday: 09:00 - 20:00 (Sunday: Closed)",
                "periods": [
                    {"day": day, "open": "09:00", "close": "20:00"}
                    for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
                ]
            }

        day_map = {}
        for s in schedules:
            day_name = cls.DAY_NAMES[s.day_of_week]
            time_slot = f"{s.start_time.strftime('%H:%M')} - {s.end_time.strftime('%H:%M')}"
            day_map.setdefault(day_name, []).append(time_slot)

        periods = []
        summary_lines = []
        for day in cls.DAY_NAMES:
            if day in day_map:
                slots = ", ".join(day_map[day])
                summary_lines.append(f"{day}: {slots}")
                for s in schedules:
                    if cls.DAY_NAMES[s.day_of_week] == day:
                        periods.append({
                            "day": day,
                            "open": s.start_time.strftime('%H:%M'),
                            "close": s.end_time.strftime('%H:%M'),
                            "shift": s.session_name
                        })
            else:
                summary_lines.append(f"{day}: Closed")

        return {
            "summary": "; ".join(summary_lines[:7]),
            "periods": periods
        }

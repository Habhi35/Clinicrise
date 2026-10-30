import hashlib
import json
import os
from datetime import timedelta
from django.conf import settings
from django.utils import timezone

from practices.models import DoctorProfile, Practice, PracticeService
from websites.models import ClinicWebsite, WebsitePage
from leads.models import Lead
from bookings.models import BookingRequest, PracticeLocation
from security.models import AuditLog, BackupRecord, ConsentRecord
from security.services.audit_service import AuditService


class BackupService:
    """
    Automated and on-demand practice snapshot service.
    Exports clinical data, booking records, inquiries, websites, and consent logs
    into cryptographically verified JSON archives.
    """

    @classmethod
    def create_backup(
        cls,
        practice: Practice,
        user=None,
        backup_name: str = "",
        backup_type: str = BackupRecord.TYPE_MANUAL,
        request=None
    ) -> BackupRecord:
        """
        Generates a complete tenant data snapshot, calculates SHA-256 checksum,
        and saves it to the practice's backup storage.
        """
        timestamp_str = timezone.now().strftime("%Y%m%d_%H%M%S")
        if not backup_name:
            backup_name = f"Backup_{practice.slug}_{timestamp_str}"

        # 1. Gather Practice Details
        practice_data = {
            "id": str(practice.id),
            "name": practice.name,
            "slug": practice.slug,
            "clinic_type": getattr(practice, 'clinic_type', ''),
            "phone_number": practice.phone_number,
            "email": practice.email,
            "address": practice.address,
            "city": practice.city,
            "state": practice.state,
            "country": practice.country,
        }

        # 2. Locations
        locations = list(PracticeLocation.objects.filter(practice=practice).values(
            'id', 'name', 'code', 'address', 'city', 'state', 'phone_number', 'is_primary'
        ))
        for loc in locations:
            loc['id'] = str(loc['id'])

        # 3. Services
        services = list(PracticeService.objects.filter(practice=practice).values(
            'id', 'name', 'category', 'description', 'price', 'duration_minutes', 'is_active'
        ))
        for s in services:
            s['id'] = str(s['id'])
            s['price'] = str(s['price']) if s.get('price') is not None else None

        # 4. Doctor Profiles
        doctors_qs = DoctorProfile.objects.filter(
            user__practice_memberships__practice=practice,
            user__practice_memberships__is_active=True
        ).distinct()
        doctors = []
        for d in doctors_qs:
            doctors.append({
                'id': str(d.id),
                'full_name': d.user.full_name,
                'qualification': d.qualifications,
                'specialization': d.specialization,
                'experience_years': d.experience_years,
                'consultation_fee': str(d.default_consultation_fee),
                'bio': d.bio,
                'is_verified': d.is_verified,
            })

        # 5. Website & Pages
        website = ClinicWebsite.objects.filter(practice=practice).first()
        website_data = None
        pages_data = []
        blogs_data = []
        if website:
            website_data = {
                "id": str(website.id),
                "title": website.title,
                "subdomain": website.subdomain,
                "template_style": website.template_style,
                "primary_color": website.primary_color,
                "contact_phone": website.contact_phone,
                "contact_email": website.contact_email,
                "is_published": website.is_published,
            }
            pages_data = list(WebsitePage.objects.filter(website=website).values(
                'id', 'title', 'slug', 'page_type', 'is_homepage', 'is_published', 'published_content'
            ))
            for p in pages_data:
                p['id'] = str(p['id'])

            blogs_data = []

        # 6. Leads & Enquiries
        leads = list(Lead.objects.filter(practice=practice).values(
            'id', 'patient_name', 'phone_number', 'email', 'service_requested', 'doctor_requested',
            'status', 'priority', 'source', 'created_at'
        ))
        for l in leads:
            l['id'] = str(l['id'])
            l['created_at'] = l['created_at'].isoformat() if l.get('created_at') else None

        # 7. Bookings & Appointments
        bookings = list(BookingRequest.objects.filter(practice=practice).values(
            'id', 'booking_reference', 'patient_name', 'phone_number', 'email',
            'consultation_mode', 'preferred_date', 'status', 'created_at'
        ))
        for b in bookings:
            b['id'] = str(b['id'])
            b['preferred_date'] = str(b['preferred_date']) if b.get('preferred_date') else None
            b['created_at'] = b['created_at'].isoformat() if b.get('created_at') else None

        # 8. Consent Records
        consents = list(ConsentRecord.objects.filter(practice=practice).values(
            'id', 'patient_identifier', 'patient_name', 'consent_type', 'status', 'audit_hash', 'granted_at'
        ))
        for c in consents:
            c['id'] = str(c['id'])
            c['granted_at'] = c['granted_at'].isoformat() if c.get('granted_at') else None

        # Total record count and manifest
        manifest = {
            "practice": 1,
            "locations_count": len(locations),
            "services_count": len(services),
            "doctors_count": len(doctors),
            "website_pages_count": len(pages_data),
            "blog_articles_count": len(blogs_data),
            "leads_count": len(leads),
            "bookings_count": len(bookings),
            "consents_count": len(consents),
        }
        total_records = sum(manifest.values())

        snapshot = {
            "metadata": {
                "backup_version": "1.0",
                "practice_id": str(practice.id),
                "practice_name": practice.name,
                "exported_at": timezone.now().isoformat(),
                "created_by": getattr(user, 'email', 'system') if user else 'system',
                "manifest": manifest,
            },
            "practice": practice_data,
            "locations": locations,
            "services": services,
            "doctors": doctors,
            "website": website_data,
            "pages": pages_data,
            "blogs": blogs_data,
            "leads": leads,
            "bookings": bookings,
            "consent_records": consents,
        }

        # Serialize to formatted JSON string
        json_content = json.dumps(snapshot, indent=2, default=str)
        checksum = hashlib.sha256(json_content.encode('utf-8')).hexdigest()

        # Save to disk
        backup_dir = os.path.join(settings.MEDIA_ROOT, 'backups', str(practice.id))
        os.makedirs(backup_dir, exist_ok=True)
        file_name = f"{backup_name}.json"
        full_file_path = os.path.join(backup_dir, file_name)

        with open(full_file_path, 'w', encoding='utf-8') as f:
            f.write(json_content)

        file_size = os.path.getsize(full_file_path)

        record = BackupRecord.objects.create(
            practice=practice,
            backup_name=backup_name,
            backup_type=backup_type,
            status=BackupRecord.STATUS_COMPLETED,
            created_by=user if user and user.is_authenticated else None,
            file_path=os.path.relpath(full_file_path, settings.MEDIA_ROOT),
            file_size_bytes=file_size,
            records_count=total_records,
            checksum_sha256=checksum,
            manifest=manifest,
            expires_at=timezone.now() + timedelta(days=90)  # Standard 90-day retention
        )

        AuditService.log(
            practice=practice,
            action="backup.created",
            category=AuditLog.CATEGORY_BACKUP,
            description=f"Backup snapshot '{backup_name}' generated ({total_records} records, {file_size} bytes).",
            actor=user,
            severity=AuditLog.SEVERITY_INFO,
            target_model="BackupRecord",
            target_id=str(record.id),
            target_repr=backup_name,
            changes={"checksum": checksum, "records_count": total_records},
            request=request
        )

        return record

    @classmethod
    def verify_backup(cls, backup: BackupRecord) -> dict:
        """
        Integrity check: re-reads the backup file, recomputes SHA-256,
        and validates against stored checksum.
        """
        full_path = os.path.join(settings.MEDIA_ROOT, backup.file_path)
        if not os.path.exists(full_path):
            return {
                "is_valid": False,
                "error": "Backup file not found on storage."
            }

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()

            current_checksum = hashlib.sha256(content.encode('utf-8')).hexdigest()
            checksum_matched = (current_checksum == backup.checksum_sha256)

            data = json.loads(content)
            return {
                "is_valid": checksum_matched,
                "checksum_verified": checksum_matched,
                "expected_checksum": backup.checksum_sha256,
                "computed_checksum": current_checksum,
                "manifest": backup.manifest,
                "total_records": backup.records_count,
            }
        except Exception as exc:
            return {
                "is_valid": False,
                "error": f"Corrupted or invalid JSON archive: {str(exc)}"
            }

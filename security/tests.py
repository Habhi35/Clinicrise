import os
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from authentication.services.jwt_service import get_tokens_for_user
from practices.models import Practice, PracticeMembership
from security.models import AuditLog, BackupRecord, ConsentRecord
from security.permissions import RoleChecker
from security.services.audit_service import AuditService
from security.services.backup_service import BackupService
from security.services.consent_service import ConsentService

User = get_user_model()


class SecurityAndAuditTestCase(TestCase):
    """
    Comprehensive test suite for Security & Audit in ClinicRise:
    - Role checks & RBAC matrix
    - Patient consent records & SHA-256 audit hashing
    - Compliance audit trail & actor tracking
    - Rate limits & abuse throttling
    - Practice database backups & integrity verification
    - Multi-tenant security isolation
    """

    def setUp(self):
        self.client = APIClient()

        # 1. Practice Owner User
        self.owner = User.objects.create_user(
            email='owner@cityclinic.com',
            phone_number='+919876540001',
            first_name='Dr. Vikram',
            last_name='Mehta',
            password='StrongPassword123!'
        )
        self.owner_tokens = get_tokens_for_user(self.owner)

        # 2. Practice Admin User
        self.admin_user = User.objects.create_user(
            email='admin@cityclinic.com',
            phone_number='+919876540002',
            first_name='Ananya',
            last_name='Iyer',
            password='StrongPassword123!'
        )
        self.admin_tokens = get_tokens_for_user(self.admin_user)

        # 3. Staff / Receptionist User
        self.staff_user = User.objects.create_user(
            email='staff@cityclinic.com',
            phone_number='+919876540003',
            first_name='Ramesh',
            last_name='Kumar',
            password='StrongPassword123!'
        )
        self.staff_tokens = get_tokens_for_user(self.staff_user)

        # 4. External User (Tenant B)
        self.other_user = User.objects.create_user(
            email='doctor@otherclinic.com',
            phone_number='+919876540004',
            password='StrongPassword123!'
        )
        self.other_tokens = get_tokens_for_user(self.other_user)

        # 5. Practice Tenant A: City Health Clinic
        self.practice = Practice.objects.create(
            name='City Health Clinic',
            slug='city-health-clinic',
            owner=self.owner,
            city='Bangalore',
            state='Karnataka',
            is_active=True
        )
        self.owner_membership = PracticeMembership.objects.create(
            practice=self.practice,
            user=self.owner,
            role=PracticeMembership.ROLE_OWNER,
            is_active=True
        )
        self.admin_membership = PracticeMembership.objects.create(
            practice=self.practice,
            user=self.admin_user,
            role=PracticeMembership.ROLE_ADMIN,
            is_active=True
        )
        self.staff_membership = PracticeMembership.objects.create(
            practice=self.practice,
            user=self.staff_user,
            role=PracticeMembership.ROLE_STAFF,
            is_active=True
        )

        # 6. Practice Tenant B: Other Clinic
        self.other_practice = Practice.objects.create(
            name='Other Polyclinic',
            slug='other-polyclinic',
            owner=self.other_user,
            is_active=True
        )
        self.other_membership = PracticeMembership.objects.create(
            practice=self.other_practice,
            user=self.other_user,
            role=PracticeMembership.ROLE_OWNER,
            is_active=True
        )

    # -------------------------------------------------------------
    # 1. ROLE CHECKS & RBAC
    # -------------------------------------------------------------

    def test_role_checker_utility(self):
        """Verifies role hierarchy: owner > admin > doctor > staff."""
        self.assertTrue(RoleChecker.is_owner(self.owner, self.practice))
        self.assertTrue(RoleChecker.is_admin(self.owner, self.practice))
        self.assertTrue(RoleChecker.is_doctor(self.owner, self.practice))
        self.assertTrue(RoleChecker.is_staff(self.owner, self.practice))

        self.assertFalse(RoleChecker.is_owner(self.admin_user, self.practice))
        self.assertTrue(RoleChecker.is_admin(self.admin_user, self.practice))
        self.assertTrue(RoleChecker.is_staff(self.admin_user, self.practice))

        self.assertFalse(RoleChecker.is_owner(self.staff_user, self.practice))
        self.assertFalse(RoleChecker.is_admin(self.staff_user, self.practice))
        self.assertTrue(RoleChecker.is_staff(self.staff_user, self.practice))

    def test_my_permissions_endpoint(self):
        """Authenticated user queries their role capabilities."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.staff_tokens['access']}")
        url = reverse('security:my_permissions')
        response = self.client.get(url, HTTP_X_PRACTICE_ID=str(self.practice.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['role'], PracticeMembership.ROLE_STAFF)
        self.assertFalse(response.data['capabilities']['can_manage_billing'])
        self.assertFalse(response.data['capabilities']['can_view_audit_logs'])
        self.assertTrue(response.data['capabilities']['can_record_consent'])

    def test_roles_overview_admin_only(self):
        """Only Admin or Owner can inspect team roles; Staff gets 403."""
        url = reverse('security:roles_overview')

        # Staff attempt -> 403
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.staff_tokens['access']}")
        res_staff = self.client.get(url, HTTP_X_PRACTICE_ID=str(self.practice.id))
        self.assertEqual(res_staff.status_code, status.HTTP_403_FORBIDDEN)

        # Admin attempt -> 200
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_tokens['access']}")
        res_admin = self.client.get(url, HTTP_X_PRACTICE_ID=str(self.practice.id))
        self.assertEqual(res_admin.status_code, status.HTTP_200_OK)
        self.assertEqual(res_admin.data['total_members'], 3)

    # -------------------------------------------------------------
    # 2. CONSENT RECORDS & AUDIT SIGNATURES
    # -------------------------------------------------------------

    def test_record_consent_with_sha256_audit_hash(self):
        """Recording consent computes SHA-256 hash and logs audit entry."""
        data = {
            'patient_identifier': '+919988776655',
            'patient_name': 'Meera Patel',
            'consent_type': ConsentRecord.TYPE_TELECONSULTATION,
            'consent_text': 'I agree to video recording for teleconsultation purposes.',
            'version': '1.2'
        }

        record = ConsentService.record_consent(self.practice, data)
        self.assertIsNotNone(record.audit_hash)
        self.assertEqual(len(record.audit_hash), 64)  # SHA-256 is 64 hex characters
        self.assertEqual(record.status, ConsentRecord.STATUS_GRANTED)

        # Verify audit log was automatically recorded
        audit = AuditLog.objects.filter(practice=self.practice, action='consent.granted').first()
        self.assertIsNotNone(audit)
        self.assertIn('+919988776655', audit.description)

    def test_withdraw_consent(self):
        """Revoking consent sets status to withdrawn and logs audit trail."""
        record = ConsentService.record_consent(self.practice, {
            'patient_identifier': '+919988776655',
            'consent_type': ConsentRecord.TYPE_WHATSAPP_NOTIFICATIONS,
            'consent_text': 'WhatsApp reminders agreement.'
        })

        revoked = ConsentService.withdraw_consent(
            practice=self.practice,
            patient_identifier='+919988776655',
            consent_type=ConsentRecord.TYPE_WHATSAPP_NOTIFICATIONS,
            reason='Patient opted out',
            performed_by=self.staff_user
        )

        self.assertEqual(len(revoked), 1)
        record.refresh_from_db()
        self.assertEqual(record.status, ConsentRecord.STATUS_WITHDRAWN)
        self.assertEqual(record.withdrawn_reason, 'Patient opted out')

        # Check has_active_consent returns False
        has_consent = ConsentService.has_active_consent(
            self.practice, '+919988776655', ConsentRecord.TYPE_WHATSAPP_NOTIFICATIONS
        )
        self.assertFalse(has_consent)

    def test_public_consent_intake_endpoint(self):
        """Public patient consent acceptance via API."""
        url = reverse('security:public_consent_intake', kwargs={'practice_slug_or_domain': self.practice.slug})
        payload = {
            'patient_identifier': '+919876599999',
            'patient_name': 'Kavita Rao',
            'consent_type': ConsentRecord.TYPE_MARKETING,
            'consent_text': 'I consent to promotional health tips.',
            'version': '2.0'
        }

        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
        self.assertIn('audit_hash', response.data)

    # -------------------------------------------------------------
    # 3. AUDIT LOGS & TENANT ISOLATION
    # -------------------------------------------------------------

    def test_audit_log_query_and_filtering(self):
        """Admins can view and filter practice audit logs."""
        AuditService.log(
            practice=self.practice,
            action="patient_privacy.exported",
            category=AuditLog.CATEGORY_PATIENT_PRIVACY,
            description="Patient health records exported for insurance.",
            actor=self.admin_user,
            severity=AuditLog.SEVERITY_WARNING
        )
        AuditService.log(
            practice=self.practice,
            action="auth.login",
            category=AuditLog.CATEGORY_AUTH,
            description="Staff user logged in successfully.",
            actor=self.staff_user,
            severity=AuditLog.SEVERITY_INFO
        )

        # Audit log in Other Practice (must not bleed over)
        AuditService.log(
            practice=self.other_practice,
            action="auth.login",
            category=AuditLog.CATEGORY_AUTH,
            description="Other clinic user logged in.",
            actor=self.other_user
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_tokens['access']}")
        url = reverse('security:audit_log_list')
        response = self.client.get(url, HTTP_X_PRACTICE_ID=str(self.practice.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should see exactly the 2 logs from practice A
        self.assertEqual(response.data['total_count'], 2)

        # Filter by severity=warning
        res_filtered = self.client.get(f"{url}?severity=warning", HTTP_X_PRACTICE_ID=str(self.practice.id))
        self.assertEqual(res_filtered.status_code, status.HTTP_200_OK)
        self.assertEqual(res_filtered.data['total_count'], 1)
        self.assertEqual(res_filtered.data['results'][0]['action'], 'patient_privacy.exported')

    # -------------------------------------------------------------
    # 4. BACKUPS & DATA SNAPSHOTS
    # -------------------------------------------------------------

    def test_create_and_verify_backup(self):
        """Creating a backup archives tenant records and verifies SHA-256 checksum."""
        backup = BackupService.create_backup(
            practice=self.practice,
            user=self.owner,
            backup_name="Test_Clinic_Snapshot"
        )

        self.assertEqual(backup.status, BackupRecord.STATUS_COMPLETED)
        self.assertTrue(backup.file_size_bytes > 0)
        self.assertIsNotNone(backup.checksum_sha256)
        self.assertEqual(len(backup.checksum_sha256), 64)

        # Integrity verification
        verification = BackupService.verify_backup(backup)
        self.assertTrue(verification['is_valid'])
        self.assertTrue(verification['checksum_verified'])
        self.assertEqual(verification['expected_checksum'], verification['computed_checksum'])

        # Verify audit log was recorded
        audit = AuditLog.objects.filter(practice=self.practice, action='backup.created').first()
        self.assertIsNotNone(audit)

    def test_backup_download_restricted_to_owner(self):
        """Backup archive download is restricted strictly to Practice Owner."""
        backup = BackupService.create_backup(self.practice, user=self.owner)

        url = reverse('security:backup_download', kwargs={'pk': backup.id})

        # Admin attempt -> 403 Forbidden
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.admin_tokens['access']}")
        res_admin = self.client.get(url, HTTP_X_PRACTICE_ID=str(self.practice.id))
        self.assertEqual(res_admin.status_code, status.HTTP_403_FORBIDDEN)

        # Owner attempt -> 200 OK FileResponse
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.owner_tokens['access']}")
        res_owner = self.client.get(url, HTTP_X_PRACTICE_ID=str(self.practice.id))
        self.assertEqual(res_owner.status_code, status.HTTP_200_OK)
        self.assertEqual(res_owner['Content-Type'], 'application/json')

import uuid
from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Practice(models.Model):
    """
    Practice/Clinic entity representing a tenant in the ClinicRise platform.
    Every medical clinic, dental center, or hospital has its own isolated practice tenant.
    """
    CLINIC_TYPE_SOLO = 'solo_clinic'
    CLINIC_TYPE_POLYCLINIC = 'polyclinic'
    CLINIC_TYPE_DENTAL = 'dental_clinic'
    CLINIC_TYPE_HOSPITAL_OPD = 'hospital_opd'
    CLINIC_TYPE_DIAGNOSTIC = 'diagnostic_center'
    CLINIC_TYPE_TELEHEALTH = 'telehealth'

    CLINIC_TYPE_CHOICES = [
        (CLINIC_TYPE_SOLO, 'Solo Clinic / Private Practice'),
        (CLINIC_TYPE_POLYCLINIC, 'Polyclinic / Multispeciality Clinic'),
        (CLINIC_TYPE_DENTAL, 'Dental Clinic'),
        (CLINIC_TYPE_HOSPITAL_OPD, 'Hospital OPD / Branch'),
        (CLINIC_TYPE_DIAGNOSTIC, 'Diagnostic & Wellness Center'),
        (CLINIC_TYPE_TELEHEALTH, 'Virtual / Teleconsultation Only'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, help_text="Clinic or Practice Name")
    slug = models.SlugField(max_length=255, unique=True, blank=True, db_index=True)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='owned_practices',
        help_text="User who owns the practice account"
    )

    clinic_type = models.CharField(
        max_length=50,
        choices=CLINIC_TYPE_CHOICES,
        default=CLINIC_TYPE_SOLO,
        blank=True
    )
    tagline = models.CharField(max_length=255, blank=True)
    about = models.TextField(blank=True)

    phone_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True, null=True)
    logo_url = models.URLField(max_length=500, blank=True, null=True)
    logo_image = models.ImageField(upload_to='practice_logos/', blank=True, null=True)

    # Location / Address details
    address = models.TextField(blank=True)
    landmark = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default='India')

    # Legal / Tax
    gst_number = models.CharField(max_length=30, blank=True)
    established_year = models.PositiveSmallIntegerField(null=True, blank=True)

    # Localization / Billing Settings
    currency = models.CharField(max_length=10, default='INR')
    timezone = models.CharField(max_length=50, default='Asia/Kolkata')

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Practice'
        verbose_name_plural = 'Practices'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or "practice"
            unique_slug = f"{base_slug}-{str(uuid.uuid4())[:8]}"
            self.slug = unique_slug
        super().save(*args, **kwargs)

    @property
    def logo_display_url(self):
        if self.logo_image:
            return self.logo_image.url
        return self.logo_url


class PracticeMembership(models.Model):
    """
    Membership linking Users to Practices with specific roles and permissions.
    Supports multi-tenant access (e.g. a Doctor can be part of multiple practices).
    """
    ROLE_OWNER = 'owner'
    ROLE_ADMIN = 'admin'
    ROLE_DOCTOR = 'doctor'
    ROLE_RECEPTIONIST = 'receptionist'
    ROLE_ASSISTANT = 'assistant'
    ROLE_STAFF = 'staff'

    ROLE_CHOICES = [
        (ROLE_OWNER, 'Practice Owner'),
        (ROLE_ADMIN, 'Practice Admin'),
        (ROLE_DOCTOR, 'Doctor / Practitioner'),
        (ROLE_RECEPTIONIST, 'Frontdesk / Receptionist'),
        (ROLE_ASSISTANT, 'Clinical Assistant / Nurse'),
        (ROLE_STAFF, 'General Staff'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    practice = models.ForeignKey(
        Practice,
        on_delete=models.CASCADE,
        related_name='memberships'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='practice_memberships'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_STAFF)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Practice Membership'
        verbose_name_plural = 'Practice Memberships'
        unique_together = ('practice', 'user')
        ordering = ['-joined_at']

    def __str__(self):
        return f"{self.user} - {self.get_role_display()} at {self.practice.name}"

    @property
    def is_owner(self):
        return self.role == self.ROLE_OWNER

    @property
    def is_admin(self):
        return self.role in [self.ROLE_OWNER, self.ROLE_ADMIN]

    @property
    def is_doctor(self):
        return self.role in [self.ROLE_OWNER, self.ROLE_ADMIN, self.ROLE_DOCTOR]

    @property
    def is_receptionist(self):
        return self.role in [self.ROLE_OWNER, self.ROLE_ADMIN, self.ROLE_RECEPTIONIST, self.ROLE_STAFF]

    @property
    def is_assistant(self):
        return self.role in [self.ROLE_OWNER, self.ROLE_ADMIN, self.ROLE_ASSISTANT]

    @property
    def is_clinical_staff(self):
        return self.role in [self.ROLE_OWNER, self.ROLE_ADMIN, self.ROLE_DOCTOR, self.ROLE_ASSISTANT]

    @property
    def is_frontdesk(self):
        return self.role in [self.ROLE_OWNER, self.ROLE_ADMIN, self.ROLE_RECEPTIONIST, self.ROLE_STAFF]


class DoctorProfile(models.Model):
    """
    Professional profile for doctors / practitioners on ClinicRise.
    Linked 1-to-1 with a User account.
    """
    GENDER_MALE = 'male'
    GENDER_FEMALE = 'female'
    GENDER_OTHER = 'other'
    GENDER_UNSPECIFIED = 'prefer_not_to_say'

    GENDER_CHOICES = [
        (GENDER_MALE, 'Male'),
        (GENDER_FEMALE, 'Female'),
        (GENDER_OTHER, 'Other'),
        (GENDER_UNSPECIFIED, 'Prefer not to say'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='doctor_profile'
    )
    title = models.CharField(max_length=20, default='Dr.', blank=True)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, blank=True)

    # Medical Registration & Licensing
    medical_license_number = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="State Medical Council / National Registration Number"
    )
    registration_council = models.CharField(
        max_length=255,
        blank=True,
        help_text="State Medical Council / Licensing Body (e.g. Maharashtra Medical Council)"
    )
    registration_year = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Year of Medical Registration"
    )

    specialization = models.CharField(
        max_length=150,
        help_text="e.g. General Physician, Dentist, Cardiologist, Pediatrician"
    )
    qualifications = models.CharField(
        max_length=255,
        help_text="e.g. MBBS, MD, BDS, MDS, MS"
    )
    experience_years = models.PositiveSmallIntegerField(
        default=0,
        help_text="Years of clinical practice experience"
    )
    languages_spoken = models.CharField(
        max_length=255,
        blank=True,
        default='English',
        help_text="Comma-separated languages spoken (e.g. English, Hindi, Telugu)"
    )
    bio = models.TextField(blank=True, help_text="Short professional summary / bio")
    default_consultation_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Default consultation fee in practice currency"
    )

    # Profile photo & Credentials
    profile_photo = models.ImageField(upload_to='doctor_photos/', blank=True, null=True)
    profile_photo_url = models.URLField(max_length=500, blank=True, null=True)
    registration_certificate = models.FileField(upload_to='doctor_certificates/', blank=True, null=True)
    registration_certificate_url = models.URLField(max_length=500, blank=True, null=True)

    is_verified = models.BooleanField(
        default=False,
        help_text="Designates whether the doctor license has been verified by platform admins"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Doctor Profile'
        verbose_name_plural = 'Doctor Profiles'
        ordering = ['-created_at']

    def __str__(self):
        prefix = f"{self.title} " if self.title else "Dr. "
        return f"{prefix}{self.user.full_name} ({self.specialization})"

    @property
    def full_name(self):
        prefix = f"{self.title} " if self.title else "Dr. "
        return f"{prefix}{self.user.full_name}".strip()

    @property
    def qualification(self):
        return self.qualifications

    @property
    def photo_display_url(self):
        if self.profile_photo:
            return self.profile_photo.url
        return self.profile_photo_url or self.user.avatar_url


class PracticeInvitation(models.Model):
    """
    Invitation issued by Practice Owners/Admins to invite doctors or staff into their practice.
    """
    STATUS_PENDING = 'pending'
    STATUS_ACCEPTED = 'accepted'
    STATUS_REJECTED = 'rejected'
    STATUS_REVOKED = 'revoked'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_REVOKED, 'Revoked'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    practice = models.ForeignKey(
        Practice,
        on_delete=models.CASCADE,
        related_name='invitations'
    )
    email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    role = models.CharField(
        max_length=20,
        choices=PracticeMembership.ROLE_CHOICES,
        default=PracticeMembership.ROLE_DOCTOR
    )
    invite_code = models.CharField(max_length=64, unique=True, db_index=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_invitations'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        verbose_name = 'Practice Invitation'
        verbose_name_plural = 'Practice Invitations'
        ordering = ['-created_at']

    def __str__(self):
        recipient = self.email or self.phone_number or "User"
        return f"Invitation for {recipient} as {self.get_role_display()} to {self.practice.name}"


class TenantAwareModel(models.Model):
    """
    Abstract base model for all tenant-scoped data in ClinicRise
    (e.g., Services, Timings, Clinic Images, Patients, Appointments, Prescriptions).
    Guarantees strict tenant isolation by scoping records to a specific Practice.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    practice = models.ForeignKey(
        Practice,
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)s_records",
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class PracticeService(TenantAwareModel):
    """
    Medical and healthcare services provided at a practice, optionally tied to a specific doctor.
    """
    CATEGORY_CONSULTATION = 'consultation'
    CATEGORY_FOLLOW_UP = 'follow_up'
    CATEGORY_PROCEDURE = 'procedure'
    CATEGORY_DIAGNOSTIC = 'diagnostic'
    CATEGORY_SURGERY = 'surgery'
    CATEGORY_TELECONSULTATION = 'teleconsultation'
    CATEGORY_OTHER = 'other'

    CATEGORY_CHOICES = [
        (CATEGORY_CONSULTATION, 'Consultation'),
        (CATEGORY_FOLLOW_UP, 'Follow-up Visit'),
        (CATEGORY_PROCEDURE, 'Clinical Procedure'),
        (CATEGORY_DIAGNOSTIC, 'Diagnostic / Investigation'),
        (CATEGORY_SURGERY, 'Minor / Day Surgery'),
        (CATEGORY_TELECONSULTATION, 'Video / Online Consultation'),
        (CATEGORY_OTHER, 'Other Healthcare Service'),
    ]

    doctor = models.ForeignKey(
        DoctorProfile,
        on_delete=models.CASCADE,
        related_name='services',
        null=True,
        blank=True,
        help_text="Optional doctor offering this service. If null, service is practice-wide."
    )
    name = models.CharField(max_length=255, help_text="Service name, e.g. General OPD Consultation")
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default=CATEGORY_CONSULTATION)
    description = models.TextField(blank=True, help_text="Service description or instructions for patients")
    duration_minutes = models.PositiveSmallIntegerField(default=15, help_text="Expected consultation/procedure duration in minutes")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Fee in practice currency")
    is_active = models.BooleanField(default=True)
    is_teleconsultation = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Practice Service'
        verbose_name_plural = 'Practice Services'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.practice.currency} {self.price})"


class DoctorSchedule(TenantAwareModel):
    """
    Working hours, OPD sessions and availability schedule for a doctor at a specific practice.
    """
    DAY_MONDAY = 0
    DAY_TUESDAY = 1
    DAY_WEDNESDAY = 2
    DAY_THURSDAY = 3
    DAY_FRIDAY = 4
    DAY_SATURDAY = 5
    DAY_SUNDAY = 6

    DAY_CHOICES = [
        (DAY_MONDAY, 'Monday'),
        (DAY_TUESDAY, 'Tuesday'),
        (DAY_WEDNESDAY, 'Wednesday'),
        (DAY_THURSDAY, 'Thursday'),
        (DAY_FRIDAY, 'Friday'),
        (DAY_SATURDAY, 'Saturday'),
        (DAY_SUNDAY, 'Sunday'),
    ]

    doctor = models.ForeignKey(
        DoctorProfile,
        on_delete=models.CASCADE,
        related_name='schedules'
    )
    day_of_week = models.PositiveSmallIntegerField(choices=DAY_CHOICES, help_text="Day of the week (0=Monday, 6=Sunday)")
    session_name = models.CharField(max_length=100, default='General OPD', help_text="e.g. Morning Shift, Evening OPD")
    start_time = models.TimeField(help_text="Shift start time, e.g. 09:00")
    end_time = models.TimeField(help_text="Shift end time, e.g. 13:00")
    slot_duration_minutes = models.PositiveSmallIntegerField(default=15, help_text="Duration per appointment slot in minutes")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Doctor Schedule'
        verbose_name_plural = 'Doctor Schedules'
        ordering = ['day_of_week', 'start_time']

    def __str__(self):
        return f"{self.doctor} - {self.get_day_of_week_display()}: {self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}"


class PracticeImage(TenantAwareModel):
    """
    Clinic exterior/interior photos, logos, and medical accreditation images.
    """
    IMAGE_TYPE_CLINIC_FACADE = 'clinic_facade'
    IMAGE_TYPE_RECEPTION = 'reception'
    IMAGE_TYPE_CONSULTATION = 'consultation_room'
    IMAGE_TYPE_WAITING = 'waiting_area'
    IMAGE_TYPE_EQUIPMENT = 'equipment'
    IMAGE_TYPE_CERTIFICATE = 'certificate'
    IMAGE_TYPE_LOGO = 'logo'
    IMAGE_TYPE_OTHER = 'other'

    IMAGE_TYPE_CHOICES = [
        (IMAGE_TYPE_CLINIC_FACADE, 'Clinic Exterior / Facade'),
        (IMAGE_TYPE_RECEPTION, 'Reception / Frontdesk'),
        (IMAGE_TYPE_CONSULTATION, 'Doctor Consultation Room'),
        (IMAGE_TYPE_WAITING, 'Patient Waiting Area'),
        (IMAGE_TYPE_EQUIPMENT, 'Medical Equipment / OT'),
        (IMAGE_TYPE_CERTIFICATE, 'License / Certificate'),
        (IMAGE_TYPE_LOGO, 'Clinic Logo'),
        (IMAGE_TYPE_OTHER, 'Other Photo'),
    ]

    image = models.ImageField(upload_to='practice_images/', blank=True, null=True)
    image_url = models.URLField(max_length=500, blank=True, null=True, help_text="Direct URL to hosted image")
    image_type = models.CharField(max_length=50, choices=IMAGE_TYPE_CHOICES, default=IMAGE_TYPE_OTHER)
    caption = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Practice Image'
        verbose_name_plural = 'Practice Images'
        ordering = ['order', '-created_at']

    def __str__(self):
        return f"{self.practice.name} - {self.get_image_type_display()}"


class DoctorOnboarding(models.Model):
    """
    Stateful multi-step onboarding wizard for doctors.
    Persists progress, completed steps, and draft forms across sessions.
    """
    STEP_DOCTOR_PROFILE = 'doctor_profile'
    STEP_CLINIC_DETAILS = 'clinic_details'
    STEP_SERVICES = 'services'
    STEP_TIMINGS = 'timings'
    STEP_IMAGES = 'images'
    STEP_REVIEW = 'review'
    STEP_COMPLETED = 'completed'

    STEP_CHOICES = [
        (STEP_DOCTOR_PROFILE, 'Doctor Profile & Registration Number'),
        (STEP_CLINIC_DETAILS, 'Clinic & Practice Details'),
        (STEP_SERVICES, 'Clinical Services & Consultation Fees'),
        (STEP_TIMINGS, 'Clinic Timings & Working Hours'),
        (STEP_IMAGES, 'Clinic Photos & Verification Documents'),
        (STEP_REVIEW, 'Review & Finalize'),
        (STEP_COMPLETED, 'Onboarding Completed'),
    ]

    STEPS_ORDER = [
        STEP_DOCTOR_PROFILE,
        STEP_CLINIC_DETAILS,
        STEP_SERVICES,
        STEP_TIMINGS,
        STEP_IMAGES,
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='doctor_onboarding'
    )
    practice = models.ForeignKey(
        Practice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='doctor_onboardings'
    )
    current_step = models.CharField(max_length=30, choices=STEP_CHOICES, default=STEP_DOCTOR_PROFILE)
    completed_steps = models.JSONField(default=list, blank=True)
    draft_data = models.JSONField(default=dict, blank=True)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Doctor Onboarding'
        verbose_name_plural = 'Doctor Onboardings'
        ordering = ['-updated_at']

    def __str__(self):
        status_label = "Completed" if self.is_completed else f"Step: {self.current_step}"
        return f"Onboarding for {self.user} ({status_label})"

    @property
    def progress_percentage(self):
        if self.is_completed:
            return 100
        completed_count = len(set(self.completed_steps or []).intersection(set(self.STEPS_ORDER)))
        total_steps = len(self.STEPS_ORDER)
        return int((completed_count / total_steps) * 100)

    def mark_step_completed(self, step_name):
        steps = set(self.completed_steps or [])
        steps.add(step_name)
        self.completed_steps = list(steps)
        if step_name in self.STEPS_ORDER:
            idx = self.STEPS_ORDER.index(step_name)
            if idx + 1 < len(self.STEPS_ORDER):
                self.current_step = self.STEPS_ORDER[idx + 1]
            else:
                self.current_step = self.STEP_REVIEW
        self.save(update_fields=['completed_steps', 'current_step', 'updated_at'])

    def save_draft_step(self, step_name, data):
        if not isinstance(self.draft_data, dict):
            self.draft_data = {}
        import json
        from django.core.serializers.json import DjangoJSONEncoder
        self.draft_data[step_name] = json.loads(json.dumps(data, cls=DjangoJSONEncoder))
        self.save(update_fields=['draft_data', 'updated_at'])

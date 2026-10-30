import logging
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from practices.models import PracticeMembership
from websites.models import WebsitePage

logger = logging.getLogger(__name__)


class ContentApprovalService:
    """
    Workflow engine for clinical content review and doctor approvals:
    - Draft submission by staff/author
    - Clinical accuracy review by verified doctors
    - Rejection with clinical feedback notes
    - Pre-publication doctor sign-off gating
    - Unified doctor approval queue
    - Blog drafts management
    """

    STATUS_DRAFT = 'draft'
    STATUS_PENDING = 'pending_approval'
    STATUS_APPROVED = 'approved'
    STATUS_CHANGES_REQUESTED = 'changes_requested'

    @classmethod
    def get_approval_data(cls, page):
        """Extracts normalized approval metadata from page draft_content."""
        draft = page.draft_content if isinstance(page.draft_content, dict) else {}
        approval = draft.get('approval')
        if not isinstance(approval, dict):
            approval = {
                'status': cls.STATUS_DRAFT,
                'submitted_by': None,
                'submitted_at': None,
                'submission_notes': '',
                'reviewed_by': None,
                'reviewed_at': None,
                'review_notes': '',
                'history': [],
            }
        return approval

    @classmethod
    def is_doctor_or_owner(cls, user, practice):
        """Checks if the user holds a Doctor, Admin, or Owner role in the practice."""
        if not user or not user.is_authenticated or not practice:
            return False
        membership = PracticeMembership.objects.filter(
            practice=practice,
            user=user,
            is_active=True
        ).first()
        return bool(membership and membership.role in [
            PracticeMembership.ROLE_OWNER,
            PracticeMembership.ROLE_ADMIN,
            PracticeMembership.ROLE_DOCTOR
        ])

    @classmethod
    def submit_for_review(cls, page, user, submission_notes=''):
        """
        Staff or author submits website page or blog draft for doctor review.
        """
        if not isinstance(page.draft_content, dict):
            page.draft_content = {}

        now_iso = timezone.now().isoformat()
        approval = cls.get_approval_data(page)

        approval['status'] = cls.STATUS_PENDING
        approval['submitted_by'] = {
            'id': str(user.id),
            'name': getattr(user, 'full_name', str(user)),
            'email': getattr(user, 'email', ''),
        }
        approval['submitted_at'] = now_iso
        approval['submission_notes'] = submission_notes.strip()

        history = approval.get('history', [])
        history.append({
            'action': 'submitted_for_review',
            'user': getattr(user, 'full_name', str(user)),
            'timestamp': now_iso,
            'notes': submission_notes.strip(),
        })
        approval['history'] = history

        page.draft_content['approval'] = approval
        page.has_unpublished_changes = True
        page.save(update_fields=['draft_content', 'has_unpublished_changes', 'updated_at'])

        # Also update parent website status
        page.website.has_unpublished_changes = True
        page.website.save(update_fields=['has_unpublished_changes'])

        logger.info(f"Page '{page.title}' ({page.id}) submitted for review by {user}")
        return page

    @classmethod
    def review_content(cls, page, doctor_user, action, review_notes=''):
        """
        Doctor reviews submitted content:
        action = 'approve' -> marks content approved for publication.
        action = 'request_changes' -> requests clinical revisions with doctor feedback.
        """
        if not cls.is_doctor_or_owner(doctor_user, page.website.practice):
            raise PermissionDenied("Only verified medical practitioners or practice owners can review and approve content.")

        if action not in ['approve', 'request_changes']:
            raise ValidationError("Action must be either 'approve' or 'request_changes'.")

        now_iso = timezone.now().isoformat()
        approval = cls.get_approval_data(page)

        doc_title = 'Dr.'
        if hasattr(doctor_user, 'doctor_profile') and doctor_user.doctor_profile:
            doc_title = doctor_user.doctor_profile.title or 'Dr.'

        reviewer_info = {
            'id': str(doctor_user.id),
            'name': f"{doc_title} {doctor_user.full_name}".strip(),
            'email': getattr(doctor_user, 'email', ''),
        }

        if action == 'approve':
            approval['status'] = cls.STATUS_APPROVED
            approval['reviewed_by'] = reviewer_info
            approval['reviewed_at'] = now_iso
            approval['review_notes'] = review_notes.strip()

            history_entry = {
                'action': 'approved',
                'doctor': reviewer_info['name'],
                'timestamp': now_iso,
                'comments': review_notes.strip() or 'Clinically approved for publication.',
            }
        else:
            approval['status'] = cls.STATUS_CHANGES_REQUESTED
            approval['reviewed_by'] = reviewer_info
            approval['reviewed_at'] = now_iso
            approval['review_notes'] = review_notes.strip()

            history_entry = {
                'action': 'changes_requested',
                'doctor': reviewer_info['name'],
                'timestamp': now_iso,
                'comments': review_notes.strip() or 'Revisions requested by doctor before publication.',
            }

        history = approval.get('history', [])
        history.append(history_entry)
        approval['history'] = history

        if not isinstance(page.draft_content, dict):
            page.draft_content = {}
        page.draft_content['approval'] = approval
        page.save(update_fields=['draft_content', 'updated_at'])

        logger.info(f"Page '{page.title}' ({page.id}) reviewed by {doctor_user}: {action}")
        return page

    @classmethod
    def check_can_publish(cls, page, user):
        """
        Enforces doctor approval gate before publication:
        - If user is Doctor, Admin, or Owner: allowed.
        - If user is Frontdesk/Staff: requires approval['status'] == 'approved'.
        """
        is_dr_or_owner = cls.is_doctor_or_owner(user, page.website.practice)
        if is_dr_or_owner:
            return True, ""

        approval = cls.get_approval_data(page)
        curr_status = approval.get('status', cls.STATUS_DRAFT)

        if curr_status != cls.STATUS_APPROVED:
            status_labels = {
                cls.STATUS_DRAFT: "Draft (Not submitted for doctor review)",
                cls.STATUS_PENDING: "Pending Doctor Review",
                cls.STATUS_CHANGES_REQUESTED: "Changes Requested by Doctor",
            }
            label = status_labels.get(curr_status, curr_status)
            return False, f"Publishing restricted: Content requires doctor approval before publication. Current status is '{label}'. Please submit it for doctor review."

        return True, ""

    @classmethod
    def get_approval_queue(cls, website, status_filter=None):
        """
        Retrieves all items requiring doctor approval across website pages and blog posts.
        """
        pages = website.pages.all().order_by('-updated_at')
        pending_list = []
        approved_list = []
        changes_requested_list = []

        for p in pages:
            draft = p.draft_content if isinstance(p.draft_content, dict) else {}
            approval = draft.get('approval') or {}
            item_status = approval.get('status', cls.STATUS_DRAFT)
            is_blog = draft.get('content_type') == 'blog_post' or p.slug.startswith('blog/')

            summary_item = {
                'id': str(p.id),
                'title': p.title,
                'slug': p.slug,
                'content_type': 'blog_post' if is_blog else 'page',
                'page_type': p.page_type,
                'approval_status': item_status,
                'submitted_by': approval.get('submitted_by'),
                'submitted_at': approval.get('submitted_at'),
                'submission_notes': approval.get('submission_notes', ''),
                'reviewed_by': approval.get('reviewed_by'),
                'reviewed_at': approval.get('reviewed_at'),
                'review_notes': approval.get('review_notes', ''),
                'has_unpublished_changes': p.has_unpublished_changes,
                'is_published': p.is_published,
                'updated_at': p.updated_at,
            }

            if item_status == cls.STATUS_PENDING:
                pending_list.append(summary_item)
            elif item_status == cls.STATUS_APPROVED:
                approved_list.append(summary_item)
            elif item_status == cls.STATUS_CHANGES_REQUESTED:
                changes_requested_list.append(summary_item)

        items = pending_list + changes_requested_list + approved_list
        if status_filter:
            items = [item for item in items if item['approval_status'] == status_filter]

        return {
            'total_pending': len(pending_list),
            'total_approved': len(approved_list),
            'total_changes_requested': len(changes_requested_list),
            'items': items,
        }

    # =================================================================
    # BLOG POST HELPER METHODS (Stored natively in WebsitePage)
    # =================================================================

    @classmethod
    def list_blogs(cls, website, status_filter=None):
        """Lists all blog posts associated with this clinic website."""
        pages = website.pages.filter(page_type=WebsitePage.PAGE_TYPE_CUSTOM).order_by('-created_at')
        blog_posts = []

        for page in pages:
            draft = page.draft_content if isinstance(page.draft_content, dict) else {}
            if draft.get('content_type') == 'blog_post' or page.slug.startswith('blog/'):
                approval = draft.get('approval') or {}
                post_status = approval.get('status', cls.STATUS_DRAFT)
                if status_filter and post_status != status_filter:
                    continue

                blog_posts.append({
                    'id': str(page.id),
                    'title': page.title,
                    'slug': page.slug.replace('blog/', ''),
                    'full_slug': page.slug,
                    'category': draft.get('category', 'General Healthcare'),
                    'excerpt': draft.get('excerpt', ''),
                    'cover_image_url': draft.get('cover_image_url', ''),
                    'author_doctor_name': draft.get('author_doctor_name', ''),
                    'read_time_minutes': draft.get('read_time_minutes', 3),
                    'tags': draft.get('tags', []),
                    'approval_status': post_status,
                    'submitted_by': approval.get('submitted_by'),
                    'reviewed_by': approval.get('reviewed_by'),
                    'review_notes': approval.get('review_notes', ''),
                    'is_published': page.is_published,
                    'published_at': page.published_at,
                    'created_at': page.created_at,
                    'updated_at': page.updated_at,
                })

        return blog_posts

    @classmethod
    def create_blog(cls, website, author_user, data):
        """Creates a new blog article draft under the clinic website."""
        from django.utils.text import slugify
        raw_slug = data.get('slug') or slugify(data.get('title', 'blog-post'))
        slug = f"blog/{raw_slug}" if not raw_slug.startswith('blog/') else raw_slug

        # Ensure slug uniqueness for this website
        existing_count = WebsitePage.objects.filter(website=website, slug=slug).count()
        if existing_count > 0:
            slug = f"{slug}-{timezone.now().strftime('%m%d%H%M')}"

        now_iso = timezone.now().isoformat()
        draft_content = {
            'content_type': 'blog_post',
            'category': data.get('category', 'General Healthcare'),
            'excerpt': data.get('excerpt', ''),
            'body_html': data.get('body_html', ''),
            'cover_image_url': data.get('cover_image_url', ''),
            'author_doctor_id': data.get('author_doctor_id', ''),
            'author_doctor_name': data.get('author_doctor_name', getattr(author_user, 'full_name', 'Medical Staff')),
            'tags': data.get('tags', []),
            'read_time_minutes': data.get('read_time_minutes', 4),
            'approval': {
                'status': cls.STATUS_DRAFT,
                'submitted_by': None,
                'submitted_at': None,
                'submission_notes': '',
                'reviewed_by': None,
                'reviewed_at': None,
                'review_notes': '',
                'history': [{
                    'action': 'created',
                    'user': getattr(author_user, 'full_name', str(author_user)),
                    'timestamp': now_iso,
                    'notes': 'Draft created.'
                }]
            }
        }

        page = WebsitePage.objects.create(
            website=website,
            title=data.get('title', 'Untitled Article'),
            slug=slug,
            page_type=WebsitePage.PAGE_TYPE_CUSTOM,
            is_in_navigation=False,
            is_in_footer=False,
            draft_content=draft_content,
            has_unpublished_changes=True,
            is_published=False
        )

        return page

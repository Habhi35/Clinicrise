import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from practices.models import Practice

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Practice)
def auto_provision_practice_subscription(sender, instance, created, **kwargs):
    """
    Automatically creates a 14-day Free Trial subscription
    whenever a new Practice tenant is registered.
    """
    if created:
        try:
            from billing.services.billing_service import BillingService
            BillingService.create_trial_subscription(instance)
            logger.info(f"Auto-provisioned trial subscription for new practice {instance.name} ({instance.id})")
        except Exception as e:
            logger.exception(f"Failed to auto-provision trial subscription for practice {instance.id}: {str(e)}")

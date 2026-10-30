from django.core.management.base import BaseCommand
from billing.services.billing_service import BillingService


class Command(BaseCommand):
    help = 'Processes daily subscription expirations, auto-renewals, grace periods, and applies scheduled downgrades.'

    def handle(self, *args, **options):
        self.stdout.write("Starting daily subscription renewal and expiration processing...")
        stats = BillingService.process_expired_subscriptions()
        self.stdout.write(self.style.SUCCESS(
            f"Subscription processing complete:\n"
            f" - Expired / Suspended: {stats['expired']}\n"
            f" - Moved to Grace Period: {stats['grace_period']}\n"
            f" - Cancelled at Period End: {stats['cancelled']}\n"
            f" - Auto-renewed: {stats['renewed']}"
        ))

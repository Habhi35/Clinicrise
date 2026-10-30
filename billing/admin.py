from django.contrib import admin
from billing.models import (
    Invoice,
    PaymentTransaction,
    PracticeSubscription,
    SubscriptionPlan,
    WebhookEvent,
)


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'tier', 'monthly_price', 'yearly_price', 'max_doctors', 'max_locations', 'is_active', 'is_public', 'sort_order')
    list_filter = ('tier', 'is_active', 'is_public')
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(PracticeSubscription)
class PracticeSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('practice', 'plan', 'status', 'billing_interval', 'current_period_end', 'auto_renew', 'is_in_trial')
    list_filter = ('status', 'billing_interval', 'auto_renew', 'plan')
    search_fields = ('practice__name', 'practice__slug', 'gateway_customer_id', 'gateway_subscription_id')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'practice', 'plan_snapshot_name', 'billing_interval', 'total_amount', 'currency', 'status', 'paid_at', 'created_at')
    list_filter = ('status', 'billing_interval', 'currency', 'payment_gateway')
    search_fields = ('invoice_number', 'practice__name', 'gateway_order_id', 'gateway_payment_id')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'invoice', 'practice', 'gateway', 'action', 'amount', 'currency', 'status', 'created_at')
    list_filter = ('gateway', 'status', 'action')
    search_fields = ('invoice__invoice_number', 'practice__name', 'gateway_order_id', 'gateway_payment_id')
    readonly_fields = ('created_at',)


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ('event_id', 'gateway', 'event_type', 'status', 'processed_at', 'created_at')
    list_filter = ('gateway', 'status', 'event_type')
    search_fields = ('event_id', 'event_type')
    readonly_fields = ('created_at',)

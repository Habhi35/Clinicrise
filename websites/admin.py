from django.contrib import admin
from websites.models import (
    ClinicWebsite,
    CustomDomain,
    WebsiteInquiry,
    WebsitePage,
    WebsitePageRevision,
)


class CustomDomainInline(admin.TabularInline):
    model = CustomDomain
    extra = 1
    fields = ('domain', 'is_primary', 'status', 'ssl_status', 'cname_target')


class WebsitePageInline(admin.TabularInline):
    model = WebsitePage
    extra = 0
    fields = ('title', 'slug', 'is_homepage', 'page_type', 'is_published', 'has_unpublished_changes', 'nav_order')


@admin.register(ClinicWebsite)
class ClinicWebsiteAdmin(admin.ModelAdmin):
    list_display = ('title', 'practice', 'subdomain', 'template_style', 'is_published', 'is_maintenance', 'has_unpublished_changes', 'created_at')
    list_filter = ('is_published', 'is_maintenance', 'template_style')
    search_fields = ('title', 'subdomain', 'practice__name')
    prepopulated_fields = {'subdomain': ('title',)}
    inlines = [CustomDomainInline, WebsitePageInline]
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(CustomDomain)
class CustomDomainAdmin(admin.ModelAdmin):
    list_display = ('domain', 'website', 'is_primary', 'status', 'ssl_status', 'last_verified_at', 'created_at')
    list_filter = ('status', 'ssl_status', 'is_primary')
    search_fields = ('domain', 'website__title', 'website__subdomain')
    readonly_fields = ('id', 'verification_token', 'created_at', 'updated_at')


@admin.register(WebsitePage)
class WebsitePageAdmin(admin.ModelAdmin):
    list_display = ('title', 'website', 'slug', 'is_homepage', 'page_type', 'is_published', 'has_unpublished_changes', 'published_version', 'nav_order')
    list_filter = ('is_published', 'has_unpublished_changes', 'page_type', 'is_homepage')
    search_fields = ('title', 'slug', 'website__title')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('id', 'published_version', 'published_at', 'created_at', 'updated_at')


@admin.register(WebsitePageRevision)
class WebsitePageRevisionAdmin(admin.ModelAdmin):
    list_display = ('page', 'version', 'published_at', 'published_by')
    list_filter = ('published_at',)
    search_fields = ('page__title', 'page__website__title')
    readonly_fields = ('id', 'published_at')


@admin.register(WebsiteInquiry)
class WebsiteInquiryAdmin(admin.ModelAdmin):
    list_display = ('patient_name', 'website', 'phone_number', 'preferred_service', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('patient_name', 'phone_number', 'email', 'website__title')
    readonly_fields = ('id', 'created_at')

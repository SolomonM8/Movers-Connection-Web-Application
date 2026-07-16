from django.contrib import admin

from .models import BugReport, Report, SupportMessage, SupportThread


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("reporter", "reported_user", "reason", "status", "created_at")
    list_filter = ("status", "reason")


@admin.register(BugReport)
class BugReportAdmin(admin.ModelAdmin):
    list_display = ("reporter", "status", "created_at")
    list_filter = ("status",)


class SupportMessageInline(admin.TabularInline):
    model = SupportMessage
    extra = 0


@admin.register(SupportThread)
class SupportThreadAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at")
    inlines = [SupportMessageInline]

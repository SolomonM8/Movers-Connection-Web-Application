from django.contrib import admin

from .models import Job, JobApplication, Message


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("__str__", "driver_profile", "county", "job_date", "status", "pricing_model", "workers_needed")
    list_filter = ("status", "job_type", "pricing_model", "county__state")
    search_fields = ("driver_profile__company_name", "county__name", "city")


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ("__str__", "job", "laborer_profile", "status", "applied_at")
    list_filter = ("status",)
    search_fields = ("laborer_profile__display_name", "job__county__name")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("__str__", "application", "sender", "created_at")
    search_fields = ("sender__email", "body")

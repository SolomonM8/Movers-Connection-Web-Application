from django.contrib import admin

from .models import Job


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("__str__", "driver_profile", "county", "job_date", "pricing_model", "workers_needed")
    list_filter = ("job_type", "pricing_model", "county__state")
    search_fields = ("driver_profile__company_name", "county__name", "city")

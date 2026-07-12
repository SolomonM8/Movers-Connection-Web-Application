from django.contrib import admin

from .models import Conversation, ConversationMessage, Job, JobApplication, JobRating


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("__str__", "driver_profile", "county", "job_date", "status", "pricing_model", "workers_needed")
    list_filter = ("status", "job_type", "pricing_model", "county__state")
    search_fields = ("driver_profile__company_name", "county__name", "city")


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ("__str__", "job", "laborer_profile", "status", "source", "applied_at")
    list_filter = ("status", "source")
    search_fields = ("laborer_profile__display_name", "job__county__name")


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("__str__", "driver_profile", "laborer_profile", "created_at")
    search_fields = ("driver_profile__company_name", "laborer_profile__display_name")


@admin.register(ConversationMessage)
class ConversationMessageAdmin(admin.ModelAdmin):
    list_display = ("__str__", "conversation", "sender", "is_system", "created_at")
    search_fields = ("sender__email", "body")


@admin.register(JobRating)
class JobRatingAdmin(admin.ModelAdmin):
    list_display = ("__str__", "application", "professionalism", "punctuality", "moving_skill", "created_at")
    search_fields = ("application__laborer_profile__display_name",)

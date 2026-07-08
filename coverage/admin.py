from django.contrib import admin

from .models import County, ServiceArea


@admin.register(County)
class CountyAdmin(admin.ModelAdmin):
    list_display = ("name", "state", "fips")
    list_filter = ("state",)
    search_fields = ("name", "fips")


@admin.register(ServiceArea)
class ServiceAreaAdmin(admin.ModelAdmin):
    list_display = ("laborer_profile", "county")
    list_filter = ("county__state",)
    search_fields = ("laborer_profile__display_name", "county__name")

import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.generic import TemplateView

from accounts.constants import US_STATE_CHOICES
from accounts.models import Connection, User
from accounts.views import RoleRequiredMixin

from .models import County, ServiceArea

MAX_SERVICE_COUNTIES = 6


def _serialize_service_areas(profile):
    served = (
        ServiceArea.objects.filter(laborer_profile=profile)
        .select_related("county")
        .order_by("-is_primary", "county__state", "county__name")
    )
    return [
        {
            "fips": sa.county_id,
            "name": sa.county.name,
            "state": sa.county.state,
            "is_primary": sa.is_primary,
        }
        for sa in served
    ]


class ServiceAreaView(RoleRequiredMixin, TemplateView):
    template_name = "coverage/service_areas.html"
    allowed_roles = (User.Role.LABORER,)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.request.user.laborer_profile
        selected_state = self.request.GET.get("state", "")

        selected_counties = _serialize_service_areas(profile)

        context["states"] = US_STATE_CHOICES
        context["selected_state"] = selected_state
        context["total_count"] = len(selected_counties)
        context["max_counties"] = MAX_SERVICE_COUNTIES
        context["selected_counties_json"] = json.dumps(selected_counties)
        context["selected_fips_json"] = json.dumps([c["fips"] for c in selected_counties])
        return context


class ToggleServiceAreaAPIView(RoleRequiredMixin, View):
    allowed_roles = (User.Role.LABORER,)

    def post(self, request, fips):
        profile = request.user.laborer_profile
        county = get_object_or_404(County, fips=fips)
        existing = ServiceArea.objects.filter(laborer_profile=profile, county=county).first()

        if existing:
            was_primary = existing.is_primary
            existing.delete()
            if was_primary:
                promoted = ServiceArea.objects.filter(laborer_profile=profile).order_by("id").first()
                if promoted:
                    promoted.is_primary = True
                    promoted.save(update_fields=["is_primary"])
            status = "removed"
        else:
            current_count = ServiceArea.objects.filter(laborer_profile=profile).count()
            if current_count >= MAX_SERVICE_COUNTIES:
                selected_counties = _serialize_service_areas(profile)
                return JsonResponse(
                    {
                        "status": "limit_reached",
                        "message": (
                            f"You can only select a home county plus up to "
                            f"{MAX_SERVICE_COUNTIES - 1} more. Remove one to add another."
                        ),
                        "total_count": len(selected_counties),
                        "selected_counties": selected_counties,
                    },
                    status=400,
                )
            ServiceArea.objects.create(
                laborer_profile=profile, county=county, is_primary=current_count == 0
            )
            status = "added"

        selected_counties = _serialize_service_areas(profile)
        return JsonResponse(
            {
                "status": status,
                "fips": fips,
                "county_name": county.name,
                "state": county.state,
                "total_count": len(selected_counties),
                "max_counties": MAX_SERVICE_COUNTIES,
                "selected_counties": selected_counties,
            }
        )


class SetPrimaryServiceAreaAPIView(RoleRequiredMixin, View):
    allowed_roles = (User.Role.LABORER,)

    def post(self, request, fips):
        profile = request.user.laborer_profile
        service_area = get_object_or_404(
            ServiceArea, laborer_profile=profile, county_id=fips
        )
        ServiceArea.objects.filter(laborer_profile=profile).update(is_primary=False)
        service_area.is_primary = True
        service_area.save(update_fields=["is_primary"])
        return JsonResponse({"selected_counties": _serialize_service_areas(profile)})


class MapView(LoginRequiredMixin, TemplateView):
    template_name = "coverage/map.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["states_json"] = json.dumps(dict(US_STATE_CHOICES))
        context["is_driver"] = self.request.user.role == User.Role.DRIVER
        return context


class CountyLaborersAPIView(LoginRequiredMixin, View):
    def get(self, request, fips):
        county = get_object_or_404(County, fips=fips)
        service_areas = (
            ServiceArea.objects.filter(county=county)
            .select_related("laborer_profile", "laborer_profile__user")
            .order_by("-is_primary")
        )
        friend_ids = set()
        if request.user.role == User.Role.DRIVER:
            friend_ids = set(
                Connection.objects.filter(driver_profile=request.user.driver_profile).values_list(
                    "laborer_profile_id", flat=True
                )
            )
        data = {
            "county_name": county.name,
            "state": county.state,
            "laborers": [
                {
                    "laborer_id": sa.laborer_profile_id,
                    "display_name": sa.laborer_profile.display_name or sa.laborer_profile.user.email,
                    "city": sa.laborer_profile.city,
                    "state": sa.laborer_profile.state,
                    "phone_number": sa.laborer_profile.phone_number,
                    "is_primary": sa.is_primary,
                    "is_friend": sa.laborer_profile_id in friend_ids,
                }
                for sa in service_areas
            ],
        }
        return JsonResponse(data)

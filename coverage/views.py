import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.generic import TemplateView

from accounts.constants import US_STATE_CHOICES
from accounts.models import LaborerProfile, User
from accounts.views import RoleRequiredMixin

from .models import County, ServiceArea

MAX_SERVICE_COUNTIES = 6


def _serialize_service_areas(profile):
    served = (
        ServiceArea.objects.filter(laborer_profile=profile)
        .select_related("county")
        .order_by("county__state", "county__name")
    )
    summary = {}
    selected_fips = []
    for service_area in served:
        summary.setdefault(service_area.county.state, []).append(service_area.county.name)
        selected_fips.append(service_area.county_id)
    return summary, selected_fips


class ServiceAreaView(RoleRequiredMixin, TemplateView):
    template_name = "coverage/service_areas.html"
    allowed_roles = (User.Role.LABORER,)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.request.user.laborer_profile
        selected_state = self.request.GET.get("state", "")

        summary, selected_fips = _serialize_service_areas(profile)

        context["states"] = US_STATE_CHOICES
        context["selected_state"] = selected_state
        context["summary"] = summary
        context["total_count"] = len(selected_fips)
        context["max_counties"] = MAX_SERVICE_COUNTIES
        context["selected_fips_json"] = json.dumps(selected_fips)
        return context


class ToggleServiceAreaAPIView(RoleRequiredMixin, View):
    allowed_roles = (User.Role.LABORER,)

    def post(self, request, fips):
        profile = request.user.laborer_profile
        county = get_object_or_404(County, fips=fips)
        existing = ServiceArea.objects.filter(laborer_profile=profile, county=county).first()

        if existing:
            existing.delete()
            status = "removed"
        else:
            current_count = ServiceArea.objects.filter(laborer_profile=profile).count()
            if current_count >= MAX_SERVICE_COUNTIES:
                summary, selected_fips = _serialize_service_areas(profile)
                return JsonResponse(
                    {
                        "status": "limit_reached",
                        "message": (
                            f"You can only select up to {MAX_SERVICE_COUNTIES} counties. "
                            "Remove one to add another."
                        ),
                        "total_count": len(selected_fips),
                        "selected_fips": selected_fips,
                        "summary": summary,
                    },
                    status=400,
                )
            ServiceArea.objects.create(laborer_profile=profile, county=county)
            status = "added"

        summary, selected_fips = _serialize_service_areas(profile)
        return JsonResponse(
            {
                "status": status,
                "fips": fips,
                "county_name": county.name,
                "state": county.state,
                "total_count": len(selected_fips),
                "max_counties": MAX_SERVICE_COUNTIES,
                "selected_fips": selected_fips,
                "summary": summary,
            }
        )


class MapView(LoginRequiredMixin, TemplateView):
    template_name = "coverage/map.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["states_json"] = json.dumps(dict(US_STATE_CHOICES))
        return context


class CountyLaborersAPIView(LoginRequiredMixin, View):
    def get(self, request, fips):
        county = get_object_or_404(County, fips=fips)
        laborers = LaborerProfile.objects.filter(service_areas__county=county).distinct()
        data = {
            "county_name": county.name,
            "state": county.state,
            "laborers": [
                {
                    "display_name": laborer.display_name or laborer.user.email,
                    "city": laborer.city,
                    "state": laborer.state,
                    "phone_number": laborer.phone_number,
                }
                for laborer in laborers
            ],
        }
        return JsonResponse(data)

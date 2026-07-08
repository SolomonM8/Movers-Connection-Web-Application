from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import TemplateView

from accounts.constants import US_STATE_CHOICES
from accounts.models import User
from accounts.views import RoleRequiredMixin

from .models import County, ServiceArea


class ServiceAreaView(RoleRequiredMixin, TemplateView):
    template_name = "coverage/service_areas.html"
    allowed_roles = (User.Role.LABORER,)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.request.user.laborer_profile
        selected_state = self.request.GET.get("state", "")

        served = (
            ServiceArea.objects.filter(laborer_profile=profile)
            .select_related("county")
            .order_by("county__state", "county__name")
        )
        summary = {}
        for service_area in served:
            summary.setdefault(service_area.county.state, []).append(service_area.county.name)

        context["states"] = US_STATE_CHOICES
        context["selected_state"] = selected_state
        context["summary"] = summary
        if selected_state:
            context["counties"] = County.objects.filter(state=selected_state)
            context["selected_fips"] = set(
                served.filter(county__state=selected_state).values_list("county_id", flat=True)
            )
        return context

    def post(self, request, *args, **kwargs):
        profile = request.user.laborer_profile
        state = request.POST.get("state", "")
        checked_fips = request.POST.getlist("counties")

        if state:
            ServiceArea.objects.filter(laborer_profile=profile, county__state=state).delete()
            counties = County.objects.filter(state=state, fips__in=checked_fips)
            ServiceArea.objects.bulk_create(
                ServiceArea(laborer_profile=profile, county=county) for county in counties
            )
            state_label = dict(US_STATE_CHOICES).get(state, state)
            messages.success(request, f"Updated your service counties for {state_label}.")

        return redirect(f"{reverse('coverage:service_areas')}?state={state}")

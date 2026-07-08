from django.contrib import messages
from django.db.models import F
from django.urls import reverse_lazy
from django.views.generic import CreateView

from accounts.models import DriverProfile, User
from accounts.views import RoleRequiredMixin

from .forms import JobForm


class JobCreateView(RoleRequiredMixin, CreateView):
    form_class = JobForm
    template_name = "jobs/job_form.html"
    allowed_roles = (User.Role.DRIVER,)
    success_url = reverse_lazy("accounts:dashboard")

    def form_valid(self, form):
        form.instance.driver_profile = self.request.user.driver_profile
        response = super().form_valid(form)
        DriverProfile.objects.filter(pk=self.request.user.driver_profile.pk).update(
            jobs_created_count=F("jobs_created_count") + 1
        )
        messages.success(self.request, "Your job has been posted.")
        return response

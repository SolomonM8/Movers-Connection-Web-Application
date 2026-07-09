from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from accounts.models import DriverProfile, User
from accounts.views import RoleRequiredMixin

from .forms import JobForm, MessageForm
from .models import Job, JobApplication


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


class DriverJobOwnerMixin(RoleRequiredMixin):
    allowed_roles = (User.Role.DRIVER,)

    def get_queryset(self):
        return Job.objects.filter(driver_profile=self.request.user.driver_profile)


class JobDetailView(DriverJobOwnerMixin, DetailView):
    model = Job
    template_name = "jobs/job_detail.html"
    context_object_name = "job"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["applications"] = self.object.applications.select_related(
            "laborer_profile", "laborer_profile__user"
        )
        return context


class JobUpdateView(DriverJobOwnerMixin, UpdateView):
    model = Job
    form_class = JobForm
    template_name = "jobs/job_form.html"

    def get_success_url(self):
        return reverse("jobs:detail", args=[self.object.pk])

    def form_valid(self, form):
        messages.success(self.request, "Job updated.")
        return super().form_valid(form)


class JobDeleteView(DriverJobOwnerMixin, View):
    def post(self, request, pk):
        job = get_object_or_404(Job, pk=pk, driver_profile=request.user.driver_profile)
        job.delete()
        messages.success(request, "Job deleted.")
        return redirect("accounts:dashboard")


class JobMarkCompleteView(DriverJobOwnerMixin, View):
    def post(self, request, pk):
        job = get_object_or_404(Job, pk=pk, driver_profile=request.user.driver_profile)
        if job.status != Job.Status.OPEN:
            messages.info(request, "This job is already marked completed.")
        else:
            job.status = Job.Status.COMPLETED
            job.save(update_fields=["status"])
            DriverProfile.objects.filter(pk=request.user.driver_profile.pk).update(
                jobs_completed_count=F("jobs_completed_count") + 1
            )
            messages.success(request, "Job marked as completed.")
        return redirect("jobs:detail", pk=pk)


class ApplicationRespondView(DriverJobOwnerMixin, View):
    def post(self, request, pk, app_pk):
        job = get_object_or_404(Job, pk=pk, driver_profile=request.user.driver_profile)
        application = get_object_or_404(JobApplication, pk=app_pk, job=job)
        action = request.POST.get("action")
        if action == "accept":
            application.status = JobApplication.Status.ACCEPTED
            application.responded_at = timezone.now()
            application.save(update_fields=["status", "responded_at"])
            messages.success(request, f"Accepted {application.laborer_profile}.")
        elif action == "decline":
            application.status = JobApplication.Status.DECLINED
            application.responded_at = timezone.now()
            application.save(update_fields=["status", "responded_at"])
            messages.success(request, f"Declined {application.laborer_profile}.")
        return redirect("jobs:detail", pk=pk)


class LaborerJobListView(RoleRequiredMixin, ListView):
    template_name = "jobs/job_browse.html"
    context_object_name = "jobs"
    allowed_roles = (User.Role.LABORER,)

    def get_queryset(self):
        profile = self.request.user.laborer_profile
        county_ids = profile.service_areas.values_list("county_id", flat=True)
        applied_job_ids = JobApplication.objects.filter(laborer_profile=profile).values_list(
            "job_id", flat=True
        )
        today = timezone.now().date()
        return (
            Job.objects.filter(
                Q(county_id__in=county_ids, status=Job.Status.OPEN, job_date__gte=today)
                | Q(id__in=applied_job_ids)
            )
            .select_related("county", "driver_profile")
            .distinct()
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.request.user.laborer_profile
        applications = JobApplication.objects.filter(laborer_profile=profile)
        application_by_job = {app.job_id: app for app in applications}
        jobs = list(context["jobs"])
        for job in jobs:
            job.my_application = application_by_job.get(job.id)
        context["jobs"] = jobs
        return context


class JobApplyView(RoleRequiredMixin, View):
    allowed_roles = (User.Role.LABORER,)

    def post(self, request, pk):
        job = get_object_or_404(Job, pk=pk, status=Job.Status.OPEN)
        profile = request.user.laborer_profile
        _, created = JobApplication.objects.get_or_create(job=job, laborer_profile=profile)
        if created:
            messages.success(request, "Application submitted.")
        else:
            messages.info(request, "You've already applied to this job.")
        return redirect("jobs:browse")


class MessageThreadView(LoginRequiredMixin, View):
    template_name = "jobs/message_thread.html"

    def get_application(self, request, app_pk):
        application = get_object_or_404(
            JobApplication.objects.select_related(
                "job", "job__driver_profile__user", "laborer_profile__user"
            ),
            pk=app_pk,
            status=JobApplication.Status.ACCEPTED,
        )
        user = request.user
        is_driver = application.job.driver_profile.user_id == user.id
        is_laborer = application.laborer_profile.user_id == user.id
        if not (is_driver or is_laborer or user.is_superuser):
            raise Http404
        return application

    def get(self, request, app_pk):
        application = self.get_application(request, app_pk)
        form = MessageForm()
        thread = application.messages.select_related("sender")
        return render(
            request, self.template_name, {"application": application, "form": form, "thread": thread}
        )

    def post(self, request, app_pk):
        application = self.get_application(request, app_pk)
        form = MessageForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.application = application
            message.sender = request.user
            message.save()
            return redirect("jobs:messages", app_pk=app_pk)
        thread = application.messages.select_related("sender")
        return render(
            request, self.template_name, {"application": application, "form": form, "thread": thread}
        )

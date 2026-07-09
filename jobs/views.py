from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from accounts.models import Connection, DriverProfile, LaborerProfile, Notification, User
from accounts.views import RoleRequiredMixin

from .forms import JobForm, MessageForm
from .models import Job, JobApplication


class JobCreateView(RoleRequiredMixin, CreateView):
    form_class = JobForm
    template_name = "jobs/job_form.html"
    allowed_roles = (User.Role.DRIVER,)
    success_url = reverse_lazy("accounts:dashboard")

    def _active_job_count(self):
        profile = self.request.user.driver_profile
        today = timezone.now().date()
        return Job.objects.filter(
            driver_profile=profile, status=Job.Status.OPEN, job_date__gte=today
        ).count()

    def get(self, request, *args, **kwargs):
        if self._active_job_count() >= Job.MAX_ACTIVE_PER_DRIVER:
            messages.error(
                request,
                f"You can only have {Job.MAX_ACTIVE_PER_DRIVER} active jobs at a time. "
                "Complete or delete one before posting another.",
            )
            return redirect("accounts:dashboard")
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if self._active_job_count() >= Job.MAX_ACTIVE_PER_DRIVER:
            messages.error(
                request,
                f"You can only have {Job.MAX_ACTIVE_PER_DRIVER} active jobs at a time. "
                "Complete or delete one before posting another.",
            )
            return redirect("accounts:dashboard")
        return super().post(request, *args, **kwargs)

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
        context["can_mark_complete"] = self.object.job_date <= timezone.now().date()
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
        if job.status == Job.Status.COMPLETED:
            messages.error(request, "Completed jobs can't be deleted.")
            return redirect("jobs:detail", pk=pk)
        job.delete()
        messages.success(request, "Job deleted.")
        return redirect("accounts:dashboard")


class DriverPastJobListView(DriverJobOwnerMixin, ListView):
    template_name = "jobs/job_past.html"
    context_object_name = "jobs"

    def get_queryset(self):
        today = timezone.now().date()
        return (
            Job.objects.filter(driver_profile=self.request.user.driver_profile)
            .filter(Q(job_date__lt=today) | Q(status=Job.Status.COMPLETED))
            .select_related("county")
        )


class JobMarkCompleteView(DriverJobOwnerMixin, View):
    def post(self, request, pk):
        job = get_object_or_404(Job, pk=pk, driver_profile=request.user.driver_profile)
        if job.status != Job.Status.OPEN:
            messages.info(request, "This job is already marked completed.")
        elif job.job_date > timezone.now().date():
            messages.error(request, "You can't mark a job completed before its date arrives.")
        else:
            job.status = Job.Status.COMPLETED
            job.save(update_fields=["status"])
            messages.success(request, "Job marked as completed.")
        return redirect("jobs:detail", pk=pk)


class ApplicationRespondView(DriverJobOwnerMixin, View):
    def post(self, request, pk, app_pk):
        job = get_object_or_404(Job, pk=pk, driver_profile=request.user.driver_profile)
        application = get_object_or_404(
            JobApplication, pk=app_pk, job=job, source=JobApplication.Source.APPLIED
        )
        action = request.POST.get("action")
        if action == "accept":
            application.status = JobApplication.Status.ACCEPTED
            application.responded_at = timezone.now()
            application.save(update_fields=["status", "responded_at"])
            Notification.objects.create(
                recipient=application.laborer_profile.user,
                message=(
                    f"You were accepted for the {job.get_job_type_display()} job on "
                    f"{job.job_date} in {job.county}."
                ),
                url=reverse("jobs:messages", args=[application.pk]),
            )
            messages.success(request, f"Accepted {application.laborer_profile}.")
        elif action == "decline":
            application.status = JobApplication.Status.DECLINED
            application.responded_at = timezone.now()
            application.save(update_fields=["status", "responded_at"])
            Notification.objects.create(
                recipient=application.laborer_profile.user,
                message=(
                    f"Your application for the {job.get_job_type_display()} job on "
                    f"{job.job_date} in {job.county} was declined."
                ),
                url=reverse("jobs:browse"),
            )
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
        context["my_friend_driver_ids"] = set(
            Connection.objects.filter(laborer_profile=profile).values_list(
                "driver_profile_id", flat=True
            )
        )
        context["invitations"] = JobApplication.objects.filter(
            laborer_profile=profile,
            source=JobApplication.Source.INVITED,
            status=JobApplication.Status.PENDING,
        ).select_related("job", "job__county", "job__driver_profile", "job__driver_profile__user")
        return context


class InvitationRespondView(RoleRequiredMixin, View):
    allowed_roles = (User.Role.LABORER,)

    def post(self, request, app_pk):
        application = get_object_or_404(
            JobApplication,
            pk=app_pk,
            laborer_profile=request.user.laborer_profile,
            source=JobApplication.Source.INVITED,
        )
        job = application.job
        action = request.POST.get("action")
        if action == "accept":
            application.status = JobApplication.Status.ACCEPTED
            application.responded_at = timezone.now()
            application.save(update_fields=["status", "responded_at"])
            Notification.objects.create(
                recipient=job.driver_profile.user,
                message=(
                    f"{application.laborer_profile} accepted your invite for the "
                    f"{job.get_job_type_display()} job on {job.job_date} in {job.county}."
                ),
                url=reverse("jobs:messages", args=[application.pk]),
            )
            messages.success(request, "Invitation accepted!")
        elif action == "decline":
            application.status = JobApplication.Status.DECLINED
            application.responded_at = timezone.now()
            application.save(update_fields=["status", "responded_at"])
            Notification.objects.create(
                recipient=job.driver_profile.user,
                message=(
                    f"{application.laborer_profile} declined your invite for the "
                    f"{job.get_job_type_display()} job on {job.job_date} in {job.county}."
                ),
                url=reverse("jobs:detail", args=[job.pk]),
            )
            messages.success(request, "Invitation declined.")
        return redirect("jobs:browse")


class JobApplyView(RoleRequiredMixin, View):
    allowed_roles = (User.Role.LABORER,)

    def post(self, request, pk):
        job = get_object_or_404(Job, pk=pk, status=Job.Status.OPEN)
        profile = request.user.laborer_profile
        _, created = JobApplication.objects.get_or_create(job=job, laborer_profile=profile)
        if created:
            Notification.objects.create(
                recipient=job.driver_profile.user,
                message=(
                    f"{profile} applied to your {job.get_job_type_display()} job on "
                    f"{job.job_date} in {job.county}."
                ),
                url=reverse("jobs:detail", args=[job.pk]),
            )
            messages.success(request, "Application submitted.")
        else:
            messages.info(request, "You've already applied to this job.")
        return redirect("jobs:browse")


class JobInviteView(RoleRequiredMixin, View):
    allowed_roles = (User.Role.DRIVER,)
    template_name = "jobs/job_invite.html"

    def get_active_jobs(self, request):
        today = timezone.now().date()
        return Job.objects.filter(
            driver_profile=request.user.driver_profile, status=Job.Status.OPEN, job_date__gte=today
        ).select_related("county")

    def get(self, request, laborer_pk):
        laborer_profile = get_object_or_404(LaborerProfile, pk=laborer_pk)
        jobs = self.get_active_jobs(request)
        return render(
            request, self.template_name, {"laborer_profile": laborer_profile, "jobs": jobs}
        )

    def post(self, request, laborer_pk):
        laborer_profile = get_object_or_404(LaborerProfile, pk=laborer_pk)
        jobs = self.get_active_jobs(request)
        job = jobs.filter(pk=request.POST.get("job")).first()
        if not job:
            messages.error(request, "Please select a valid job to invite this laborer to.")
            return redirect("jobs:invite", laborer_pk=laborer_pk)
        application, created = JobApplication.objects.get_or_create(
            job=job,
            laborer_profile=laborer_profile,
            defaults={"source": JobApplication.Source.INVITED},
        )
        if created:
            Notification.objects.create(
                recipient=laborer_profile.user,
                message=(
                    f"You were invited to a {job.get_job_type_display()} job on "
                    f"{job.job_date} in {job.county} by {request.user.driver_profile}."
                ),
                url=reverse("jobs:browse"),
            )
            messages.success(request, f"Invited {laborer_profile} to the job.")
        else:
            messages.info(request, f"{laborer_profile} already has a pending application for that job.")
        return redirect("jobs:detail", pk=job.pk)


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

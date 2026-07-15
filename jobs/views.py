import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, F, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.html import format_html
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from accounts.constants import US_STATE_CHOICES
from accounts.models import Connection, DriverProfile, LaborerProfile, Notification, User
from accounts.templatetags.avatar_tags import compute_avatar_color, compute_avatar_initial
from accounts.views import RoleRequiredMixin

from .forms import ConversationMessageForm, JobForm, JobRatingForm
from .models import (
    Conversation,
    ConversationMessage,
    Job,
    JobApplication,
    JobRating,
    unrated_eligible_applications,
)


def get_or_create_conversation(driver_profile, laborer_profile):
    conversation, _ = Conversation.objects.get_or_create(
        driver_profile=driver_profile, laborer_profile=laborer_profile
    )
    return conversation


def add_system_message(conversation, body):
    ConversationMessage.objects.create(conversation=conversation, is_system=True, body=body)


def notify_new_message(recipient, sender_display, url):
    Notification.objects.create(
        recipient=recipient, message=f"New message from {sender_display}.", url=url
    )


def message_cta_html(other_profile):
    return format_html(
        ' <button type="button" class="btn-secondary btn-inline" data-open-conversation="{}">Message them &rarr;</button>',
        other_profile.pk,
    )


class JobFormContextMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["states_json"] = json.dumps(US_STATE_CHOICES)
        job = getattr(self, "object", None)
        if job and job.county_id:
            context["initial_county_json"] = json.dumps(
                {"fips": job.county_id, "name": job.county.name, "state": job.county.state}
            )
        else:
            context["initial_county_json"] = "null"
        return context


class JobCreateView(JobFormContextMixin, RoleRequiredMixin, CreateView):
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

    def _has_unrated_eligible_applications(self):
        return unrated_eligible_applications(self.request.user.driver_profile).exists()

    def get(self, request, *args, **kwargs):
        if self._active_job_count() >= Job.MAX_ACTIVE_PER_DRIVER:
            messages.error(
                request,
                f"You can only have {Job.MAX_ACTIVE_PER_DRIVER} active jobs at a time. "
                "Complete or delete one before posting another.",
            )
            return redirect("accounts:dashboard")
        if self._has_unrated_eligible_applications():
            messages.error(
                request,
                "You have jobs awaiting a rating. Rate your past laborers from your dashboard "
                "before posting a new job.",
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
        if self._has_unrated_eligible_applications():
            messages.error(
                request,
                "You have jobs awaiting a rating. Rate your past laborers from your dashboard "
                "before posting a new job.",
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


class JobDetailView(LoginRequiredMixin, DetailView):
    model = Job
    template_name = "jobs/job_detail.html"
    context_object_name = "job"

    def get_queryset(self):
        return Job.objects.select_related("county", "driver_profile", "driver_profile__user")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        job = self.object
        user = self.request.user
        is_owner = (
            user.role == User.Role.DRIVER
            and hasattr(user, "driver_profile")
            and job.driver_profile_id == user.driver_profile.pk
        )
        context["is_owner"] = is_owner
        if is_owner:
            context["applications"] = job.applications.select_related(
                "laborer_profile", "laborer_profile__user"
            )
            context["can_mark_complete"] = job.job_date <= timezone.now().date()
        elif user.role == User.Role.LABORER and hasattr(user, "laborer_profile"):
            context["my_application"] = job.applications.filter(
                laborer_profile=user.laborer_profile
            ).first()
        return context


class JobUpdateView(JobFormContextMixin, DriverJobOwnerMixin, UpdateView):
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


def driver_past_jobs_queryset(driver_profile):
    today = timezone.now().date()
    return (
        Job.objects.filter(driver_profile=driver_profile)
        .filter(Q(job_date__lt=today) | Q(status=Job.Status.COMPLETED))
        .select_related("county")
    )


def laborer_past_jobs_queryset(laborer_profile):
    today = timezone.now().date()
    return (
        Job.objects.filter(
            applications__laborer_profile=laborer_profile,
            applications__status=JobApplication.Status.ACCEPTED,
        )
        .filter(Q(job_date__lt=today) | Q(status=Job.Status.COMPLETED))
        .select_related("county", "driver_profile")
        .distinct()
    )


def job_hub_redirect(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    if request.user.role == User.Role.DRIVER:
        return redirect("jobs:driver_hub")
    if request.user.role == User.Role.LABORER:
        return redirect("jobs:browse")
    return redirect("accounts:dashboard")


class DriverPastJobListView(DriverJobOwnerMixin, ListView):
    template_name = "jobs/job_past.html"
    context_object_name = "jobs"

    def get_queryset(self):
        return driver_past_jobs_queryset(self.request.user.driver_profile)


class DriverJobHubView(DriverJobOwnerMixin, TemplateView):
    template_name = "jobs/job_hub_driver.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.request.user.driver_profile
        today = timezone.now().date()
        context["profile"] = profile
        context["active_jobs"] = (
            profile.jobs.filter(status=Job.Status.OPEN, job_date__gte=today)
            .select_related("county")
            .annotate(application_count=Count("applications"))
        )
        context["past_jobs"] = driver_past_jobs_queryset(profile)
        context["completed_jobs_count"] = profile.jobs.filter(status=Job.Status.COMPLETED).count()
        return context


class LaborerPastJobListView(RoleRequiredMixin, ListView):
    template_name = "jobs/job_past_laborer.html"
    context_object_name = "jobs"
    allowed_roles = (User.Role.LABORER,)

    def get_queryset(self):
        return laborer_past_jobs_queryset(self.request.user.laborer_profile)

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


class JobMarkCompleteView(DriverJobOwnerMixin, View):
    def post(self, request, pk):
        job = get_object_or_404(Job, pk=pk, driver_profile=request.user.driver_profile)
        if job.status != Job.Status.OPEN:
            messages.info(request, "This job is already marked completed.")
            return redirect("jobs:detail", pk=pk)
        if job.job_date > timezone.now().date():
            messages.error(request, "You can't mark a job completed before its date arrives.")
            return redirect("jobs:detail", pk=pk)

        job.status = Job.Status.COMPLETED
        job.save(update_fields=["status"])
        messages.success(request, "Job marked as completed.")

        unrated = job.applications.filter(status=JobApplication.Status.ACCEPTED, rating__isnull=True)
        count = unrated.count()
        if count == 1:
            return redirect("jobs:rate_application", app_pk=unrated.first().pk)
        if count > 1:
            return redirect("jobs:rating_index", pk=job.pk)
        return redirect("jobs:detail", pk=pk)


class JobRatingIndexView(DriverJobOwnerMixin, DetailView):
    model = Job
    template_name = "jobs/job_rating_index.html"
    context_object_name = "job"

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.is_rating_eligible:
            messages.error(request, "This job isn't eligible for rating yet.")
            return redirect("jobs:detail", pk=self.object.pk)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["unrated_applications"] = self.object.applications.filter(
            status=JobApplication.Status.ACCEPTED, rating__isnull=True
        ).select_related("laborer_profile", "laborer_profile__user")
        return context


class JobRatingCreateView(RoleRequiredMixin, CreateView):
    form_class = JobRatingForm
    template_name = "jobs/job_rating_form.html"
    allowed_roles = (User.Role.DRIVER,)

    def dispatch(self, request, *args, **kwargs):
        self.application = get_object_or_404(
            JobApplication.objects.select_related(
                "job", "laborer_profile", "laborer_profile__user"
            ),
            pk=kwargs["app_pk"],
            job__driver_profile=getattr(request.user, "driver_profile", None),
            status=JobApplication.Status.ACCEPTED,
        )
        self.job = self.application.job
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        if not self.job.is_rating_eligible:
            messages.error(request, "This job isn't eligible for rating yet.")
            return redirect("jobs:detail", pk=self.job.pk)
        if hasattr(self.application, "rating"):
            messages.info(request, "You've already rated this laborer for this job.")
            return redirect("jobs:detail", pk=self.job.pk)
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if not self.job.is_rating_eligible or hasattr(self.application, "rating"):
            return redirect("jobs:detail", pk=self.job.pk)
        return super().post(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["job"] = self.job
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["application"] = self.application
        context["job"] = self.job
        return context

    def form_valid(self, form):
        form.instance.application = self.application
        response = super().form_valid(form)
        messages.success(self.request, f"Rating submitted for {self.application.laborer_profile}.")
        return response

    def get_success_url(self):
        remaining = self.job.applications.filter(
            status=JobApplication.Status.ACCEPTED, rating__isnull=True
        ).exclude(pk=self.application.pk)
        if remaining.exists():
            return reverse("jobs:rating_index", args=[self.job.pk])
        return reverse("jobs:detail", args=[self.job.pk])


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
            conversation = get_or_create_conversation(job.driver_profile, application.laborer_profile)
            add_system_message(
                conversation,
                f"Job accepted: {job.get_job_type_display()} on {job.job_date} in {job.county}.",
            )
            Notification.objects.create(
                recipient=application.laborer_profile.user,
                message=(
                    f"You were accepted for the {job.get_job_type_display()} job on "
                    f"{job.job_date} in {job.county}."
                ),
                url=reverse("accounts:dashboard") + f"?open_chat={conversation.pk}",
            )
            messages.success(
                request,
                format_html(
                    "Accepted {}.{}",
                    application.laborer_profile,
                    message_cta_html(application.laborer_profile),
                ),
            )
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
        connections = Connection.objects.filter(laborer_profile=profile)
        my_friend_status = {
            c.driver_profile_id: c.status
            for c in connections.only("driver_profile_id", "status")
        }
        jobs = list(context["jobs"])
        for job in jobs:
            job.my_application = application_by_job.get(job.id)
            job.driver_friend_status = my_friend_status.get(job.driver_profile_id, "none")
        context["jobs"] = jobs
        context["invitations"] = JobApplication.objects.filter(
            laborer_profile=profile,
            source=JobApplication.Source.INVITED,
            status=JobApplication.Status.PENDING,
        ).select_related("job", "job__county", "job__driver_profile", "job__driver_profile__user")
        context["completed_jobs_count"] = JobApplication.objects.filter(
            laborer_profile=profile, status=JobApplication.Status.ACCEPTED, job__status=Job.Status.COMPLETED
        ).count()
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
            conversation = get_or_create_conversation(job.driver_profile, application.laborer_profile)
            add_system_message(
                conversation,
                f"Invite accepted: {job.get_job_type_display()} on {job.job_date} in {job.county}.",
            )
            Notification.objects.create(
                recipient=job.driver_profile.user,
                message=(
                    f"{application.laborer_profile} accepted your invite for the "
                    f"{job.get_job_type_display()} job on {job.job_date} in {job.county}."
                ),
                url=reverse("accounts:dashboard") + f"?open_chat={conversation.pk}",
            )
            messages.success(
                request,
                format_html(
                    "Invitation accepted!{}",
                    message_cta_html(job.driver_profile),
                ),
            )
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
            conversation = get_or_create_conversation(request.user.driver_profile, laborer_profile)
            add_system_message(
                conversation,
                f"New job invite: {job.get_job_type_display()} on {job.job_date} in {job.county}.",
            )
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


def get_conversation_for_user(request, conversation_pk):
    conversation = get_object_or_404(
        Conversation.objects.select_related("driver_profile__user", "laborer_profile__user"),
        pk=conversation_pk,
    )
    user = request.user
    is_driver = conversation.driver_profile.user_id == user.id
    is_laborer = conversation.laborer_profile.user_id == user.id
    if not (is_driver or is_laborer or user.is_superuser):
        raise Http404
    return conversation


def serialize_conversation_message(message, request_user):
    return {
        "id": message.pk,
        "is_system": message.is_system,
        "is_self": bool(message.sender_id) and message.sender_id == request_user.id,
        "sender_email": message.sender.email if message.sender else None,
        "body": message.body,
        "created_at": message.created_at.isoformat(),
    }


def serialize_conversation_row(conversation, other_profile, other_name, is_friend, job_id, last_message, unread_count):
    timestamp = last_message.created_at if last_message else conversation.created_at
    return {
        "id": conversation.pk,
        "other_name": other_name,
        "avatar_url": other_profile.profile_picture.url if other_profile.profile_picture else None,
        "avatar_color": compute_avatar_color(other_profile.pk),
        "avatar_initial": compute_avatar_initial(other_name),
        "is_friend": is_friend,
        "has_job": bool(job_id),
        "job_id": job_id,
        "last_message": last_message.body if last_message else None,
        "last_message_at": timestamp.isoformat(),
        "unread_count": unread_count,
    }


def active_job_id_for_pair(driver_profile, laborer_profile):
    today = timezone.now().date()
    application = (
        JobApplication.objects.filter(
            job__driver_profile=driver_profile,
            laborer_profile=laborer_profile,
            status=JobApplication.Status.ACCEPTED,
            job__status=Job.Status.OPEN,
            job__job_date__gte=today,
        )
        .order_by("job__job_date")
        .first()
    )
    return application.job_id if application else None


def markable_job_id_for_pair(driver_profile, laborer_profile):
    """A job between this pair that's open and eligible to be marked completed right now
    (mirrors JobMarkCompleteView's own gate) — deliberately separate from
    active_job_id_for_pair, which is scoped to *upcoming* jobs for the JOB badge."""
    application = (
        JobApplication.objects.filter(
            job__driver_profile=driver_profile,
            laborer_profile=laborer_profile,
            status=JobApplication.Status.ACCEPTED,
            job__status=Job.Status.OPEN,
            job__job_date__lte=timezone.now().date(),
        )
        .order_by("job__job_date")
        .first()
    )
    return application.job_id if application else None


class MessageUnreadCountAPIView(LoginRequiredMixin, View):
    def get(self, request):
        user = request.user
        count = (
            ConversationMessage.objects.filter(
                Q(conversation__driver_profile__user=user) | Q(conversation__laborer_profile__user=user)
            )
            .exclude(sender=user)
            .filter(is_read=False)
            .count()
        )
        return JsonResponse({"count": count})


class ConversationListAPIView(LoginRequiredMixin, View):
    def get(self, request):
        user = request.user
        today = timezone.now().date()
        rows = []

        if user.role == User.Role.DRIVER and hasattr(user, "driver_profile"):
            profile = user.driver_profile
            conversations_qs = Conversation.objects.filter(driver_profile=profile).select_related(
                "laborer_profile", "laborer_profile__user"
            )
            friend_ids = set(
                Connection.objects.filter(
                    driver_profile=profile, status=Connection.Status.ACCEPTED
                ).values_list("laborer_profile_id", flat=True)
            )
            job_id_by_other_profile = {}
            for laborer_id, job_id in (
                JobApplication.objects.filter(
                    job__driver_profile=profile,
                    status=JobApplication.Status.ACCEPTED,
                    job__status=Job.Status.OPEN,
                    job__job_date__gte=today,
                )
                .order_by("job__job_date")
                .values_list("laborer_profile_id", "job_id")
            ):
                job_id_by_other_profile.setdefault(laborer_id, job_id)
            for conversation in conversations_qs:
                other_profile = conversation.laborer_profile
                other_name = other_profile.display_name or other_profile.user.email
                last_message = conversation.messages.order_by("-created_at").first()
                unread = conversation.messages.filter(is_read=False).exclude(sender=user).count()
                rows.append(
                    serialize_conversation_row(
                        conversation,
                        other_profile,
                        other_name,
                        other_profile.pk in friend_ids,
                        job_id_by_other_profile.get(other_profile.pk),
                        last_message,
                        unread,
                    )
                )
        elif user.role == User.Role.LABORER and hasattr(user, "laborer_profile"):
            profile = user.laborer_profile
            conversations_qs = Conversation.objects.filter(laborer_profile=profile).select_related(
                "driver_profile", "driver_profile__user"
            )
            friend_ids = set(
                Connection.objects.filter(
                    laborer_profile=profile, status=Connection.Status.ACCEPTED
                ).values_list("driver_profile_id", flat=True)
            )
            job_id_by_other_profile = {}
            for driver_id, job_id in (
                JobApplication.objects.filter(
                    laborer_profile=profile,
                    status=JobApplication.Status.ACCEPTED,
                    job__status=Job.Status.OPEN,
                    job__job_date__gte=today,
                )
                .order_by("job__job_date")
                .values_list("job__driver_profile_id", "job_id")
            ):
                job_id_by_other_profile.setdefault(driver_id, job_id)
            for conversation in conversations_qs:
                other_profile = conversation.driver_profile
                other_name = other_profile.company_name or other_profile.user.email
                last_message = conversation.messages.order_by("-created_at").first()
                unread = conversation.messages.filter(is_read=False).exclude(sender=user).count()
                rows.append(
                    serialize_conversation_row(
                        conversation,
                        other_profile,
                        other_name,
                        other_profile.pk in friend_ids,
                        job_id_by_other_profile.get(other_profile.pk),
                        last_message,
                        unread,
                    )
                )

        rows.sort(key=lambda c: c["last_message_at"], reverse=True)
        return JsonResponse({"conversations": rows})


class FriendSearchAPIView(LoginRequiredMixin, View):
    def get(self, request):
        user = request.user
        query = request.GET.get("q", "").strip().lower()
        results = []
        if query:
            if user.role == User.Role.DRIVER and hasattr(user, "driver_profile"):
                connections = Connection.objects.filter(
                    driver_profile=user.driver_profile, status=Connection.Status.ACCEPTED
                ).select_related("laborer_profile", "laborer_profile__user")
                for connection in connections:
                    profile = connection.laborer_profile
                    name = profile.display_name or profile.user.email
                    if query in name.lower():
                        results.append(
                            {
                                "other_profile_id": profile.pk,
                                "other_name": name,
                                "avatar_url": profile.profile_picture.url if profile.profile_picture else None,
                                "avatar_color": compute_avatar_color(profile.pk),
                                "avatar_initial": compute_avatar_initial(name),
                            }
                        )
            elif user.role == User.Role.LABORER and hasattr(user, "laborer_profile"):
                connections = Connection.objects.filter(
                    laborer_profile=user.laborer_profile, status=Connection.Status.ACCEPTED
                ).select_related("driver_profile", "driver_profile__user")
                for connection in connections:
                    profile = connection.driver_profile
                    name = profile.company_name or profile.user.email
                    if query in name.lower():
                        results.append(
                            {
                                "other_profile_id": profile.pk,
                                "other_name": name,
                                "avatar_url": profile.profile_picture.url if profile.profile_picture else None,
                                "avatar_color": compute_avatar_color(profile.pk),
                                "avatar_initial": compute_avatar_initial(name),
                            }
                        )
        return JsonResponse({"results": results[:10]})


class ConversationStartAPIView(LoginRequiredMixin, View):
    def post(self, request):
        user = request.user
        other_profile_id = request.POST.get("other_profile_id")
        if not other_profile_id:
            return JsonResponse({"error": "other_profile_id is required"}, status=400)
        if user.role == User.Role.DRIVER and hasattr(user, "driver_profile"):
            other_profile = get_object_or_404(LaborerProfile, pk=other_profile_id)
            conversation = get_or_create_conversation(user.driver_profile, other_profile)
            other_name = other_profile.display_name or other_profile.user.email
            job_id = markable_job_id_for_pair(user.driver_profile, other_profile)
        elif user.role == User.Role.LABORER and hasattr(user, "laborer_profile"):
            other_profile = get_object_or_404(DriverProfile, pk=other_profile_id)
            conversation = get_or_create_conversation(other_profile, user.laborer_profile)
            other_name = other_profile.company_name or other_profile.user.email
            job_id = markable_job_id_for_pair(other_profile, user.laborer_profile)
        else:
            raise Http404
        return JsonResponse(
            {
                "id": conversation.pk,
                "other_name": other_name,
                "avatar_url": other_profile.profile_picture.url if other_profile.profile_picture else None,
                "avatar_color": compute_avatar_color(other_profile.pk),
                "avatar_initial": compute_avatar_initial(other_name),
                "job_id": job_id,
            }
        )


class ConversationThreadAPIView(LoginRequiredMixin, View):
    def get(self, request, conversation_pk):
        conversation = get_conversation_for_user(request, conversation_pk)
        conversation.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
        thread = conversation.messages.select_related("sender")
        job_id = markable_job_id_for_pair(conversation.driver_profile, conversation.laborer_profile)
        return JsonResponse(
            {
                "messages": [serialize_conversation_message(m, request.user) for m in thread],
                "job_id": job_id,
            }
        )

    def post(self, request, conversation_pk):
        conversation = get_conversation_for_user(request, conversation_pk)
        form = ConversationMessageForm(request.POST)
        if not form.is_valid():
            return JsonResponse({"errors": form.errors}, status=400)
        message = form.save(commit=False)
        message.conversation = conversation
        message.sender = request.user
        message.save()
        is_sender_driver = conversation.driver_profile.user_id == request.user.id
        recipient = (
            conversation.laborer_profile.user if is_sender_driver else conversation.driver_profile.user
        )
        sender_display = (
            str(conversation.driver_profile) if is_sender_driver else str(conversation.laborer_profile)
        )
        notify_new_message(
            recipient, sender_display, reverse("accounts:dashboard") + f"?open_chat={conversation.pk}"
        )
        return JsonResponse({"message": serialize_conversation_message(message, request.user)})

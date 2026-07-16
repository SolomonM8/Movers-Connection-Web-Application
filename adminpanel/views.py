from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView

from accounts.models import Connection, LaborerProfile, Notification, User
from accounts.views import RoleRequiredMixin
from jobs.models import Job, JobApplication
from jobs.views import add_system_message, get_or_create_conversation

from .forms import BanUserForm, BugReportForm, ReportForm, SupportMessageForm
from .models import BugReport, Report, SupportMessage, SupportThread


class AdminRequiredMixin(RoleRequiredMixin):
    allowed_roles = (User.Role.ADMIN,)


def admin_stats():
    return {
        "driver_count": User.objects.filter(role=User.Role.DRIVER).count(),
        "laborer_count": User.objects.filter(role=User.Role.LABORER).count(),
        "open_jobs_count": Job.objects.filter(status=Job.Status.OPEN).count(),
        "completed_jobs_count": Job.objects.filter(status=Job.Status.COMPLETED).count(),
        "connection_count": Connection.objects.filter(status=Connection.Status.ACCEPTED).count(),
        "open_reports_count": Report.objects.filter(status=Report.Status.OPEN).count(),
        "open_bug_reports_count": BugReport.objects.filter(status=BugReport.Status.OPEN).count(),
    }


class UserListView(AdminRequiredMixin, ListView):
    template_name = "adminpanel/user_list.html"
    context_object_name = "user_list"
    paginate_by = 50

    def get_queryset(self):
        qs = User.objects.order_by("-date_joined")
        role = self.request.GET.get("role")
        if role in (User.Role.DRIVER, User.Role.LABORER, User.Role.ADMIN):
            qs = qs.filter(role=role)
        if self.request.GET.get("banned") == "1":
            qs = qs.filter(is_banned=True)
        search = self.request.GET.get("q", "").strip()
        if search:
            qs = qs.filter(email__icontains=search)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["role_filter"] = self.request.GET.get("role", "")
        context["banned_filter"] = self.request.GET.get("banned", "")
        context["search"] = self.request.GET.get("q", "")
        return context


class UserDetailView(AdminRequiredMixin, DetailView):
    model = User
    pk_url_kwarg = "user_pk"
    template_name = "adminpanel/user_detail.html"
    context_object_name = "target_user"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        target = self.object
        if target.role == User.Role.DRIVER and hasattr(target, "driver_profile"):
            context["profile"] = target.driver_profile
            context["jobs_count"] = target.driver_profile.jobs.count()
        elif target.role == User.Role.LABORER and hasattr(target, "laborer_profile"):
            context["profile"] = target.laborer_profile
            context["jobs_count"] = target.laborer_profile.job_applications.filter(
                status=JobApplication.Status.ACCEPTED
            ).count()
        context["reports_received"] = target.reports_received.select_related("reporter").all()
        context["reports_filed"] = target.reports_filed.select_related("reported_user").all()
        context["ban_form"] = BanUserForm()
        return context


class BanUserView(AdminRequiredMixin, View):
    def post(self, request, user_pk):
        target = get_object_or_404(User, pk=user_pk)
        if request.POST.get("action") == "unban":
            target.is_banned = False
            target.ban_reason = ""
            target.banned_at = None
            target.is_active = True
            target.save(update_fields=["is_banned", "ban_reason", "banned_at", "is_active"])
            messages.success(request, f"{target.email} has been unbanned.")
        else:
            form = BanUserForm(request.POST)
            if form.is_valid():
                target.is_banned = True
                target.ban_reason = form.cleaned_data["ban_reason"]
                target.banned_at = timezone.now()
                target.is_active = False
                target.save(update_fields=["is_banned", "ban_reason", "banned_at", "is_active"])
                messages.success(request, f"{target.email} has been banned.")
            else:
                messages.error(request, "A ban reason is required.")
        return redirect("adminpanel:user_detail", user_pk=target.pk)


class JobListView(AdminRequiredMixin, ListView):
    template_name = "adminpanel/job_list.html"
    context_object_name = "job_list"
    paginate_by = 50

    def get_queryset(self):
        qs = Job.objects.select_related("county", "driver_profile", "driver_profile__user").order_by(
            "-job_date"
        )
        status = self.request.GET.get("status")
        if status in (Job.Status.OPEN, Job.Status.COMPLETED):
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_filter"] = self.request.GET.get("status", "")
        context["laborer_list"] = LaborerProfile.objects.select_related("user").order_by("display_name")
        return context


class JobForceCloseView(AdminRequiredMixin, View):
    def post(self, request, pk):
        job = get_object_or_404(Job, pk=pk)
        job.status = Job.Status.COMPLETED
        job.save(update_fields=["status"])
        messages.success(request, f"Job #{job.pk} marked as completed.")
        return redirect("adminpanel:job_list")


class JobAssignView(AdminRequiredMixin, View):
    def post(self, request, pk):
        job = get_object_or_404(Job, pk=pk)
        laborer_profile = get_object_or_404(LaborerProfile, pk=request.POST.get("laborer_pk"))
        application, created = JobApplication.objects.get_or_create(
            job=job,
            laborer_profile=laborer_profile,
            defaults={"source": JobApplication.Source.INVITED},
        )
        application.status = JobApplication.Status.ACCEPTED
        application.responded_at = timezone.now()
        application.save(update_fields=["status", "responded_at"])
        conversation = get_or_create_conversation(job.driver_profile, laborer_profile)
        add_system_message(
            conversation,
            f"{laborer_profile} was assigned to this job by an admin.",
            related_job=job,
        )
        Notification.objects.create(
            recipient=laborer_profile.user,
            message=(
                f"You were assigned to a {job.get_job_type_display()} job on "
                f"{job.job_date} in {job.county}."
            ),
            url=reverse("jobs:detail", args=[job.pk]),
        )
        Notification.objects.create(
            recipient=job.driver_profile.user,
            message=f"{laborer_profile} was assigned to your job by an admin.",
            url=reverse("jobs:detail", args=[job.pk]),
        )
        messages.success(request, f"{laborer_profile} assigned to job #{job.pk}.")
        return redirect("adminpanel:job_list")


class ReportListView(AdminRequiredMixin, ListView):
    template_name = "adminpanel/report_list.html"
    context_object_name = "report_list"
    paginate_by = 50

    def get_queryset(self):
        qs = Report.objects.select_related("reporter", "reported_user")
        status = self.request.GET.get("status")
        if status in Report.Status.values:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_filter"] = self.request.GET.get("status", "")
        context["status_choices"] = Report.Status.choices
        return context


class ReportUpdateStatusView(AdminRequiredMixin, View):
    def post(self, request, report_pk):
        report = get_object_or_404(Report, pk=report_pk)
        status = request.POST.get("status")
        if status in Report.Status.values:
            report.status = status
            report.admin_notes = request.POST.get("admin_notes", report.admin_notes)
            if status != Report.Status.OPEN and report.reviewed_at is None:
                report.reviewed_at = timezone.now()
            report.save(update_fields=["status", "admin_notes", "reviewed_at"])
            messages.success(request, "Report updated.")
        return redirect("adminpanel:report_list")


class BugReportListView(AdminRequiredMixin, ListView):
    template_name = "adminpanel/bug_report_list.html"
    context_object_name = "bug_report_list"
    paginate_by = 50

    def get_queryset(self):
        qs = BugReport.objects.select_related("reporter")
        status = self.request.GET.get("status")
        if status in BugReport.Status.values:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_filter"] = self.request.GET.get("status", "")
        context["status_choices"] = BugReport.Status.choices
        return context


class BugReportUpdateStatusView(AdminRequiredMixin, View):
    def post(self, request, bug_report_pk):
        bug_report = get_object_or_404(BugReport, pk=bug_report_pk)
        status = request.POST.get("status")
        if status in BugReport.Status.values:
            bug_report.status = status
            bug_report.save(update_fields=["status"])
            messages.success(request, "Bug report updated.")
        return redirect("adminpanel:bug_report_list")


class SupportInboxView(AdminRequiredMixin, ListView):
    template_name = "adminpanel/support_inbox.html"
    context_object_name = "thread_list"

    def get_queryset(self):
        threads = list(SupportThread.objects.select_related("user").prefetch_related("messages"))
        for thread in threads:
            all_messages = list(thread.messages.all())
            thread.unread_count = sum(
                1 for m in all_messages if not m.is_from_admin and not m.is_read_by_admin
            )
            thread.last_message = all_messages[-1] if all_messages else None
        threads.sort(
            key=lambda t: t.last_message.created_at if t.last_message else t.created_at, reverse=True
        )
        return threads


class SupportStartView(AdminRequiredMixin, View):
    def post(self, request, user_pk):
        target = get_object_or_404(User, pk=user_pk)
        thread, _ = SupportThread.objects.get_or_create(user=target)
        return redirect("adminpanel:support_thread", thread_pk=thread.pk)


class SupportThreadView(AdminRequiredMixin, DetailView):
    model = SupportThread
    pk_url_kwarg = "thread_pk"
    template_name = "adminpanel/support_thread.html"
    context_object_name = "thread"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        messages_qs = self.object.messages.select_related("sender")
        messages_qs.filter(is_from_admin=False, is_read_by_admin=False).update(is_read_by_admin=True)
        context["message_list"] = messages_qs
        return context

    def post(self, request, *args, **kwargs):
        thread = self.get_object()
        body = request.POST.get("body", "").strip()
        if body:
            SupportMessage.objects.create(
                thread=thread, sender=request.user, is_from_admin=True, body=body, is_read_by_admin=True
            )
        return redirect("adminpanel:support_thread", thread_pk=thread.pk)


# --- User-facing views (any logged-in user, not admin-only) ---


class ReportUserView(LoginRequiredMixin, View):
    template_name = "adminpanel/report_user_form.html"

    def get(self, request, user_pk):
        reported_user = get_object_or_404(User, pk=user_pk)
        if reported_user == request.user:
            messages.error(request, "You can't report yourself.")
            return redirect("accounts:dashboard")
        return render(
            request, self.template_name, {"reported_user": reported_user, "form": ReportForm()}
        )

    def post(self, request, user_pk):
        reported_user = get_object_or_404(User, pk=user_pk)
        if reported_user == request.user:
            messages.error(request, "You can't report yourself.")
            return redirect("accounts:dashboard")
        form = ReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.reporter = request.user
            report.reported_user = reported_user
            report.save()
            messages.success(request, "Thanks -- your report has been sent to our team.")
            if hasattr(reported_user, "driver_profile"):
                return redirect("accounts:driver_profile_detail", driver_pk=reported_user.driver_profile.pk)
            if hasattr(reported_user, "laborer_profile"):
                return redirect("accounts:laborer_profile_detail", laborer_pk=reported_user.laborer_profile.pk)
            return redirect("accounts:dashboard")
        return render(request, self.template_name, {"reported_user": reported_user, "form": form})


class BugReportSubmitView(LoginRequiredMixin, View):
    template_name = "adminpanel/bug_report_form.html"

    def get(self, request):
        initial = {"page_url": request.GET.get("from", "")}
        return render(request, self.template_name, {"form": BugReportForm(initial=initial)})

    def post(self, request):
        form = BugReportForm(request.POST)
        if form.is_valid():
            bug_report = form.save(commit=False)
            bug_report.reporter = request.user
            bug_report.save()
            messages.success(request, "Thanks for the report -- we'll take a look.")
            return redirect("accounts:dashboard")
        return render(request, self.template_name, {"form": form})


class UserSupportThreadView(LoginRequiredMixin, View):
    template_name = "adminpanel/user_support_thread.html"

    def get(self, request):
        thread = SupportThread.objects.filter(user=request.user).first()
        message_list = []
        if thread:
            message_list = thread.messages.select_related("sender")
            message_list.filter(is_from_admin=True, is_read_by_user=False).update(is_read_by_user=True)
        return render(
            request, self.template_name, {"thread": thread, "message_list": message_list, "form": SupportMessageForm()}
        )

    def post(self, request):
        body = request.POST.get("body", "").strip()
        if body:
            thread, _ = SupportThread.objects.get_or_create(user=request.user)
            SupportMessage.objects.create(
                thread=thread, sender=request.user, is_from_admin=False, body=body, is_read_by_user=True
            )
        return redirect("adminpanel:user_support_thread")

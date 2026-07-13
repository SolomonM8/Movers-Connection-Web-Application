from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.html import format_html
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from .forms import (
    DriverProfileEditForm,
    DriverSignUpForm,
    LaborerProfileEditForm,
    LaborerSignUpForm,
    NoAutofocusAuthenticationForm,
)
from .models import Connection, DeviceToken, DriverProfile, LaborerProfile, Notification, User


class LandingView(TemplateView):
    template_name = "accounts/landing.html"

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("accounts:dashboard")
        return super().get(request, *args, **kwargs)


class RoleChoiceView(TemplateView):
    template_name = "accounts/role_choice.html"


class CustomLoginView(LoginView):
    template_name = "accounts/login.html"
    form_class = NoAutofocusAuthenticationForm



class DriverSignUpView(CreateView):
    form_class = DriverSignUpForm
    template_name = "accounts/signup_form.html"
    success_url = reverse_lazy("accounts:dashboard")
    extra_context = {
        "role_label": "Driver / Moving Company",
        "role_icon": "includes/icon-truck.svg",
    }

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        messages.info(
            self.request,
            "Welcome! Head to the Coverage Map and search an address to find labor groups near your next job.",
        )
        return response


class LaborerSignUpView(CreateView):
    form_class = LaborerSignUpForm
    template_name = "accounts/signup_form.html"
    success_url = reverse_lazy("accounts:dashboard")
    extra_context = {
        "role_label": "Laborer / Labor Group",
        "role_icon": "includes/icon-hardhat.svg",
    }

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        messages.info(
            self.request,
            "Welcome! Your next step is to select the counties you serve.",
        )
        return response


def dashboard_redirect(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    if request.user.is_superuser or request.user.role == User.Role.ADMIN:
        target = "accounts:admin_dashboard"
    elif request.user.role == User.Role.DRIVER:
        target = "accounts:driver_dashboard"
    else:
        target = "accounts:laborer_dashboard"
    url = reverse(target)
    query_string = request.META.get("QUERY_STRING", "")
    if query_string:
        url = f"{url}?{query_string}"
    return redirect(url)


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    allowed_roles = ()

    def test_func(self):
        user = self.request.user
        if user.is_superuser:
            return True
        return user.role in self.allowed_roles


class DriverDashboardView(RoleRequiredMixin, TemplateView):
    template_name = "accounts/driver_dashboard.html"
    allowed_roles = (User.Role.DRIVER,)

    def get_context_data(self, **kwargs):
        from django.db.models import Count

        from jobs.models import Job, unrated_eligible_applications

        context = super().get_context_data(**kwargs)
        profile = self.request.user.driver_profile
        today = timezone.now().date()
        active_jobs = (
            profile.jobs.filter(status=Job.Status.OPEN, job_date__gte=today)
            .select_related("county")
            .annotate(application_count=Count("applications"))
        )
        context["profile"] = profile
        context["active_jobs"] = active_jobs
        context["completed_jobs_count"] = profile.jobs.filter(status=Job.Status.COMPLETED).count()
        context["unrated_applications"] = unrated_eligible_applications(profile).select_related(
            "job", "job__county", "laborer_profile", "laborer_profile__user"
        )
        return context


class LaborerDashboardView(RoleRequiredMixin, TemplateView):
    template_name = "accounts/laborer_dashboard.html"
    allowed_roles = (User.Role.LABORER,)

    def get_context_data(self, **kwargs):
        from jobs.models import rating_summary_for_laborer

        context = super().get_context_data(**kwargs)
        profile = self.request.user.laborer_profile
        areas = list(
            profile.service_areas.select_related("county").order_by(
                "-is_primary", "county__state", "county__name"
            )
        )
        context["profile"] = profile
        context["primary_area"] = next((area for area in areas if area.is_primary), None)
        context["other_areas"] = [area for area in areas if not area.is_primary]
        context["service_areas_count"] = len(areas)
        context["rating_summary"] = rating_summary_for_laborer(profile)
        context["equipment_checklist"] = _equipment_checklist(profile)
        return context


class LaborerProfileEditView(RoleRequiredMixin, UpdateView):
    form_class = LaborerProfileEditForm
    template_name = "accounts/laborer_profile_edit.html"
    allowed_roles = (User.Role.LABORER,)
    success_url = reverse_lazy("accounts:dashboard")

    def get_object(self, queryset=None):
        return self.request.user.laborer_profile

    def form_valid(self, form):
        messages.success(self.request, "Your account information has been updated.")
        return super().form_valid(form)


def _equipment_checklist(profile):
    return [
        ("Dolly", profile.has_dolly),
        ("Floor dolly", profile.has_floor_dolly),
        ("Tools", profile.has_tools),
        ("Drills", profile.has_drills),
        ("Shoulder dollies", profile.has_shoulder_dollies),
        ("Hump straps", profile.has_hump_straps),
    ]


class LaborerProfileDetailView(LoginRequiredMixin, DetailView):
    model = LaborerProfile
    pk_url_kwarg = "laborer_pk"
    template_name = "accounts/laborer_profile_detail.html"
    context_object_name = "profile"

    def get_context_data(self, **kwargs):
        from jobs.models import Job, JobApplication, rating_summary_for_laborer

        context = super().get_context_data(**kwargs)
        profile = self.object
        context["service_areas"] = profile.service_areas.select_related("county").order_by(
            "-is_primary", "county__state", "county__name"
        )
        context["completed_jobs_count"] = profile.job_applications.filter(
            status=JobApplication.Status.ACCEPTED, job__status=Job.Status.COMPLETED
        ).count()
        context["rating_summary"] = rating_summary_for_laborer(profile)
        context["equipment_checklist"] = _equipment_checklist(profile)
        return context


class DriverProfileEditView(RoleRequiredMixin, UpdateView):
    form_class = DriverProfileEditForm
    template_name = "accounts/driver_profile_edit.html"
    allowed_roles = (User.Role.DRIVER,)
    success_url = reverse_lazy("accounts:dashboard")

    def get_object(self, queryset=None):
        return self.request.user.driver_profile

    def form_valid(self, form):
        messages.success(self.request, "Your account information has been updated.")
        return super().form_valid(form)


class AccountDeleteView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/delete_account.html"

    def post(self, request, *args, **kwargs):
        password = request.POST.get("password", "")
        if not request.user.check_password(password):
            messages.error(request, "That password isn't right. Your account was not deleted.")
            return redirect("accounts:delete_account")

        user = request.user
        logout(request)
        user.delete()
        messages.success(request, "Your account has been permanently deleted.")
        return redirect("landing")


class AdminDashboardView(RoleRequiredMixin, TemplateView):
    template_name = "accounts/admin_dashboard.html"
    allowed_roles = (User.Role.ADMIN,)


class RegisterPushTokenView(LoginRequiredMixin, View):
    def post(self, request):
        token = request.POST.get("token", "").strip()
        platform = request.POST.get("platform", "android").strip() or "android"
        if not token:
            return JsonResponse({"status": "error", "message": "Missing token"}, status=400)
        DeviceToken.objects.update_or_create(
            token=token, defaults={"user": request.user, "platform": platform}
        )
        return JsonResponse({"status": "ok"})


class MarkTourSeenView(LoginRequiredMixin, View):
    def post(self, request):
        if not request.user.has_seen_tour:
            request.user.has_seen_tour = True
            request.user.save(update_fields=["has_seen_tour"])
        return JsonResponse({"status": "ok"})


class NotificationListView(LoginRequiredMixin, ListView):
    template_name = "accounts/notifications.html"
    context_object_name = "notification_list"

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).select_related(
            "related_connection"
        )[:30]

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return response


class NotificationMarkReadView(LoginRequiredMixin, View):
    def post(self, request):
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return JsonResponse({"status": "ok"})


class NotificationClearView(LoginRequiredMixin, View):
    def post(self, request):
        Notification.objects.filter(recipient=request.user).delete()
        if request.headers.get("X-Requested-With") == "fetch":
            return JsonResponse({"status": "ok"})
        messages.success(request, "Notifications cleared.")
        return redirect("accounts:notifications")


class FriendsListView(RoleRequiredMixin, TemplateView):
    template_name = "accounts/friends.html"
    allowed_roles = (User.Role.DRIVER, User.Role.LABORER)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        is_driver = user.role == User.Role.DRIVER
        context["is_driver"] = is_driver
        if is_driver:
            qs = Connection.objects.filter(driver_profile=user.driver_profile).select_related(
                "laborer_profile", "laborer_profile__user"
            )
        else:
            qs = Connection.objects.filter(laborer_profile=user.laborer_profile).select_related(
                "driver_profile", "driver_profile__user"
            )
        context["connections"] = qs.filter(status=Connection.Status.ACCEPTED)
        context["incoming_requests"] = qs.filter(status=Connection.Status.PENDING).exclude(
            requested_by=user
        )
        context["outgoing_requests"] = qs.filter(
            status=Connection.Status.PENDING, requested_by=user
        )
        return context


def _display_name_for_user(user):
    if hasattr(user, "driver_profile"):
        return str(user.driver_profile)
    if hasattr(user, "laborer_profile"):
        return str(user.laborer_profile)
    return user.email


def _profile_for_user(user):
    if hasattr(user, "driver_profile"):
        return user.driver_profile
    if hasattr(user, "laborer_profile"):
        return user.laborer_profile
    return None


def _start_friend_conversation(driver_profile, laborer_profile):
    from jobs.views import add_system_message, get_or_create_conversation

    conversation = get_or_create_conversation(driver_profile, laborer_profile)
    add_system_message(conversation, "You are now friends!")
    return conversation


def _open_chat_url(conversation):
    return reverse("accounts:dashboard") + f"?open_chat={conversation.pk}"


def _handle_friend_request(request, driver_profile, laborer_profile):
    connection = Connection.objects.filter(
        driver_profile=driver_profile, laborer_profile=laborer_profile
    ).first()
    other_user = (
        laborer_profile.user if request.user.id == driver_profile.user_id else driver_profile.user
    )
    other_profile = (
        laborer_profile if request.user.id == driver_profile.user_id else driver_profile
    )

    if connection is None:
        connection = Connection.objects.create(
            driver_profile=driver_profile,
            laborer_profile=laborer_profile,
            status=Connection.Status.PENDING,
            requested_by=request.user,
        )
        Notification.objects.create(
            recipient=other_user,
            message=f"{_display_name_for_user(request.user)} wants to be friends.",
            url=reverse("accounts:friends"),
            related_connection=connection,
        )
        messages.success(request, "Friend request sent.")
    elif connection.status == Connection.Status.ACCEPTED:
        messages.info(request, "You're already friends.")
    elif connection.requested_by_id == request.user.id:
        messages.info(request, "Request already sent — waiting on them to respond.")
    else:
        # They'd already requested us first; adding them back counts as accepting.
        from jobs.views import message_cta_html

        connection.status = Connection.Status.ACCEPTED
        connection.responded_at = timezone.now()
        connection.save(update_fields=["status", "responded_at"])
        conversation = _start_friend_conversation(driver_profile, laborer_profile)
        if connection.requested_by_id:
            Notification.objects.create(
                recipient=connection.requested_by,
                message=f"{_display_name_for_user(request.user)} accepted your friend request.",
                url=_open_chat_url(conversation),
            )
        messages.success(
            request,
            format_html("You're now friends!{}", message_cta_html(other_profile)),
        )
    return connection


class AddLaborerFriendView(RoleRequiredMixin, View):
    allowed_roles = (User.Role.DRIVER,)

    def post(self, request, laborer_pk):
        laborer_profile = get_object_or_404(LaborerProfile, pk=laborer_pk)
        _handle_friend_request(request, request.user.driver_profile, laborer_profile)
        return redirect(request.META.get("HTTP_REFERER") or reverse("accounts:friends"))


class AddDriverFriendView(RoleRequiredMixin, View):
    allowed_roles = (User.Role.LABORER,)

    def post(self, request, driver_pk):
        driver_profile = get_object_or_404(DriverProfile, pk=driver_pk)
        _handle_friend_request(request, driver_profile, request.user.laborer_profile)
        return redirect(request.META.get("HTTP_REFERER") or reverse("accounts:friends"))


class AcceptFriendRequestView(RoleRequiredMixin, View):
    allowed_roles = (User.Role.DRIVER, User.Role.LABORER)

    def post(self, request, connection_pk):
        user = request.user
        if user.role == User.Role.DRIVER:
            connection = get_object_or_404(
                Connection,
                pk=connection_pk,
                driver_profile=user.driver_profile,
                status=Connection.Status.PENDING,
            )
        else:
            connection = get_object_or_404(
                Connection,
                pk=connection_pk,
                laborer_profile=user.laborer_profile,
                status=Connection.Status.PENDING,
            )
        if connection.requested_by_id == user.id:
            messages.error(request, "You can't accept your own request.")
            return redirect(request.META.get("HTTP_REFERER") or reverse("accounts:friends"))
        from jobs.views import message_cta_html

        other_profile = (
            connection.laborer_profile if user.role == User.Role.DRIVER else connection.driver_profile
        )
        connection.status = Connection.Status.ACCEPTED
        connection.responded_at = timezone.now()
        connection.save(update_fields=["status", "responded_at"])
        conversation = _start_friend_conversation(connection.driver_profile, connection.laborer_profile)
        if connection.requested_by_id:
            Notification.objects.create(
                recipient=connection.requested_by,
                message=f"{_display_name_for_user(user)} accepted your friend request.",
                url=_open_chat_url(conversation),
            )
        messages.success(
            request,
            format_html("Friend request accepted.{}", message_cta_html(other_profile)),
        )
        return redirect(request.META.get("HTTP_REFERER") or reverse("accounts:friends"))


class DeclineFriendRequestView(RoleRequiredMixin, View):
    allowed_roles = (User.Role.DRIVER, User.Role.LABORER)

    def post(self, request, connection_pk):
        user = request.user
        if user.role == User.Role.DRIVER:
            connection = get_object_or_404(
                Connection,
                pk=connection_pk,
                driver_profile=user.driver_profile,
                status=Connection.Status.PENDING,
            )
        else:
            connection = get_object_or_404(
                Connection,
                pk=connection_pk,
                laborer_profile=user.laborer_profile,
                status=Connection.Status.PENDING,
            )
        connection.delete()
        messages.success(request, "Request removed.")
        return redirect(request.META.get("HTTP_REFERER") or reverse("accounts:friends"))


class RemoveFriendView(RoleRequiredMixin, View):
    allowed_roles = (User.Role.DRIVER, User.Role.LABORER)

    def post(self, request, connection_pk):
        user = request.user
        if user.role == User.Role.DRIVER:
            connection = get_object_or_404(
                Connection,
                pk=connection_pk,
                driver_profile=user.driver_profile,
                status=Connection.Status.ACCEPTED,
            )
        else:
            connection = get_object_or_404(
                Connection,
                pk=connection_pk,
                laborer_profile=user.laborer_profile,
                status=Connection.Status.ACCEPTED,
            )
        connection.delete()
        messages.success(request, "Removed from friends.")
        return redirect("accounts:friends")

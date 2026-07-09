from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, ListView, TemplateView, UpdateView

from .forms import DriverSignUpForm, LaborerProfileEditForm, LaborerSignUpForm
from .models import Connection, DriverProfile, LaborerProfile, Notification, User


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
        return redirect("accounts:admin_dashboard")
    if request.user.role == User.Role.DRIVER:
        return redirect("accounts:driver_dashboard")
    return redirect("accounts:laborer_dashboard")


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

        from jobs.models import Job

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
        return context


class LaborerDashboardView(RoleRequiredMixin, TemplateView):
    template_name = "accounts/laborer_dashboard.html"
    allowed_roles = (User.Role.LABORER,)

    def get_context_data(self, **kwargs):
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


class AdminDashboardView(RoleRequiredMixin, TemplateView):
    template_name = "accounts/admin_dashboard.html"
    allowed_roles = (User.Role.ADMIN,)


class NotificationListView(LoginRequiredMixin, ListView):
    template_name = "accounts/notifications.html"
    context_object_name = "notification_list"

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)[:30]

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
            context["connections"] = Connection.objects.filter(
                driver_profile=user.driver_profile
            ).select_related("laborer_profile", "laborer_profile__user")
        else:
            context["connections"] = Connection.objects.filter(
                laborer_profile=user.laborer_profile
            ).select_related("driver_profile", "driver_profile__user")
        return context


class AddLaborerFriendView(RoleRequiredMixin, View):
    allowed_roles = (User.Role.DRIVER,)

    def post(self, request, laborer_pk):
        laborer_profile = get_object_or_404(LaborerProfile, pk=laborer_pk)
        _, created = Connection.objects.get_or_create(
            driver_profile=request.user.driver_profile, laborer_profile=laborer_profile
        )
        if created:
            messages.success(request, f"Added {laborer_profile} to your friends.")
        else:
            messages.info(request, f"{laborer_profile} is already in your friends.")
        return redirect(request.META.get("HTTP_REFERER") or reverse("accounts:friends"))


class AddDriverFriendView(RoleRequiredMixin, View):
    allowed_roles = (User.Role.LABORER,)

    def post(self, request, driver_pk):
        driver_profile = get_object_or_404(DriverProfile, pk=driver_pk)
        _, created = Connection.objects.get_or_create(
            driver_profile=driver_profile, laborer_profile=request.user.laborer_profile
        )
        if created:
            messages.success(request, f"Added {driver_profile} to your friends.")
        else:
            messages.info(request, f"{driver_profile} is already in your friends.")
        return redirect(request.META.get("HTTP_REFERER") or reverse("accounts:friends"))


class RemoveFriendView(RoleRequiredMixin, View):
    allowed_roles = (User.Role.DRIVER, User.Role.LABORER)

    def post(self, request, connection_pk):
        user = request.user
        if user.role == User.Role.DRIVER:
            connection = get_object_or_404(
                Connection, pk=connection_pk, driver_profile=user.driver_profile
            )
        else:
            connection = get_object_or_404(
                Connection, pk=connection_pk, laborer_profile=user.laborer_profile
            )
        connection.delete()
        messages.success(request, "Removed from friends.")
        return redirect("accounts:friends")

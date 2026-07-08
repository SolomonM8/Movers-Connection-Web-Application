from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView, UpdateView

from .forms import DriverSignUpForm, LaborerProfileEditForm, LaborerSignUpForm
from .models import User


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


class LaborerDashboardView(RoleRequiredMixin, TemplateView):
    template_name = "accounts/laborer_dashboard.html"
    allowed_roles = (User.Role.LABORER,)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.request.user.laborer_profile
        context["profile"] = profile
        context["service_areas"] = (
            profile.service_areas.select_related("county").order_by("county__state", "county__name")
        )
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

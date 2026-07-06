from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView

from .forms import DriverSignUpForm, LaborerSignUpForm
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
    extra_context = {"role_label": "Driver / Moving Company"}

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response


class LaborerSignUpView(CreateView):
    form_class = LaborerSignUpForm
    template_name = "accounts/signup_form.html"
    success_url = reverse_lazy("accounts:dashboard")
    extra_context = {"role_label": "Laborer / Labor Group"}

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


class AdminDashboardView(RoleRequiredMixin, TemplateView):
    template_name = "accounts/admin_dashboard.html"
    allowed_roles = (User.Role.ADMIN,)

from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView

from .forms import RoleRestrictedUserCreationForm
from .models import User


class RegisterView(CreateView):
    form_class = RoleRestrictedUserCreationForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("accounts:dashboard")

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response


class CustomLoginView(LoginView):
    template_name = "accounts/login.html"


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

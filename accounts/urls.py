from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", views.CustomLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page="accounts:login"), name="logout"),
    path("dashboard/", views.dashboard_redirect, name="dashboard"),
    path("dashboard/driver/", views.DriverDashboardView.as_view(), name="driver_dashboard"),
    path("dashboard/laborer/", views.LaborerDashboardView.as_view(), name="laborer_dashboard"),
    path("dashboard/admin/", views.AdminDashboardView.as_view(), name="admin_dashboard"),
]

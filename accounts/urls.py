from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.CustomLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(next_page="accounts:login"), name="logout"),
    path("register/", views.RoleChoiceView.as_view(), name="register"),
    path("register/driver/", views.DriverSignUpView.as_view(), name="register_driver"),
    path("register/laborer/", views.LaborerSignUpView.as_view(), name="register_laborer"),
    path("dashboard/", views.dashboard_redirect, name="dashboard"),
    path("dashboard/driver/", views.DriverDashboardView.as_view(), name="driver_dashboard"),
    path("dashboard/laborer/", views.LaborerDashboardView.as_view(), name="laborer_dashboard"),
    path("dashboard/laborer/edit/", views.LaborerProfileEditView.as_view(), name="laborer_profile_edit"),
    path("dashboard/driver/edit/", views.DriverProfileEditView.as_view(), name="driver_profile_edit"),
    path("dashboard/admin/", views.AdminDashboardView.as_view(), name="admin_dashboard"),
    path("notifications/", views.NotificationListView.as_view(), name="notifications"),
    path(
        "notifications/mark-read/",
        views.NotificationMarkReadView.as_view(),
        name="notifications_mark_read",
    ),
    path("notifications/clear/", views.NotificationClearView.as_view(), name="notifications_clear"),
    path("friends/", views.FriendsListView.as_view(), name="friends"),
    path(
        "friends/add/laborer/<int:laborer_pk>/",
        views.AddLaborerFriendView.as_view(),
        name="add_laborer_friend",
    ),
    path(
        "friends/add/driver/<int:driver_pk>/",
        views.AddDriverFriendView.as_view(),
        name="add_driver_friend",
    ),
    path("friends/remove/<int:connection_pk>/", views.RemoveFriendView.as_view(), name="remove_friend"),
]

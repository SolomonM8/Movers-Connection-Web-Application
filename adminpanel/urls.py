from django.urls import path

from . import views

app_name = "adminpanel"

urlpatterns = [
    path("users/", views.UserListView.as_view(), name="user_list"),
    path("users/<int:user_pk>/", views.UserDetailView.as_view(), name="user_detail"),
    path("users/<int:user_pk>/ban/", views.BanUserView.as_view(), name="ban_user"),
    path("jobs/", views.JobListView.as_view(), name="job_list"),
    path("jobs/<int:pk>/close/", views.JobForceCloseView.as_view(), name="job_force_close"),
    path("jobs/<int:pk>/assign/", views.JobAssignView.as_view(), name="job_assign"),
    path("reports/", views.ReportListView.as_view(), name="report_list"),
    path("reports/<int:report_pk>/status/", views.ReportUpdateStatusView.as_view(), name="report_update_status"),
    path("bug-reports/", views.BugReportListView.as_view(), name="bug_report_list"),
    path(
        "bug-reports/<int:bug_report_pk>/status/",
        views.BugReportUpdateStatusView.as_view(),
        name="bug_report_update_status",
    ),
    path("support/", views.SupportInboxView.as_view(), name="support_inbox"),
    path("support/start/<int:user_pk>/", views.SupportStartView.as_view(), name="support_start"),
    path("support/<int:thread_pk>/", views.SupportThreadView.as_view(), name="support_thread"),
    path("report-user/<int:user_pk>/", views.ReportUserView.as_view(), name="report_user"),
    path("report-bug/", views.BugReportSubmitView.as_view(), name="report_bug"),
    path("my-support/", views.UserSupportThreadView.as_view(), name="user_support_thread"),
]

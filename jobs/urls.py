from django.urls import path

from . import views

app_name = "jobs"

urlpatterns = [
    path("", views.job_hub_redirect, name="hub"),
    path("mine/", views.DriverJobHubView.as_view(), name="driver_hub"),
    path("mine/history/", views.LaborerPastJobListView.as_view(), name="laborer_past"),
    path("create/", views.JobCreateView.as_view(), name="create"),
    path("past/", views.DriverPastJobListView.as_view(), name="past"),
    path("browse/", views.LaborerJobListView.as_view(), name="browse"),
    path("invite/<int:laborer_pk>/", views.JobInviteView.as_view(), name="invite"),
    path("<int:pk>/", views.JobDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.JobUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.JobDeleteView.as_view(), name="delete"),
    path("<int:pk>/complete/", views.JobMarkCompleteView.as_view(), name="mark_complete"),
    path("<int:pk>/ratings/", views.JobRatingIndexView.as_view(), name="rating_index"),
    path("applications/<int:app_pk>/rate/", views.JobRatingCreateView.as_view(), name="rate_application"),
    path("<int:pk>/apply/", views.JobApplyView.as_view(), name="apply"),
    path(
        "<int:pk>/applications/<int:app_pk>/respond/",
        views.ApplicationRespondView.as_view(),
        name="application_respond",
    ),
    path(
        "applications/<int:app_pk>/respond-invite/",
        views.InvitationRespondView.as_view(),
        name="invitation_respond",
    ),
    path(
        "api/messages/unread-count/",
        views.MessageUnreadCountAPIView.as_view(),
        name="message_unread_count",
    ),
    path(
        "api/messages/conversations/",
        views.ConversationListAPIView.as_view(),
        name="message_conversations",
    ),
    path(
        "api/messages/search-friends/",
        views.FriendSearchAPIView.as_view(),
        name="friend_search",
    ),
    path(
        "api/messages/start/",
        views.ConversationStartAPIView.as_view(),
        name="conversation_start",
    ),
    path(
        "api/messages/thread/<int:conversation_pk>/",
        views.ConversationThreadAPIView.as_view(),
        name="conversation_thread",
    ),
]

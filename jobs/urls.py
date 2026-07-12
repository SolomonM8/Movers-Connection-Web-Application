from django.urls import path

from . import views

app_name = "jobs"

urlpatterns = [
    path("create/", views.JobCreateView.as_view(), name="create"),
    path("past/", views.DriverPastJobListView.as_view(), name="past"),
    path("browse/", views.LaborerJobListView.as_view(), name="browse"),
    path("invite/<int:laborer_pk>/", views.JobInviteView.as_view(), name="invite"),
    path("messages/", views.MessageInboxView.as_view(), name="message_inbox"),
    path(
        "friend-messages/<int:connection_pk>/",
        views.FriendMessageThreadView.as_view(),
        name="friend_messages",
    ),
    path("<int:pk>/", views.JobDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.JobUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.JobDeleteView.as_view(), name="delete"),
    path("<int:pk>/complete/", views.JobMarkCompleteView.as_view(), name="mark_complete"),
    path("<int:pk>/apply/", views.JobApplyView.as_view(), name="apply"),
    path(
        "<int:pk>/applications/<int:app_pk>/respond/",
        views.ApplicationRespondView.as_view(),
        name="application_respond",
    ),
    path("applications/<int:app_pk>/messages/", views.MessageThreadView.as_view(), name="messages"),
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
        "api/messages/job/<int:app_pk>/",
        views.JobMessageThreadAPIView.as_view(),
        name="message_thread_api",
    ),
    path(
        "api/messages/friend/<int:connection_pk>/",
        views.FriendMessageThreadAPIView.as_view(),
        name="friend_message_thread_api",
    ),
]

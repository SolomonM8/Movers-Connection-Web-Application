from django.urls import path

from . import views

app_name = "board"

urlpatterns = [
    path("", views.BoardFeedView.as_view(), name="feed"),
    path("create/", views.PostCreateView.as_view(), name="create"),
    path("<int:pk>/", views.PostDetailView.as_view(), name="detail"),
    path("<int:pk>/delete/", views.PostDeleteView.as_view(), name="delete"),
    path("<int:pk>/comments/", views.CommentCreateView.as_view(), name="comment_create"),
    path(
        "<int:pk>/comments/<int:comment_pk>/delete/",
        views.CommentDeleteView.as_view(),
        name="comment_delete",
    ),
]

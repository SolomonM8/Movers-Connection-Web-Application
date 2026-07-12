from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView

from accounts.models import Notification, User
from accounts.views import RoleRequiredMixin, _display_name_for_user, _profile_for_user

from .forms import CommentForm, MAX_IMAGES_PER_POST, PostForm, validate_board_image
from .models import Comment, Post, PostImage

FEED_PAGE_SIZE = 15


class BoardFeedView(RoleRequiredMixin, ListView):
    template_name = "board/feed.html"
    context_object_name = "posts"
    paginate_by = FEED_PAGE_SIZE
    allowed_roles = (User.Role.DRIVER, User.Role.LABORER)

    def get_queryset(self):
        return (
            Post.objects.select_related("author")
            .prefetch_related("images", "jobs__county")
            .annotate(comment_count=Count("comments"))
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for post in context["posts"]:
            post.author_profile = _profile_for_user(post.author)
            post.author_display_name = _display_name_for_user(post.author)
        return context


class PostCreateView(RoleRequiredMixin, CreateView):
    form_class = PostForm
    template_name = "board/post_form.html"
    allowed_roles = (User.Role.DRIVER, User.Role.LABORER)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        images = self.request.FILES.getlist("images")
        body = form.cleaned_data.get("body", "").strip()
        has_jobs = bool(form.cleaned_data.get("jobs"))
        if not body and not images and not has_jobs:
            form.add_error(None, "Your post needs some text, at least one photo, or a linked job.")
            return self.form_invalid(form)
        if len(images) > MAX_IMAGES_PER_POST:
            form.add_error(None, f"You can attach at most {MAX_IMAGES_PER_POST} images per post.")
            return self.form_invalid(form)
        for image in images:
            error = validate_board_image(image)
            if error:
                form.add_error(None, error)
                return self.form_invalid(form)

        form.instance.author = self.request.user
        response = super().form_valid(form)
        if "jobs" in form.cleaned_data:
            self.object.jobs.set(form.cleaned_data["jobs"])
        for image in images:
            PostImage.objects.create(post=self.object, image=image)
        messages.success(self.request, "Your post has been shared.")
        return response

    def get_success_url(self):
        return reverse("board:detail", args=[self.object.pk])


class PostDetailView(RoleRequiredMixin, DetailView):
    model = Post
    template_name = "board/post_detail.html"
    context_object_name = "post"
    allowed_roles = (User.Role.DRIVER, User.Role.LABORER)

    def get_queryset(self):
        return Post.objects.select_related("author").prefetch_related("images", "jobs__county")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.object.author_profile = _profile_for_user(self.object.author)
        self.object.author_display_name = _display_name_for_user(self.object.author)
        comments = list(self.object.comments.select_related("author"))
        for comment in comments:
            comment.author_profile = _profile_for_user(comment.author)
            comment.author_display_name = _display_name_for_user(comment.author)
        context["comments"] = comments
        context["comment_form"] = CommentForm()
        return context


class CommentCreateView(RoleRequiredMixin, View):
    allowed_roles = (User.Role.DRIVER, User.Role.LABORER)

    def post(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post
            comment.author = request.user
            comment.save()
            if post.author_id != request.user.id:
                Notification.objects.create(
                    recipient=post.author,
                    message=f"{_display_name_for_user(request.user)} commented on your post.",
                    url=reverse("board:detail", args=[post.pk]),
                )
            messages.success(request, "Comment posted.")
        else:
            messages.error(request, "Comment couldn't be posted — please try again.")
        return redirect("board:detail", pk=pk)


class PostDeleteView(RoleRequiredMixin, View):
    allowed_roles = (User.Role.DRIVER, User.Role.LABORER)

    def post(self, request, pk):
        post = get_object_or_404(Post, pk=pk, author=request.user)
        post.delete()
        messages.success(request, "Post deleted.")
        return redirect("board:feed")


class CommentDeleteView(RoleRequiredMixin, View):
    allowed_roles = (User.Role.DRIVER, User.Role.LABORER)

    def post(self, request, pk, comment_pk):
        comment = get_object_or_404(Comment, pk=comment_pk, post_id=pk, author=request.user)
        comment.delete()
        messages.success(request, "Comment deleted.")
        return redirect("board:detail", pk=pk)

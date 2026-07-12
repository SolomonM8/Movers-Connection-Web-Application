from django.contrib import admin

from .models import Comment, Post, PostImage


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("__str__", "author", "created_at")
    search_fields = ("author__email", "body")


@admin.register(PostImage)
class PostImageAdmin(admin.ModelAdmin):
    list_display = ("__str__", "post", "created_at")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("__str__", "post", "author", "created_at")
    search_fields = ("author__email", "body")

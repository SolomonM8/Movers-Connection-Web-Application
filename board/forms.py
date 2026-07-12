from django import forms
from django.utils import timezone

from accounts.forms import ALLOWED_IMAGE_CONTENT_TYPES, MAX_IMAGE_SIZE_BYTES
from accounts.models import User
from jobs.models import Job

from .models import Comment, Post

MAX_IMAGES_PER_POST = 6


def validate_board_image(image):
    """Returns an error string, or None if the image is valid."""
    if not hasattr(image, "content_type"):
        return None
    if image.content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        return "Please upload only JPG, PNG, or WEBP images."
    if image.size > MAX_IMAGE_SIZE_BYTES:
        return "Each image must be smaller than 5MB."
    return None


class PostForm(forms.ModelForm):
    jobs = forms.ModelMultipleChoiceField(
        queryset=Job.objects.none(), required=False, widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = Post
        fields = ["body"]
        widgets = {
            "body": forms.Textarea(
                attrs={"rows": 4, "placeholder": "Share something with the community…"}
            )
        }
        labels = {"body": ""}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["body"].required = False
        if user is not None and user.role == User.Role.DRIVER and hasattr(user, "driver_profile"):
            self.fields["jobs"].queryset = Job.objects.filter(
                driver_profile=user.driver_profile,
                status=Job.Status.OPEN,
                job_date__gte=timezone.now().date(),
            ).select_related("county")
        else:
            del self.fields["jobs"]


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 2, "placeholder": "Write a comment…"})}
        labels = {"body": ""}

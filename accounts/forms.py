from django import forms
from django.contrib.auth import password_validation

from .constants import US_STATE_CHOICES
from .models import DriverProfile, LaborerProfile, User


class BaseSignUpForm(forms.ModelForm):
    role = None
    profile_model = None
    name_field_name = None

    name = forms.CharField(max_length=255)
    email = forms.EmailField()
    phone_number = forms.CharField(max_length=20, label="Phone number")
    city = forms.CharField(max_length=100)
    state = forms.ChoiceField(choices=US_STATE_CHOICES)
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput, strip=False)
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput, strip=False)

    class Meta:
        model = User
        fields = ("email",)

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match.")
        return password2

    def _post_clean(self):
        super()._post_clean()
        password2 = self.cleaned_data.get("password2")
        if password2:
            try:
                password_validation.validate_password(password2, self.instance)
            except forms.ValidationError as error:
                self.add_error("password2", error)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = self.role
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            self.profile_model.objects.update_or_create(
                user=user,
                defaults={
                    self.name_field_name: self.cleaned_data["name"],
                    "phone_number": self.cleaned_data["phone_number"],
                    "city": self.cleaned_data["city"],
                    "state": self.cleaned_data["state"],
                },
            )
        return user


class DriverSignUpForm(BaseSignUpForm):
    role = User.Role.DRIVER
    profile_model = DriverProfile
    name_field_name = "company_name"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].label = "Company or driver name"


class LaborerSignUpForm(BaseSignUpForm):
    role = User.Role.LABORER
    profile_model = LaborerProfile
    name_field_name = "display_name"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].label = "Your name or labor group name"


MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


class ProfileEditFormBase(forms.ModelForm):
    email = forms.EmailField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["email"].initial = self.instance.user.email

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        qs = User.objects.filter(email__iexact=email)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.user_id)
        if qs.exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def _clean_image(self, field_name):
        image = self.cleaned_data.get(field_name)
        if not image or not hasattr(image, "content_type"):
            return image
        if image.content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise forms.ValidationError("Please upload a JPG, PNG, or WEBP image.")
        if image.size > MAX_IMAGE_SIZE_BYTES:
            raise forms.ValidationError("Image must be smaller than 5MB.")
        return image

    def clean_profile_picture(self):
        return self._clean_image("profile_picture")

    def clean_banner_image(self):
        return self._clean_image("banner_image")

    def save(self, commit=True):
        profile = super().save(commit=commit)
        if commit:
            user = profile.user
            user.email = self.cleaned_data["email"]
            user.save(update_fields=["email"])
        return profile


class LaborerProfileEditForm(ProfileEditFormBase):
    class Meta:
        model = LaborerProfile
        fields = (
            "display_name",
            "phone_number",
            "city",
            "state",
            "profile_picture",
            "banner_image",
            "has_dolly",
            "has_floor_dolly",
            "has_tools",
            "has_drills",
            "has_shoulder_dollies",
            "has_hump_straps",
        )
        labels = {
            "display_name": "Your name or labor group name",
            "has_dolly": "Dolly",
            "has_floor_dolly": "Floor dolly",
            "has_tools": "Tools",
            "has_drills": "Drills",
            "has_shoulder_dollies": "Shoulder dollies",
            "has_hump_straps": "Hump straps",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(
            [
                "email",
                "display_name",
                "phone_number",
                "city",
                "state",
                "profile_picture",
                "banner_image",
                "has_dolly",
                "has_floor_dolly",
                "has_tools",
                "has_drills",
                "has_shoulder_dollies",
                "has_hump_straps",
            ]
        )


class DriverProfileEditForm(ProfileEditFormBase):
    class Meta:
        model = DriverProfile
        fields = ("company_name", "dot_number", "phone_number", "city", "state", "profile_picture", "banner_image")
        labels = {"company_name": "Company or driver name"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(
            ["email", "company_name", "dot_number", "phone_number", "city", "state", "profile_picture", "banner_image"]
        )

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from .forms import create_profile_for_role


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def save_user(self, request, sociallogin, form=None):
        # Pass form=None to super() regardless -- the default implementation reads
        # first_name/last_name/username/password1 off the form via allauth's own
        # field-mapping helpers, none of which exist on our User model (no
        # username field at all: USERNAME_FIELD = "email", REQUIRED_FIELDS = []).
        # We handle role + profile creation ourselves below instead.
        user = super().save_user(request, sociallogin, form=None)
        if form is not None:
            cleaned = form.cleaned_data
            user.role = cleaned["role"]
            user.save(update_fields=["role"])
            create_profile_for_role(
                user,
                cleaned["role"],
                name=cleaned["name"],
                phone_number=cleaned["phone_number"],
                city=cleaned["city"],
                state=cleaned["state"],
            )
        return user

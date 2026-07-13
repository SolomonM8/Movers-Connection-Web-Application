from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from .forms import create_profile_for_role
from .models import User


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def save_user(self, request, sociallogin, form=None):
        # Pass form=None to super() regardless -- the default implementation reads
        # first_name/last_name/username/password1 off the form via allauth's own
        # field-mapping helpers, none of which exist on our User model (no
        # username field at all: USERNAME_FIELD = "email", REQUIRED_FIELDS = []).
        # We handle role + profile creation ourselves below instead.
        user = super().save_user(request, sociallogin, form=None)
        if form is not None:
            # Role is picked before the OAuth round-trip even starts (see
            # accounts.views.SocialSignupRoleGateView) since the provider has no
            # way to carry it back to us -- read it from the session instead of
            # the (role-less) form.
            role = request.session.pop("pending_social_role", None)
            if role not in (User.Role.DRIVER, User.Role.LABORER):
                role = User.Role.LABORER  # defensive fallback; shouldn't normally happen
            cleaned = form.cleaned_data
            user.role = role
            user.save(update_fields=["role"])
            create_profile_for_role(
                user,
                role,
                name=cleaned["name"],
                phone_number=cleaned["phone_number"],
                city=cleaned["city"],
                state=cleaned["state"],
            )
        return user

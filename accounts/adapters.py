from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from .forms import create_profile_for_role
from .models import User


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        # If this Google/Facebook email already has a password-based account,
        # link the two instead of letting the flow try to create a second User
        # row with the same (unique) email -- which crashes with an
        # IntegrityError once the completion form is submitted. Only auto-link
        # on a verified email (Google always verifies before allowing OAuth;
        # this guard keeps the same code safe for providers that don't).
        if sociallogin.is_existing:
            return
        if not sociallogin.email_addresses:
            return
        primary_email = sociallogin.email_addresses[0]
        if not primary_email.verified:
            return
        existing_user = User.objects.filter(email__iexact=primary_email.email).first()
        if existing_user:
            sociallogin.connect(request, existing_user)

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

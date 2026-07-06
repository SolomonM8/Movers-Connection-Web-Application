from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User

# Admin accounts are provisioned via createsuperuser/Django admin, not self-registration.
PUBLIC_ROLE_CHOICES = [c for c in User.Role.choices if c[0] != User.Role.ADMIN]


class RoleRestrictedUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(choices=PUBLIC_ROLE_CHOICES, widget=forms.RadioSelect)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "role")

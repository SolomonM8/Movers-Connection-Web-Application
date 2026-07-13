from datetime import timedelta

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from .models import Notification, User

REMINDER_MESSAGE = "Reminder: select at least one service-area county to unlock the rest of the site."
REMINDER_INTERVAL = timedelta(minutes=10)

EXEMPT_URL_NAMES = {
    ("accounts", "logout"),
    ("accounts", "notifications_mark_read"),
    ("accounts", "notifications_clear"),
    ("accounts", "mark_tour_seen"),
    ("coverage", "service_areas"),
    ("coverage", "toggle_service_area"),
    ("coverage", "set_primary_service_area"),
}


class LaborerOnboardingLockMiddleware:
    """Redirects a laborer who hasn't selected any service-area counties back to
    their dashboard for every page except a small exempt set, and sends them a
    reminder Notification roughly every 10 minutes of activity (there's no
    background scheduler in this project, so this is a lazy, request-time check,
    not a true wall-clock timer)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        user = request.user
        if not user.is_authenticated or user.is_superuser or user.role != User.Role.LABORER:
            return None
        profile = getattr(user, "laborer_profile", None)
        if profile is None or profile.service_areas.exists():
            return None

        match = request.resolver_match
        # Unnamed/unnamespaced views (static/media serving, etc.) can't be sensibly
        # matched against EXEMPT_URL_NAMES -- let them through rather than guess.
        if match is None or not match.url_name:
            return None
        if match.app_name == "admin":
            return None
        if (match.app_name, match.url_name) in EXEMPT_URL_NAMES:
            return None

        self._maybe_send_reminder(user)
        messages.error(request, "Select at least one service-area county to unlock the rest of the site.")
        return redirect("coverage:service_areas")

    def _maybe_send_reminder(self, user):
        cutoff = timezone.now() - REMINDER_INTERVAL
        already_sent_recently = Notification.objects.filter(
            recipient=user, message=REMINDER_MESSAGE, created_at__gte=cutoff
        ).exists()
        if not already_sent_recently:
            Notification.objects.create(
                recipient=user, message=REMINDER_MESSAGE, url=reverse("coverage:service_areas"),
            )

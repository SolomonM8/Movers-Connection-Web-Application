from django.conf import settings
from django.db import models


class Report(models.Model):
    class Reason(models.TextChoices):
        SPAM = "spam", "Spam or scam"
        HARASSMENT = "harassment", "Harassment or abusive behavior"
        INAPPROPRIATE = "inappropriate", "Inappropriate messages or content"
        NO_SHOW = "no_show", "Didn't show up / no-call no-show"
        UNSAFE = "unsafe", "Unsafe behavior on the job"
        PAYMENT = "payment", "Payment dispute or fraud"
        FAKE_PROFILE = "fake_profile", "Fake profile or impersonation"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        REVIEWED = "reviewed", "Reviewed"
        ACTIONED = "actioned", "Actioned"
        DISMISSED = "dismissed", "Dismissed"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports_filed"
    )
    reported_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports_received"
    )
    reason = models.CharField(max_length=20, choices=Reason.choices)
    details = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Report: {self.reporter} -> {self.reported_user} ({self.get_reason_display()})"


class BugReport(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        RESOLVED = "resolved", "Resolved"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bug_reports"
    )
    description = models.TextField()
    page_url = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Bug report from {self.reporter} ({self.get_status_display()})"


class SupportThread(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="support_thread"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Support thread for {self.user}"


class SupportMessage(models.Model):
    thread = models.ForeignKey(SupportThread, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    is_from_admin = models.BooleanField(default=False)
    body = models.TextField()
    is_read_by_user = models.BooleanField(default=False)
    is_read_by_admin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Message on {self.thread} from {self.sender}"

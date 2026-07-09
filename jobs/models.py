from django.conf import settings
from django.db import models

from accounts.models import DriverProfile, LaborerProfile
from coverage.models import County


class Job(models.Model):
    class JobType(models.TextChoices):
        LOAD = "load", "Load"
        UNLOAD = "unload", "Unload"
        PACKING = "packing", "Packing"
        INTERNAL = "internal", "Internal"

    class PricingModel(models.TextChoices):
        FLAT_RATE = "flat_rate", "Flat rate per worker"
        HOURLY = "hourly", "Hourly rate per worker"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        COMPLETED = "completed", "Completed"

    driver_profile = models.ForeignKey(DriverProfile, on_delete=models.CASCADE, related_name="jobs")
    county = models.ForeignKey(County, on_delete=models.PROTECT, related_name="jobs")
    city = models.CharField(max_length=100, blank=True)
    job_date = models.DateField()
    job_type = models.CharField(max_length=20, choices=JobType.choices)
    workers_needed = models.PositiveIntegerField(default=1)
    pricing_model = models.CharField(max_length=20, choices=PricingModel.choices)
    flat_rate_per_worker = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    hourly_rate = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    weight_lbs = models.PositiveIntegerField(null=True, blank=True, verbose_name="Approximate weight (lbs)")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-job_date", "-created_at"]

    def __str__(self):
        return f"{self.get_job_type_display()} job on {self.job_date} in {self.county}"


class JobApplication(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="applications")
    laborer_profile = models.ForeignKey(
        LaborerProfile, on_delete=models.CASCADE, related_name="job_applications"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    applied_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("job", "laborer_profile")
        ordering = ["-applied_at"]

    def __str__(self):
        return f"{self.laborer_profile} applied to {self.job}"


class Message(models.Model):
    application = models.ForeignKey(JobApplication, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_job_messages"
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Message from {self.sender} on {self.application}"

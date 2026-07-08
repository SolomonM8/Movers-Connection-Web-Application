from django.db import models

from accounts.models import DriverProfile
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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-job_date", "-created_at"]

    def __str__(self):
        return f"{self.get_job_type_display()} job on {self.job_date} in {self.county}"

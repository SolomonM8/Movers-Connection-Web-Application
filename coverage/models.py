from django.db import models

from accounts.constants import US_STATE_CHOICES
from accounts.models import LaborerProfile


class County(models.Model):
    fips = models.CharField(max_length=5, primary_key=True)
    name = models.CharField(max_length=100)
    state = models.CharField(max_length=2, choices=US_STATE_CHOICES)

    class Meta:
        ordering = ["state", "name"]
        verbose_name_plural = "counties"

    def __str__(self):
        return f"{self.name}, {self.state}"


class ServiceArea(models.Model):
    laborer_profile = models.ForeignKey(
        LaborerProfile, on_delete=models.CASCADE, related_name="service_areas"
    )
    county = models.ForeignKey(County, on_delete=models.CASCADE, related_name="service_areas")
    is_primary = models.BooleanField(
        default=False, help_text="The laborer's home/base county."
    )

    class Meta:
        unique_together = ("laborer_profile", "county")

    def __str__(self):
        base = " (home)" if self.is_primary else ""
        return f"{self.laborer_profile} serves {self.county}{base}"

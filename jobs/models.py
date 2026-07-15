from django.conf import settings
from django.db import models
from django.db.models import Avg, Count, Q
from django.utils import timezone

from accounts.models import Connection, DriverProfile, LaborerProfile
from coverage.models import County


class Job(models.Model):
    MAX_ACTIVE_PER_DRIVER = 3

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
    needs_loading_skill = models.BooleanField(default=False)
    needs_unloading_skill = models.BooleanField(default=False)
    needs_packing_skill = models.BooleanField(default=False)
    needs_equipment_skill = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-job_date", "-created_at"]

    def __str__(self):
        return f"{self.get_job_type_display()} job on {self.job_date} in {self.county}"

    @property
    def is_rating_eligible(self):
        return self.status == self.Status.COMPLETED or self.job_date < timezone.now().date()


class JobApplication(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"

    class Source(models.TextChoices):
        APPLIED = "applied", "Applied"
        INVITED = "invited", "Invited"

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="applications")
    laborer_profile = models.ForeignKey(
        LaborerProfile, on_delete=models.CASCADE, related_name="job_applications"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.APPLIED)
    applied_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("job", "laborer_profile")
        ordering = ["-applied_at"]

    def __str__(self):
        return f"{self.laborer_profile} applied to {self.job}"

    @property
    def display_label(self):
        """One unambiguous label instead of separately showing status and
        source. While pending, the source is what's actionable ("Invited" vs
        "Applied"); once responded to, the outcome is what matters."""
        if self.status == self.Status.PENDING:
            return self.get_source_display()
        return self.get_status_display()


RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]

CORE_RATING_FIELDS = ["professionalism", "punctuality", "moving_skill"]
CONDITIONAL_RATING_FIELDS = ["loading_skill", "unloading_skill", "packing_skill", "equipment_skill"]
RATING_FIELD_LABELS = {
    "professionalism": "Professionalism",
    "punctuality": "Punctuality",
    "moving_skill": "Moving skill",
    "loading_skill": "Loading skill",
    "unloading_skill": "Unloading skill",
    "packing_skill": "Packing skill",
    "equipment_skill": "Equipment",
}

# Maps each conditional rating field to the Job boolean that makes it applicable.
CONDITIONAL_RATING_JOB_FLAGS = {
    "loading_skill": "needs_loading_skill",
    "unloading_skill": "needs_unloading_skill",
    "packing_skill": "needs_packing_skill",
    "equipment_skill": "needs_equipment_skill",
}


class JobRating(models.Model):
    application = models.OneToOneField(JobApplication, on_delete=models.CASCADE, related_name="rating")
    professionalism = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    punctuality = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    moving_skill = models.PositiveSmallIntegerField(choices=RATING_CHOICES)
    loading_skill = models.PositiveSmallIntegerField(choices=RATING_CHOICES, null=True, blank=True)
    unloading_skill = models.PositiveSmallIntegerField(choices=RATING_CHOICES, null=True, blank=True)
    packing_skill = models.PositiveSmallIntegerField(choices=RATING_CHOICES, null=True, blank=True)
    equipment_skill = models.PositiveSmallIntegerField(choices=RATING_CHOICES, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Rating for {self.application}"


def unrated_eligible_applications(driver_profile):
    today = timezone.now().date()
    return JobApplication.objects.filter(
        job__driver_profile=driver_profile,
        status=JobApplication.Status.ACCEPTED,
        rating__isnull=True,
    ).filter(Q(job__status=Job.Status.COMPLETED) | Q(job__job_date__lt=today))


def rating_summary_for_laborer(laborer_profile):
    qs = JobRating.objects.filter(application__laborer_profile=laborer_profile)

    def _row(field):
        agg = qs.aggregate(avg=Avg(field), count=Count(field))
        avg, count = agg["avg"], agg["count"]
        filled = round(avg) if avg else 0
        return {
            "label": RATING_FIELD_LABELS[field],
            "average": avg,
            "count": count,
            "stars_display": "★" * filled + "☆" * (5 - filled),
        }

    core = [_row(field) for field in CORE_RATING_FIELDS]
    conditional = [
        _row(field)
        for field in CONDITIONAL_RATING_FIELDS
        if qs.filter(**{f"{field}__isnull": False}).exists()
    ]
    return {"core": core, "conditional": conditional}


class Conversation(models.Model):
    driver_profile = models.ForeignKey(
        DriverProfile, on_delete=models.CASCADE, related_name="conversations"
    )
    laborer_profile = models.ForeignKey(
        LaborerProfile, on_delete=models.CASCADE, related_name="conversations"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("driver_profile", "laborer_profile")

    def __str__(self):
        return f"{self.driver_profile} <-> {self.laborer_profile}"


class ConversationMessage(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_conversation_messages",
    )
    body = models.TextField()
    is_system = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    related_job = models.ForeignKey(
        "jobs.Job", on_delete=models.SET_NULL, null=True, blank=True, related_name="conversation_messages"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Message from {self.sender} on {self.conversation}"

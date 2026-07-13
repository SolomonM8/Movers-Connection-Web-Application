from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .constants import US_STATE_CHOICES


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        DRIVER = "driver", "Driver / Moving Company"
        LABORER = "laborer", "Laborer / Labor Group"

    email = models.EmailField("email address", unique=True)
    role = models.CharField(max_length=20, choices=Role.choices)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)
    has_seen_tour = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    @property
    def is_driver(self):
        return self.role == self.Role.DRIVER

    @property
    def is_laborer(self):
        return self.role == self.Role.LABORER

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN

    def __str__(self):
        return self.email


class ProfileBase(models.Model):
    phone_number = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=2, choices=US_STATE_CHOICES, blank=True)
    profile_picture = models.ImageField(upload_to="avatars/", blank=True, null=True)
    banner_image = models.ImageField(upload_to="banners/", blank=True, null=True)

    class Meta:
        abstract = True


class DriverProfile(ProfileBase):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="driver_profile")
    company_name = models.CharField(max_length=255, blank=True)
    dot_number = models.CharField(max_length=50, blank=True, verbose_name="USDOT number")
    jobs_created_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.company_name or self.user.email


class LaborerProfile(ProfileBase):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="laborer_profile")
    display_name = models.CharField(max_length=255, blank=True)
    bio = models.TextField(blank=True)
    years_experience = models.PositiveIntegerField(default=0)
    has_dolly = models.BooleanField(default=False)
    has_floor_dolly = models.BooleanField(default=False)
    has_tools = models.BooleanField(default=False)
    has_drills = models.BooleanField(default=False)
    has_shoulder_dollies = models.BooleanField(default=False)
    has_hump_straps = models.BooleanField(default=False)

    def __str__(self):
        return self.display_name or self.user.email


class Connection(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"

    driver_profile = models.ForeignKey(DriverProfile, on_delete=models.CASCADE, related_name="connections")
    laborer_profile = models.ForeignKey(
        LaborerProfile, on_delete=models.CASCADE, related_name="connections"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("driver_profile", "laborer_profile")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.driver_profile} <-> {self.laborer_profile}"


class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    message = models.CharField(max_length=255)
    url = models.CharField(max_length=255, blank=True)
    related_connection = models.ForeignKey(
        Connection, on_delete=models.CASCADE, null=True, blank=True, related_name="notifications"
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.recipient}: {self.message}"


class DeviceToken(models.Model):
    """A push-notification token for one installed copy of the mobile app."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="device_tokens")
    token = models.CharField(max_length=255, unique=True)
    platform = models.CharField(max_length=20, default="android")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} ({self.platform})"


@receiver(post_save, sender=Notification)
def _send_push_for_notification(sender, instance, created, **kwargs):
    if not created:
        return
    from .push import send_push_to_user

    send_push_to_user(instance.recipient, "Movers Connection", instance.message, instance.url)

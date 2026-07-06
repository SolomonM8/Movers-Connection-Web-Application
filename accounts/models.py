from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
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

    class Meta:
        abstract = True


class DriverProfile(ProfileBase):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="driver_profile")
    company_name = models.CharField(max_length=255, blank=True)
    dot_number = models.CharField(max_length=50, blank=True, verbose_name="USDOT number")

    def __str__(self):
        return self.company_name or self.user.email


class LaborerProfile(ProfileBase):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="laborer_profile")
    display_name = models.CharField(max_length=255, blank=True)
    bio = models.TextField(blank=True)
    years_experience = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.display_name or self.user.email

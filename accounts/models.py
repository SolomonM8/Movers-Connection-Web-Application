from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class CustomUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.ADMIN)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        DRIVER = "driver", "Driver / Moving Company"
        LABORER = "laborer", "Laborer / Labor Group"

    role = models.CharField(max_length=20, choices=Role.choices)

    objects = CustomUserManager()

    @property
    def is_driver(self):
        return self.role == self.Role.DRIVER

    @property
    def is_laborer(self):
        return self.role == self.Role.LABORER

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN


class DriverProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="driver_profile")
    company_name = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    dot_number = models.CharField(max_length=50, blank=True, verbose_name="USDOT number")

    def __str__(self):
        return self.company_name or self.user.username


class LaborerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="laborer_profile")
    display_name = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    bio = models.TextField(blank=True)
    years_experience = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.display_name or self.user.username

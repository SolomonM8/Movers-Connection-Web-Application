from django.contrib.auth.models import Group
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import DriverProfile, LaborerProfile, User

ROLE_GROUP_NAMES = {
    User.Role.ADMIN: "Admins",
    User.Role.DRIVER: "Drivers",
    User.Role.LABORER: "Laborers",
}


@receiver(post_save, sender=User)
def setup_new_user(sender, instance, created, **kwargs):
    if not created:
        return

    if instance.role == User.Role.DRIVER:
        DriverProfile.objects.get_or_create(user=instance)
    elif instance.role == User.Role.LABORER:
        LaborerProfile.objects.get_or_create(user=instance)

    group_name = ROLE_GROUP_NAMES.get(instance.role)
    if group_name:
        group, _ = Group.objects.get_or_create(name=group_name)
        instance.groups.add(group)

from .models import User


def nav_context(request):
    user = request.user
    if not user.is_authenticated:
        return {}

    context = {
        "unread_notification_count": user.notifications.filter(is_read=False).count(),
        "recent_notifications": user.notifications.select_related("related_connection").all()[:5],
        "laborer_locked": (
            user.role == User.Role.LABORER
            and not user.is_superuser
            and hasattr(user, "laborer_profile")
            and not user.laborer_profile.service_areas.exists()
        ),
    }

    name_source = None
    role_icon = None
    profile = None
    if user.role == User.Role.DRIVER and hasattr(user, "driver_profile"):
        profile = user.driver_profile
        name_source = profile.company_name
        role_icon = "includes/icon-truck.svg"
    elif user.role == User.Role.LABORER and hasattr(user, "laborer_profile"):
        profile = user.laborer_profile
        name_source = profile.display_name
        role_icon = "includes/icon-hardhat.svg"

    display_name = name_source.split()[0] if name_source else user.email.split("@")[0]
    context["nav_display_name"] = display_name
    context["nav_role_icon"] = role_icon
    context["nav_profile"] = profile
    return context

from django import template

register = template.Library()


def compute_avatar_initial(name):
    if not name:
        return "?"
    return name.strip()[0].upper()


def compute_avatar_hue(pk):
    return (int(pk) * 47) % 360


def compute_avatar_color(pk):
    return f"hsl({compute_avatar_hue(pk)}, 60%, 45%)"


@register.filter
def avatar_initial(name):
    return compute_avatar_initial(name)


@register.filter
def avatar_color(pk):
    return compute_avatar_color(pk)


@register.inclusion_tag("accounts/includes/avatar.html")
def avatar(profile, size="md"):
    picture = getattr(profile, "profile_picture", None) if profile else None
    return {
        "picture_url": picture.url if picture else None,
        "color": compute_avatar_color(profile.pk) if profile else "hsl(0, 0%, 60%)",
        "initial": compute_avatar_initial(str(profile)) if profile else "?",
        "size": size,
    }

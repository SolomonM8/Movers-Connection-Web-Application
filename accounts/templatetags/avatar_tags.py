from django import template

register = template.Library()


@register.filter
def avatar_initial(name):
    if not name:
        return "?"
    return name.strip()[0].upper()


@register.filter
def avatar_color(pk):
    hue = (int(pk) * 47) % 360
    return f"hsl({hue}, 60%, 45%)"

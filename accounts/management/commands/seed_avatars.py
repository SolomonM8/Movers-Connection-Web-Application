import colorsys
import io

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db.models import Q
from PIL import Image, ImageDraw, ImageFont

from accounts.models import LaborerProfile
from accounts.templatetags.avatar_tags import compute_avatar_hue, compute_avatar_initial

IMAGE_SIZE = 256


def hue_to_rgb(hue):
    r, g, b = colorsys.hls_to_rgb(hue / 360, 0.45, 0.6)
    return (round(r * 255), round(g * 255), round(b * 255))


class Command(BaseCommand):
    help = (
        "Generate and attach a placeholder profile picture (colored circle + initial, "
        "matching the site's existing avatar color scheme) to un-seeded laborer accounts. "
        "Images are drawn locally with Pillow, not downloaded from anywhere."
    )

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=5, help="Max number of profiles to seed.")

    def handle(self, *args, **options):
        profiles = LaborerProfile.objects.filter(
            Q(profile_picture="") | Q(profile_picture__isnull=True)
        ).order_by("pk")[: options["limit"]]
        if not profiles:
            self.stdout.write("No un-seeded laborer profiles found.")
            return

        try:
            font = ImageFont.truetype("arial.ttf", IMAGE_SIZE // 2)
        except OSError:
            font = ImageFont.load_default()

        for profile in profiles:
            name = profile.display_name or profile.user.email
            initial = compute_avatar_initial(name)
            rgb = hue_to_rgb(compute_avatar_hue(profile.pk))

            image = Image.new("RGB", (IMAGE_SIZE, IMAGE_SIZE), rgb)
            draw = ImageDraw.Draw(image)
            bbox = draw.textbbox((0, 0), initial, font=font)
            text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text(
                ((IMAGE_SIZE - text_w) / 2 - bbox[0], (IMAGE_SIZE - text_h) / 2 - bbox[1]),
                initial,
                fill="white",
                font=font,
            )

            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            profile.profile_picture.save(f"seed_{profile.pk}.png", ContentFile(buffer.getvalue()), save=True)
            self.stdout.write(self.style.SUCCESS(f"Seeded avatar for {name}"))

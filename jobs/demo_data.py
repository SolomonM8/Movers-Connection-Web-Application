from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from accounts.models import Connection, DriverProfile, User

from .models import Conversation, ConversationMessage, Job

DEMO_DRIVER_EMAIL = "demo-driver@themoversconnection.com"
DEMO_COMPANY_NAME = "(Example) Ace Moving Co"


def get_or_create_demo_driver_profile():
    user, created = User.objects.get_or_create(
        email=DEMO_DRIVER_EMAIL, defaults={"role": User.Role.DRIVER, "is_active": True}
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    # accounts.signals.setup_new_user already auto-creates an empty DriverProfile
    # the moment the User row above is saved, so get_or_create's `defaults` never
    # gets a chance to apply -- set the company name explicitly instead.
    profile, _ = DriverProfile.objects.get_or_create(user=user)
    if not profile.company_name:
        profile.company_name = DEMO_COMPANY_NAME
        profile.save(update_fields=["company_name"])
    return profile


def ensure_demo_job(demo_driver_profile, county):
    """One shared demo Job per county, reused by every laborer onboarding there."""
    job, created = Job.objects.get_or_create(
        driver_profile=demo_driver_profile,
        county=county,
        defaults=dict(
            job_type=Job.JobType.LOAD,
            workers_needed=2,
            pricing_model=Job.PricingModel.FLAT_RATE,
            flat_rate_per_worker=Decimal("150.00"),
            job_date=timezone.now().date() + timedelta(days=14),
            status=Job.Status.OPEN,
        ),
    )
    if job.job_date < timezone.now().date():
        # Keep it visible in Browse Jobs indefinitely rather than letting it go stale.
        job.job_date = timezone.now().date() + timedelta(days=14)
        job.status = Job.Status.OPEN
        job.save(update_fields=["job_date", "status"])
    return job


def ensure_demo_data_for_new_county(laborer_profile, county):
    demo_driver_profile = get_or_create_demo_driver_profile()
    ensure_demo_job(demo_driver_profile, county)
    Connection.objects.get_or_create(
        driver_profile=demo_driver_profile,
        laborer_profile=laborer_profile,
        defaults={"status": Connection.Status.ACCEPTED, "responded_at": timezone.now()},
    )
    conversation, created = Conversation.objects.get_or_create(
        driver_profile=demo_driver_profile, laborer_profile=laborer_profile
    )
    if created:
        ConversationMessage.objects.create(
            conversation=conversation,
            sender=demo_driver_profile.user,
            is_system=False,
            body="Welcome to Movers Connection! Glad to have you on board.",
        )
        ConversationMessage.objects.create(
            conversation=conversation,
            sender=demo_driver_profile.user,
            is_system=False,
            body=(
                "This is what messaging looks like — friends and drivers will reach out "
                "the same way once you're connected with them."
            ),
        )


def cleanup_demo_data(laborer_profile):
    """Called once all onboarding tours are done. Removes the temporary friend
    connection + conversation; the shared demo Job is intentionally left alone."""
    demo_driver_profile = DriverProfile.objects.filter(user__email=DEMO_DRIVER_EMAIL).first()
    if demo_driver_profile is None:
        return
    Connection.objects.filter(
        driver_profile=demo_driver_profile, laborer_profile=laborer_profile
    ).delete()
    Conversation.objects.filter(
        driver_profile=demo_driver_profile, laborer_profile=laborer_profile
    ).delete()

from django import forms

from coverage.models import County

from .models import Job, Message


class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = [
            "county",
            "city",
            "job_date",
            "job_type",
            "workers_needed",
            "pricing_model",
            "flat_rate_per_worker",
            "hourly_rate",
            "weight_lbs",
        ]
        widgets = {"job_date": forms.DateInput(attrs={"type": "date"})}
        labels = {"city": "City / meeting point (optional)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["county"].choices = self._grouped_county_choices()

    @staticmethod
    def _grouped_county_choices():
        groups = {}
        for county in County.objects.order_by("state", "name"):
            groups.setdefault(county.get_state_display(), []).append((county.pk, county.name))
        return [("", "Select a county…")] + list(groups.items())

    def clean(self):
        cleaned_data = super().clean()
        pricing_model = cleaned_data.get("pricing_model")
        if pricing_model == Job.PricingModel.FLAT_RATE and not cleaned_data.get("flat_rate_per_worker"):
            self.add_error("flat_rate_per_worker", "Enter a flat rate per worker.")
        if pricing_model == Job.PricingModel.HOURLY and not cleaned_data.get("hourly_rate"):
            self.add_error("hourly_rate", "Enter an hourly rate.")
        return cleaned_data


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 3, "placeholder": "Write a message…"})}
        labels = {"body": ""}

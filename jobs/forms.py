from django import forms

from .models import ConversationMessage, Job


class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = [
            "county",
            "city",
            "job_date",
            "job_type",
            "workers_needed",
            "weight_lbs",
            "pricing_model",
            "flat_rate_per_worker",
            "hourly_rate",
        ]
        widgets = {
            "county": forms.HiddenInput(),
            "job_date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {"city": "Meeting point / city (optional)"}
        error_messages = {"county": {"required": "Choose a location for this job above."}}

    def clean(self):
        cleaned_data = super().clean()
        pricing_model = cleaned_data.get("pricing_model")
        if pricing_model == Job.PricingModel.FLAT_RATE and not cleaned_data.get("flat_rate_per_worker"):
            self.add_error("flat_rate_per_worker", "Enter a flat rate per worker.")
        if pricing_model == Job.PricingModel.HOURLY and not cleaned_data.get("hourly_rate"):
            self.add_error("hourly_rate", "Enter an hourly rate.")
        return cleaned_data


class ConversationMessageForm(forms.ModelForm):
    class Meta:
        model = ConversationMessage
        fields = ["body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 3, "placeholder": "Write a message…"})}
        labels = {"body": ""}

from django import forms

from .models import (
    CONDITIONAL_RATING_JOB_FLAGS,
    ConversationMessage,
    Job,
    JobRating,
    RATING_CHOICES,
    RATING_FIELD_LABELS,
)


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
            "needs_loading_skill",
            "needs_unloading_skill",
            "needs_packing_skill",
            "needs_equipment_skill",
            "pricing_model",
            "flat_rate_per_worker",
            "hourly_rate",
        ]
        widgets = {
            "county": forms.HiddenInput(),
            "job_date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "city": "Meeting point / city (optional)",
            "needs_loading_skill": "Needs loading skill",
            "needs_unloading_skill": "Needs unloading skill",
            "needs_packing_skill": "Needs packing skill",
            "needs_equipment_skill": "Needs equipment",
        }
        error_messages = {"county": {"required": "Choose a location for this job above."}}

    def clean(self):
        cleaned_data = super().clean()
        pricing_model = cleaned_data.get("pricing_model")
        if pricing_model == Job.PricingModel.FLAT_RATE and not cleaned_data.get("flat_rate_per_worker"):
            self.add_error("flat_rate_per_worker", "Enter a flat rate per worker.")
        if pricing_model == Job.PricingModel.HOURLY and not cleaned_data.get("hourly_rate"):
            self.add_error("hourly_rate", "Enter an hourly rate.")
        return cleaned_data


class JobRatingForm(forms.ModelForm):
    class Meta:
        model = JobRating
        fields = ["professionalism", "punctuality", "moving_skill"] + list(
            CONDITIONAL_RATING_JOB_FLAGS.keys()
        )
        widgets = {
            field: forms.RadioSelect(choices=RATING_CHOICES)
            for field in ["professionalism", "punctuality", "moving_skill"]
            + list(CONDITIONAL_RATING_JOB_FLAGS.keys())
        }
        labels = RATING_FIELD_LABELS

    def __init__(self, *args, job=None, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, job_flag in CONDITIONAL_RATING_JOB_FLAGS.items():
            if not job or not getattr(job, job_flag):
                del self.fields[field_name]
        for field in self.fields.values():
            field.required = True
            # Model fields with choices and no default get an unwanted blank
            # "---------" option auto-prepended by ModelForm; strip it here.
            field.choices = RATING_CHOICES


class ConversationMessageForm(forms.ModelForm):
    class Meta:
        model = ConversationMessage
        fields = ["body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 3, "placeholder": "Write a message…"})}
        labels = {"body": ""}

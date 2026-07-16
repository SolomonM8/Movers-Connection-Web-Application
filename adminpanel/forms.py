from django import forms

from .models import BugReport, Report, SupportMessage


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ["reason", "details"]
        widgets = {"details": forms.Textarea(attrs={"rows": 3, "placeholder": "Any extra details (optional)"})}


class BugReportForm(forms.ModelForm):
    class Meta:
        model = BugReport
        fields = ["description", "page_url"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4, "placeholder": "What happened?"}),
            "page_url": forms.HiddenInput(),
        }


class SupportMessageForm(forms.ModelForm):
    class Meta:
        model = SupportMessage
        fields = ["body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 3, "placeholder": "Write a message..."})}


class BanUserForm(forms.Form):
    ban_reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Reason for ban (shown in the admin panel only)"})
    )

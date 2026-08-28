from django import forms

from .models import AffiliateApplication


CHANNEL_CHOICES = [
    ("website", "Website"), ("blog", "Blog"), ("email", "Email newsletter"),
    ("linkedin", "LinkedIn"), ("youtube", "YouTube"), ("facebook", "Facebook"),
    ("instagram", "Instagram"), ("tiktok", "TikTok"), ("events", "Events"),
]


class AffiliateApplicationForm(forms.ModelForm):
    proposed_channels = forms.MultipleChoiceField(
        choices=CHANNEL_CHOICES, widget=forms.CheckboxSelectMultiple,
        help_text="Select every channel you intend to use.",
    )
    genuine_audience_confirmed = forms.BooleanField(
        label="I confirm that the audience and engagement information is genuine and was not purchased.",
    )
    compliance_confirmed = forms.BooleanField(
        label="I agree to use clear advertising disclosures, avoid spam and make no employment guarantees.",
    )

    class Meta:
        model = AffiliateApplication
        fields = (
            "legal_name", "applicant_type", "country", "website", "public_profiles",
            "audience_size", "audience_countries", "engagement_evidence",
            "audience_description", "proposed_channels", "promotion_plan",
            "previous_experience", "genuine_audience_confirmed", "compliance_confirmed",
        )
        widgets = {
            "country": forms.TextInput(attrs={"maxlength": 2, "placeholder": "GB"}),
            "public_profiles": forms.Textarea(attrs={"rows": 3, "placeholder": "One public URL per line"}),
            "engagement_evidence": forms.Textarea(attrs={"rows": 3}),
            "audience_description": forms.Textarea(attrs={"rows": 3}),
            "promotion_plan": forms.Textarea(attrs={"rows": 4}),
            "previous_experience": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxSelectMultiple):
                continue
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = "form-check-input"
            else:
                widget.attrs["class"] = "form-control" if not isinstance(widget, forms.Select) else "form-select"

    def clean_country(self):
        country = self.cleaned_data["country"].strip().upper()
        if len(country) != 2 or not country.isalpha():
            raise forms.ValidationError("Enter a two-letter country code, such as GB, FR or US.")
        return country

    def clean_public_profiles(self):
        profiles = self.cleaned_data.get("public_profiles", "")
        lines = [line.strip() for line in profiles.splitlines() if line.strip()]
        for line in lines:
            if not line.startswith(("https://", "http://")):
                raise forms.ValidationError("Each public profile must be a complete http:// or https:// URL.")
        return "\n".join(lines)

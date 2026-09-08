from django import forms

from .models import AffiliateApplication


CHANNEL_CHOICES = [
    ("website", "Website"), ("blog", "Blog"), ("email", "Email newsletter"),
    ("linkedin", "LinkedIn"), ("youtube", "YouTube"), ("facebook", "Facebook"),
    ("instagram", "Instagram"), ("tiktok", "TikTok"), ("events", "Events"),
    ("podcast", "Podcast"), ("community", "Community or group"),
    ("direct", "Direct client recommendations"), ("other", "Other"),
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
        label="I will disclose affiliate advertising, avoid spam, self-referrals and employment guarantees.",
    )
    primary_channel = forms.ChoiceField(choices=CHANNEL_CHOICES, help_text="Choose your main channel.")

    for channel_key, channel_label in CHANNEL_CHOICES:
        locals()[f"{channel_key}_url"] = forms.URLField(
            required=False, label=f"{channel_label} public URL",
            help_text=f"Required when {channel_label} is selected. Enter a complete public URL; never provide login details.",
        )
        locals()[f"{channel_key}_audience"] = forms.IntegerField(
            required=False, min_value=0, label=f"{channel_label} followers or monthly audience",
            help_text="Enter a genuine approximate figure. Small specialist audiences remain eligible.",
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
            "engagement_evidence": forms.Textarea(attrs={"rows": 3, "placeholder": "20–100 words: views, comments, shares, open/click rates or attendance, with a date range."}),
            "audience_description": forms.Textarea(attrs={"rows": 3, "placeholder": "40–150 words: who your audience is and why myvalidcv is relevant."}),
            "promotion_plan": forms.Textarea(attrs={"rows": 4, "placeholder": "50–250 words: formats, frequency, first activity and advertising disclosure."}),
            "previous_experience": forms.Textarea(attrs={"rows": 3, "placeholder": "Optional, up to 150 words."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        channel_fields = [name for key, _label in CHANNEL_CHOICES for name in (f"{key}_url", f"{key}_audience")]
        self.order_fields([
            "legal_name", "applicant_type", "country", "website", "public_profiles",
            "audience_size", "audience_countries", "engagement_evidence", "audience_description",
            "proposed_channels", "primary_channel", *channel_fields, "promotion_plan",
            "previous_experience", "genuine_audience_confirmed", "compliance_confirmed",
        ])
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

    def clean(self):
        cleaned = super().clean()
        selected = cleaned.get("proposed_channels") or []
        primary = cleaned.get("primary_channel")
        if primary and primary not in selected:
            self.add_error("primary_channel", "Your primary channel must also be selected.")
        details = {}
        for key in selected:
            url = cleaned.get(f"{key}_url")
            audience = cleaned.get(f"{key}_audience") or 0
            if key not in {"direct", "events"} and not url:
                self.add_error(f"{key}_url", f"Enter the public URL for your selected {key} channel.")
            details[key] = {"url": url or "", "audience": audience, "primary": key == primary}
        cleaned["channel_details_compiled"] = details
        for field, minimum, maximum in (
            ("audience_description", 40, 150), ("engagement_evidence", 20, 100),
            ("promotion_plan", 50, 250), ("previous_experience", 0, 150),
        ):
            words = len((cleaned.get(field) or "").split())
            if words < minimum:
                self.add_error(field, f"Please provide at least {minimum} words ({words} entered).")
            if words > maximum:
                self.add_error(field, f"Please use no more than {maximum} words ({words} entered).")
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.channel_details = self.cleaned_data.get("channel_details_compiled", {})
        if commit:
            instance.save()
        return instance

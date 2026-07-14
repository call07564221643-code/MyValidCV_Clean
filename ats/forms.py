from django import forms
from .models import CV


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"class": "form-control", "accept": ".pdf,.docx,.txt", "multiple": True}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        if isinstance(data, (list, tuple)):
            return [super(MultipleFileField, self).clean(item, initial) for item in data]
        return [super().clean(data, initial)]


class CVUploadForm(forms.ModelForm):
    class Meta:
        model = CV
        fields = ["title", "file"]

        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Software Developer CV"}),
            "file": forms.FileInput(attrs={"class": "form-control", "accept": ".pdf,.docx,.txt"}),
        }


class ATSAnalysisForm(forms.Form):
    SOURCE_CHOICES = [
        ("text", "Paste job description"),
        ("url", "Job advert URL"),
        ("file", "Upload job advert file"),
    ]

    cv = forms.ModelChoiceField(
        queryset=CV.objects.none(),
        required=False,
        empty_label="Select one of your uploaded CVs",
        widget=forms.Select(attrs={"class": "form-select"})
    )
    cv_file = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={"class": "form-control", "accept": ".pdf,.docx,.txt"})
    )
    cv_title = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Optional CV name"})
    )
    job_title = forms.CharField(
        max_length=150,
        required=False,
        help_text="Required only when pasting job text manually. URL/file uploads can be inferred.",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Admin, Django Developer"})
    )
    company = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Optional company name"})
    )
    source_type = forms.ChoiceField(
        choices=SOURCE_CHOICES,
        initial="text",
        required=False,
        widget=forms.HiddenInput()
    )
    job_description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 8, "placeholder": "Paste the full job description here"})
    )
    job_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={"class": "form-control", "placeholder": "https://example.com/job"})
    )
    job_file = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={"class": "form-control", "accept": ".pdf,.docx,.txt"})
    )
    deadline = forms.DateField(
        required=False,
        input_formats=["%d/%m/%Y", "%Y-%m-%d"],
        widget=forms.DateInput(format="%d/%m/%Y", attrs={"class": "form-control", "placeholder": "dd/mm/yyyy"})
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cv"].queryset = CV.objects.filter(user=user)

    def clean(self):
        cleaned_data = super().clean()
        source_type = cleaned_data.get("source_type")
        if cleaned_data.get("job_file"):
            source_type = "file"
        elif cleaned_data.get("job_url"):
            source_type = "url"
        else:
            source_type = "text"
        cleaned_data["source_type"] = source_type

        if not cleaned_data.get("cv") and not cleaned_data.get("cv_file"):
            self.add_error("cv_file", "Attach a CV or select one of your saved CVs.")
        if source_type == "text" and not cleaned_data.get("job_description"):
            self.add_error("job_description", "Paste a job description or choose another source type.")
        if source_type == "url" and not cleaned_data.get("job_url"):
            self.add_error("job_url", "Enter the job advert URL.")
        if source_type == "file" and not cleaned_data.get("job_file"):
            self.add_error("job_file", "Upload a job advert file.")
        return cleaned_data


class EnterpriseBulkAnalysisForm(forms.Form):
    SOURCE_CHOICES = ATSAnalysisForm.SOURCE_CHOICES

    batch_title = forms.CharField(
        max_length=180,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. July Python Developer Shortlist"})
    )
    job_title = forms.CharField(
        max_length=150,
        required=False,
        help_text="Required only when pasting job text manually. URL/file uploads can be inferred.",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Senior Python Developer"})
    )
    company = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Optional company or client"})
    )
    source_type = forms.ChoiceField(
        choices=SOURCE_CHOICES,
        initial="text",
        widget=forms.RadioSelect(attrs={"class": "form-check-input"})
    )
    job_description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 8, "placeholder": "Paste the full job role here"})
    )
    job_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={"class": "form-control", "placeholder": "https://example.com/job"})
    )
    job_file = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={"class": "form-control", "accept": ".pdf,.docx,.txt"})
    )
    cv_files = MultipleFileField(
        help_text="Upload up to 50 CV files for this enterprise batch."
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Optional recruiter notes"})
    )

    def clean_cv_files(self):
        cv_files = self.cleaned_data["cv_files"]
        if len(cv_files) > 50:
            raise forms.ValidationError("The Enterprise plan allows up to 50 CVs per monthly batch.")
        return cv_files

    def clean(self):
        cleaned_data = super().clean()
        source_type = cleaned_data.get("source_type")
        if source_type == "text" and not cleaned_data.get("job_title"):
            self.add_error("job_title", "Enter the job title when pasting the role manually.")
        if source_type == "text" and not cleaned_data.get("job_description"):
            self.add_error("job_description", "Paste a job role or choose another source type.")
        if source_type == "url" and not cleaned_data.get("job_url"):
            self.add_error("job_url", "Enter the job advert URL.")
        if source_type == "file" and not cleaned_data.get("job_file"):
            self.add_error("job_file", "Upload the job role file.")
        return cleaned_data

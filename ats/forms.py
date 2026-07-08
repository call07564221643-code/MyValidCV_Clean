from django import forms
from .models import CV


class CVUploadForm(forms.ModelForm):
    class Meta:
        model = CV
        fields = ["title", "file"]

        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "file": forms.FileInput(attrs={"class": "form-control"}),
        }


class ATSAnalysisForm(forms.Form):
    cv = forms.ModelChoiceField(
        queryset=CV.objects.none(),
        widget=forms.Select(attrs={"class": "form-control"})
    )
    job_title = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    job_description = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 8})
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cv"].queryset = CV.objects.filter(user=user)
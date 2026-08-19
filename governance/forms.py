from django import forms


class OptimisticLockAdminForm(forms.ModelForm):
    loaded_version = forms.IntegerField(widget=forms.HiddenInput, required=False)

    class Meta:
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["loaded_version"].initial = self.instance.version

    def clean(self):
        cleaned = super().clean()
        if self.instance and self.instance.pk:
            current = self._meta.model.objects.only("version").get(pk=self.instance.pk)
            if cleaned.get("loaded_version") != current.version:
                raise forms.ValidationError(
                    "Another administrator updated this record. Reload the page and review their changes before saving."
                )
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        if instance.pk:
            instance.version += 1
        if commit:
            instance.save()
            self.save_m2m()
        return instance

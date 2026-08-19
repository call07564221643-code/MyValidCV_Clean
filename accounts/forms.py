from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django import forms
from django.utils.text import slugify


class CustomUserCreationForm(UserCreationForm):
    username = forms.CharField(
        required=False,
        label='Username (optional)',
        help_text='Leave blank to create one automatically from your email address.',
    )
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'form-control',
                'placeholder': field.label
            })

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account already uses this email address.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        username = (cleaned_data.get('username') or '').strip()
        if not username and email:
            base = slugify(email.split('@', 1)[0]) or 'user'
            base = base[:140]
            username = base
            suffix = 1
            while User.objects.filter(username__iexact=username).exists():
                suffix += 1
                username = f'{base}-{suffix}'
            cleaned_data['username'] = username
            self.instance.username = username
        return cleaned_data


class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Username or email'
        self.fields['username'].widget.attrs.update({
            'autocomplete': 'username',
            'placeholder': 'Username or email',
        })
        self.fields['username'].error_messages['required'] = 'Enter your username or email address.'
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'form-control',
                'placeholder': field.widget.attrs.get('placeholder', field.label)
            })


class UserSettingsForm(forms.ModelForm):
    company_name = forms.CharField(required=False, max_length=180)
    position_title = forms.CharField(required=False, max_length=180, label='Your position')
    email_signature_mode = forms.ChoiceField(
        choices=(('personal', 'Sign with my name, position and company'), ('system', 'Use MyValidCV system-generated email')),
        widget=forms.RadioSelect,
        label='Recruitment email signature',
        required=False,
    )

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        profile = getattr(self.instance, 'profile', None)
        if profile:
            self.fields['company_name'].initial = profile.company_name
            self.fields['position_title'].initial = profile.position_title
            self.fields['email_signature_mode'].initial = profile.email_signature_mode
        self.fields['email'].required = True
        for field in self.fields.values():
            if not isinstance(field.widget, forms.RadioSelect):
                field.widget.attrs.update({'class': 'form-control'})

    def clean(self):
        cleaned_data = super().clean()
        profile = getattr(self.instance, 'profile', None)
        signature_mode = cleaned_data.get('email_signature_mode') or 'personal'
        cleaned_data['email_signature_mode'] = signature_mode
        if profile and profile.plan == 'enterprise' and signature_mode == 'personal':
            if not cleaned_data.get('company_name'):
                self.add_error('company_name', 'Enter your company name or choose the MyValidCV system signature.')
            if not cleaned_data.get('position_title'):
                self.add_error('position_title', 'Enter your position or choose the MyValidCV system signature.')
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=commit)
        profile = user.profile
        profile.company_name = self.cleaned_data.get('company_name', '')
        profile.position_title = self.cleaned_data.get('position_title', '')
        profile.email_signature_mode = self.cleaned_data.get('email_signature_mode', 'personal')
        if commit:
            profile.save(update_fields=['company_name', 'position_title', 'email_signature_mode'])
        return user

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.exclude(pk=self.instance.pk).filter(email__iexact=email).exists():
            raise forms.ValidationError('An account already uses this email address.')
        return email

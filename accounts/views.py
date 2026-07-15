from urllib.parse import urlencode

from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.http import url_has_allowed_host_and_scheme
from django.urls import reverse
from .forms import CustomUserCreationForm, CustomAuthenticationForm, UserSettingsForm
from .models import SocialAuthProvider


def safe_next_url(request, default='dashboard'):
    """Accept local post-login destinations and reject open redirects."""
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return default


def get_social_auth_providers():
    providers = list(SocialAuthProvider.objects.filter(is_active=True))
    if providers:
        return providers

    return [
        {'key': 'google', 'name': 'Google', 'icon_label': 'G', 'is_configured': False},
        {'key': 'linkedin', 'name': 'LinkedIn', 'icon_label': 'in', 'is_configured': False},
    ]


@require_http_methods(['GET', 'POST'])
def register(request):
    """Stage 1 of local registration: validate, create, authenticate, redirect.

    ``form.save()`` writes Django's User row. Calling ``login`` creates the
    authenticated session; the User post-save signal creates UserProfile.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
    redirect_to = safe_next_url(request)
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created successfully. Welcome {username}!')
            login(request, user)
            return redirect(redirect_to)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = CustomUserCreationForm()

    return render(request, 'accounts/register.html', {
        'form': form,
        'next': redirect_to,
        'social_providers': get_social_auth_providers(),
    })


@require_http_methods(['GET', 'POST'])
def login_view(request):
    """Authorise local credentials and establish Django's session cookie."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    redirect_to = safe_next_url(request)
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {username}!')
                return redirect(redirect_to)
    else:
        form = CustomAuthenticationForm()

    return render(request, 'accounts/login.html', {
        'form': form,
        'next': redirect_to,
        'social_providers': get_social_auth_providers(),
    })


def social_login_start(request, provider):
    """Stage 1 of social auth: hand a configured provider to django-allauth.

    Google uses OAuth2 and LinkedIn uses OIDC. The provider callback is handled
    by allauth URLs in ``config.urls``; successful callbacks create/login the
    Django User, after which the same UserProfile signal and dashboard apply.
    """
    provider_key = provider.lower()
    provider_config = SocialAuthProvider.objects.filter(key=provider_key, is_active=True).first()
    fallback_labels = {'google': 'Google', 'linkedin': 'LinkedIn'}
    label = provider_config.name if provider_config else fallback_labels.get(provider_key)
    if not label:
        messages.error(request, 'Unsupported social login provider.')
        return redirect('login')

    client_id = getattr(settings, f'{provider_key.upper()}_OAUTH_CLIENT_ID', '')
    client_secret = getattr(settings, f'{provider_key.upper()}_OAUTH_CLIENT_SECRET', '')
    if not client_id or not client_secret:
        messages.info(request, f'{label} sign-in needs its OAuth client ID and secret configured.')
        return redirect('login')

    next_url = safe_next_url(request, default='dashboard')
    route = 'google_login' if provider_key == 'google' else 'openid_connect_login'
    kwargs = {} if provider_key == 'google' else {'provider_id': 'linkedin'}
    target = reverse(route, kwargs=kwargs)
    return redirect(f'{target}?{urlencode({"next": next_url})}')


@login_required(login_url='login')
@require_http_methods(['POST'])
def logout_view(request):
    """User logout."""
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('home')


@login_required(login_url='login')
@require_http_methods(['GET', 'POST'])
def settings_view(request):
    """Let every customer manage their basic account details."""
    form = UserSettingsForm(request.POST or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Your account settings have been updated.')
        return redirect('account_settings')
    return render(request, 'accounts/settings.html', {
        'form': form,
        'profile': getattr(request.user, 'profile', None),
    })
from urllib.parse import urlencode

from django.conf import settings

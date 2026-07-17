"""
Django settings for MyValidCV project.
"""

import os
from pathlib import Path
from urllib.parse import urlparse

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent


def load_local_env():
    """Load simple KEY=value pairs from .env for local development."""
    env_path = BASE_DIR / '.env'
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_local_env()

def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in {'1', 'true', 'yes', 'on'}


def env_list(name, default=''):
    value = os.environ.get(name, default)
    return [item.strip() for item in value.split(',') if item.strip()]


def unique_list(items):
    seen = set()
    result = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def csrf_origin_from_host(host):
    if not host or host == '*':
        return ''
    if host.startswith('http://') or host.startswith('https://'):
        return host
    if host.startswith('.'):
        return f'https://*{host}'
    return f'https://{host}'


def database_from_url(database_url):
    parsed = urlparse(database_url)
    return {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': parsed.path.lstrip('/'),
        'USER': parsed.username,
        'PASSWORD': parsed.password,
        'HOST': parsed.hostname,
        'PORT': parsed.port or 5432,
        'OPTIONS': {'sslmode': 'require'},
    }


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', '')
if not SECRET_KEY:
    if os.environ.get('DYNO'):
        raise RuntimeError('SECRET_KEY is required on Heroku.')
    SECRET_KEY = 'django-insecure-local-development-only'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env_bool('DEBUG', False)

ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', 'localhost,127.0.0.1')
HEROKU_APP_NAME = os.environ.get('HEROKU_APP_NAME', '')
if HEROKU_APP_NAME:
    ALLOWED_HOSTS.append(f'{HEROKU_APP_NAME}.herokuapp.com')

CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS')
if HEROKU_APP_NAME:
    CSRF_TRUSTED_ORIGINS.append(f'https://{HEROKU_APP_NAME}.herokuapp.com')
CSRF_TRUSTED_ORIGINS.extend(
    origin for origin in (csrf_origin_from_host(host) for host in ALLOWED_HOSTS) if origin
)
CSRF_TRUSTED_ORIGINS = unique_list(CSRF_TRUSTED_ORIGINS)

# Stage 1 - application composition.
# Django imports these apps at startup. An installed app can provide models,
# migrations, admin screens and signals, but it receives web traffic only when
# its URLs are included by config/urls.py.
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.openid_connect',
    
   # Local apps
    'core',
    'accounts',
    'dashboard',
    'ats',
    'subscriptions',
    'payments',
    'analytics',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_EMAIL_VERIFICATION = 'optional'
ACCOUNT_UNIQUE_EMAIL = True
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = False

GOOGLE_OAUTH_CLIENT_ID = os.environ.get('GOOGLE_OAUTH_CLIENT_ID', '')
GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET', '')
LINKEDIN_OAUTH_CLIENT_ID = os.environ.get('LINKEDIN_OAUTH_CLIENT_ID', '')
LINKEDIN_OAUTH_CLIENT_SECRET = os.environ.get('LINKEDIN_OAUTH_CLIENT_SECRET', '')

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APPS': [{
            'client_id': GOOGLE_OAUTH_CLIENT_ID,
            'secret': GOOGLE_OAUTH_CLIENT_SECRET,
            'key': '',
        }],
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
        'OAUTH_PKCE_ENABLED': True,
    },
    'openid_connect': {
        'OAUTH_PKCE_ENABLED': True,
        'APPS': [{
            'provider_id': 'linkedin',
            'name': 'LinkedIn',
            'client_id': LINKEDIN_OAUTH_CLIENT_ID,
            'secret': LINKEDIN_OAUTH_CLIENT_SECRET,
            'settings': {
                'server_url': 'https://www.linkedin.com/oauth',
                'oauth_pkce_enabled': True,
            },
        }],
    },
}

# Stage 2 - shared database connection.
# Every model in every installed app uses this `default` connection unless a
# database router explicitly says otherwise (this project has no such router).
# Heroku should supply DATABASE_URL, which selects PostgreSQL through psycopg.
if env_bool('TEST_USE_SQLITE', False):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'test.sqlite3',
        }
    }
    PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
elif os.environ.get('DATABASE_URL'):
    DATABASES = {
        'default': database_from_url(os.environ['DATABASE_URL'])
    }
elif os.environ.get('DB_NAME'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
            'NAME': os.environ.get('DB_NAME'),
            'USER': os.environ.get('DB_USER'),
            'PASSWORD': os.environ.get('DB_PASSWORD'),
        }
    }
else:
    DATABASES = {
        'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# Media files (Uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Session settings
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 1209600  # 2 weeks
SESSION_SAVE_EVERY_REQUEST = False

# Login/Logout URLs
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'home'

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
# Enterprise batches can contain up to 50 small CVs. Django streams files above
# the per-file memory limit to temporary storage while bounding the full request.
DATA_UPLOAD_MAX_MEMORY_SIZE = 60 * 1024 * 1024
CV_RETENTION_DAYS = int(os.environ.get('CV_RETENTION_DAYS', '30'))

# Stripe payments
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
# A card-like mock form must never be exposed on a public deployment. Tests can
# still override this setting explicitly, while production always uses hosted
# Stripe Checkout (or fails closed when Stripe is not configured).
STRIPE_MOCK_MODE = env_bool('STRIPE_MOCK_MODE', False) if DEBUG else False

# Email receipts
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'receipts@myvalidcv.local')
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() == 'true'

# Maya site assistant. Ollama itself usually has no API key, but hosted
# Ollama-compatible services may require one. Keep secrets in environment
# variables only, never in source control.
OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL', '')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'llama3.1')
OLLAMA_API_KEY = os.environ.get('OLLAMA_API_KEY', '')
OLLAMA_TIMEOUT_SECONDS = int(os.environ.get('OLLAMA_TIMEOUT_SECONDS', '8'))

# Heroku/proxy security
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = env_bool('SESSION_COOKIE_SECURE', not DEBUG)
CSRF_COOKIE_SECURE = env_bool('CSRF_COOKIE_SECURE', not DEBUG)
SECURE_SSL_REDIRECT = env_bool('SECURE_SSL_REDIRECT', not DEBUG)
SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '0' if DEBUG else '31536000'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', False)
SECURE_HSTS_PRELOAD = env_bool('SECURE_HSTS_PRELOAD', False)

# Production logging
# Heroku captures stdout/stderr. Keep request tracebacks visible when DEBUG=False
# so production 500s can be diagnosed from "View logs".
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': True,
        },
        'django.security': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': True,
        },
    },
}

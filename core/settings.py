from pathlib import Path
from decouple import config
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY')
DEBUG      = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'teams',
    'projects',
    'milestones',
    'submissions',
    'reviews',
    'notifications',
    'meetings',
    'dashboard',
    'axes',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'axes.middleware.AxesMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'core.middleware.ActiveUserMiddleware',    # force-logout deactivated accounts
    'core.middleware.LoginRequiredMiddleware', # redirect unauthenticated requests
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL')
    )
}

AUTH_USER_MODEL = 'accounts.User'

LOGIN_URL           = '/accounts/login/'
LOGIN_REDIRECT_URL  = '/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ── Session security ──────────────────────────────────────────────────────────
SESSION_COOKIE_HTTPONLY         = True          # JS cannot read the session cookie
SESSION_COOKIE_SAMESITE         = 'Lax'        # Block cross-site cookie sending
SESSION_COOKIE_SECURE           = not DEBUG    # HTTPS only (auto-off in dev)
SESSION_COOKIE_AGE              = 900          # 15-minute inactivity timeout
SESSION_EXPIRE_AT_BROWSER_CLOSE = True         # Expire on browser close
SESSION_SAVE_EVERY_REQUEST      = True         # Reset 8-hour timer on activity

# ── CSRF ──────────────────────────────────────────────────────────────────────
CSRF_COOKIE_SAMESITE    = 'Lax'
CSRF_COOKIE_SECURE      = not DEBUG            # HTTPS only (auto-off in dev)
CSRF_COOKIE_HTTPONLY    = True                 # JS cannot read CSRF cookie

# ── Security headers ──────────────────────────────────────────────────────────
SECURE_CONTENT_TYPE_NOSNIFF     = True
X_FRAME_OPTIONS                 = 'DENY'
SECURE_REFERRER_POLICY          = 'strict-origin-when-cross-origin'
SECURE_BROWSER_XSS_FILTER       = True
SECURE_SSL_REDIRECT             = not DEBUG    # Force HTTPS in production
SECURE_HSTS_SECONDS             = 0 if DEBUG else 31536000   # 1 year in production
SECURE_HSTS_INCLUDE_SUBDOMAINS  = not DEBUG
SECURE_HSTS_PRELOAD             = not DEBUG

LANGUAGE_CODE = 'en-us'
TIME_ZONE     = 'Asia/Riyadh'
USE_I18N      = True
USE_TZ        = True

STATIC_URL        = '/static/'
STATIC_ROOT       = BASE_DIR / 'staticfiles'
STATICFILES_DIRS  = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# ── django-axes (failed login tracking) ──────────────────────────────────────
AXES_FAILURE_LIMIT        = 5       # lock after 5 failed attempts
AXES_COOLOFF_TIME         = 0.5     # unlock after 30 minutes (in hours)
AXES_LOCKOUT_PARAMETERS   = ['username', 'ip_address']  # lock by username + IP
AXES_RESET_ON_SUCCESS     = True    # clear failure count on successful login

# Silence deployment warnings that are intentionally off in development (DEBUG=True)
if DEBUG:
    SILENCED_SYSTEM_CHECKS = [
        'security.W004',  # HSTS — off in dev by design
        'security.W008',  # SSL redirect — off in dev by design
        'security.W012',  # SESSION_COOKIE_SECURE — off in dev by design
        'security.W016',  # CSRF_COOKIE_SECURE — off in dev by design
        'security.W018',  # DEBUG=True — expected in dev
    ]

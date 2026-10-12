import os
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
ENVIRONMENT = os.getenv("APP_ENV", "production")
LOCAL = ENVIRONMENT in {"development", "test"}
DEBUG = LOCAL and os.getenv("DJANGO_DEBUG", "0") == "1"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if LOCAL and not SECRET_KEY:
    SECRET_KEY = "local-only-key-never-use-in-production-abcdefghijklmnopqrstuvwxyz"
if not LOCAL and (len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5):
    raise ImproperlyConfigured("Set a strong DJANGO_SECRET_KEY (50+ characters).")


def csv_env(name, default=""):
    return [v.strip() for v in os.getenv(name, default).split(",") if v.strip()]


ALLOWED_HOSTS = csv_env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1" if LOCAL else "")
CSRF_TRUSTED_ORIGINS = csv_env("DJANGO_CSRF_TRUSTED_ORIGINS")
if not LOCAL and (not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS):
    raise ImproperlyConfigured("Set explicit DJANGO_ALLOWED_HOSTS.")
if not LOCAL and (
    not CSRF_TRUSTED_ORIGINS
    or any(not origin.startswith("https://") or "*" in origin for origin in CSRF_TRUSTED_ORIGINS)
):
    raise ImproperlyConfigured("Set explicit HTTPS DJANGO_CSRF_TRUSTED_ORIGINS.")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "axes",
    "expenses",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

if os.getenv("DATABASE_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["DATABASE_NAME"],
            "USER": os.environ["DATABASE_USER"],
            "PASSWORD": os.environ["DATABASE_PASSWORD"],
            "HOST": os.environ["DATABASE_HOST"],
            "PORT": os.getenv("DATABASE_PORT", "5432"),
            "CONN_MAX_AGE": 60,
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {"connect_timeout": 5, "sslmode": os.getenv("DATABASE_SSLMODE", "require")},
        }
    }
elif LOCAL:
    DATABASES = {
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}
    }
else:
    raise ImproperlyConfigured("Production requires PostgreSQL DATABASE_* variables.")

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
# Independently limit username and socket IP. Never trust arbitrary forwarded IPs.
# Behind a shared proxy the IP bucket is shared; see the deployment guide.
AXES_LOCKOUT_PARAMETERS = ["username", "ip_address"]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = "registration/locked.html"
LANGUAGE_CODE = "fa-ir"
TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"
SECURE_SSL_REDIRECT = not LOCAL
SECURE_REDIRECT_EXEMPT = [r"^health/live/$", r"^health/ready/$"]
SESSION_COOKIE_SECURE = not LOCAL
CSRF_COOKIE_SECURE = not LOCAL
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 86400
SECURE_HSTS_SECONDS = 31536000 if not LOCAL else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not LOCAL
SECURE_HSTS_PRELOAD = not LOCAL
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
DATA_UPLOAD_MAX_MEMORY_SIZE = 65536
# Enable only behind an ingress which strips and sets X-Forwarded-Proto.
if os.getenv("TRUST_PROXY_SSL_HEADER", "0") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
}
if os.getenv("SENTRY_DSN"):
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from config.telemetry import scrub_event

    sentry_sdk.init(
        dsn=os.environ["SENTRY_DSN"],
        environment=ENVIRONMENT,
        release=os.getenv("APP_RELEASE", "expense-manager@1.0.0"),
        integrations=[DjangoIntegration()],
        send_default_pii=False,
        include_local_variables=False,
        max_request_body_size="never",
        traces_sample_rate=0.0,
        before_send=scrub_event,
    )

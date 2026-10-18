import os
import secrets
import sys
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env(name, default=None, required=False):
    value = os.environ.get(name, default)
    if required and not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _resolve_secret_key():
    """
    Resolve DJANGO_SECRET_KEY without ever killing the web server.

    A missing key used to raise, which made the WSGI worker exit at boot and the
    platform restart the container forever. Instead we fall back to a key that is
    persisted next to the code so sessions survive restarts. Set
    DJANGO_SECRET_KEY in the platform for real deployments; set
    DJANGO_SECRET_KEY_REQUIRED=1 to restore the hard failure.
    """
    value = os.environ.get("DJANGO_SECRET_KEY")
    if value:
        return value

    if "collectstatic" in sys.argv:
        return "django-insecure-build-fallback-key"

    if os.environ.get("DJANGO_SECRET_KEY_REQUIRED", "0") == "1":
        raise RuntimeError("DJANGO_SECRET_KEY environment variable is not set.")

    key_path = Path(os.environ.get("DJANGO_SECRET_KEY_FILE", BASE_DIR / ".secret_key"))
    try:
        if key_path.exists():
            return key_path.read_text().strip()
        generated = secrets.token_urlsafe(64)
        key_path.write_text(generated)
        key_path.chmod(0o600)
        print(f"WARNING: DJANGO_SECRET_KEY not set; generated one at {key_path}.", file=sys.stderr)
        return generated
    except OSError as exc:  # read-only filesystem: still boot, just not persistent
        print(f"WARNING: DJANGO_SECRET_KEY not set and {key_path} is unwritable ({exc}); "
              "using an ephemeral key. Sessions will not survive restarts.", file=sys.stderr)
        return secrets.token_urlsafe(64)


SECRET_KEY = _resolve_secret_key()

DEBUG = False
ALLOWED_HOSTS = [h for h in env("DJANGO_ALLOWED_HOSTS", "*").split(",") if h]
CSRF_TRUSTED_ORIGINS = [o for o in env("CSRF_TRUSTED_ORIGINS", "").split(",") if o]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "django_filters",
    "apps.core",
    "apps.accounts",
    "apps.registry",
    "apps.clinical",
    "apps.investigations",
    "apps.decision_support",
    "apps.audit",
    "apps.web",
]

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

WSGI_APPLICATION = "config.wsgi.application"

if env("DATABASE_URL"):
    DATABASES = {
        "default": dj_database_url.config(conn_max_age=60)
    }
elif env("USE_SQLITE", "0") == "1" or not env("POSTGRES_HOST"):
    # Default to SQLite so a single-container deploy boots with zero configuration.
    # Set POSTGRES_HOST (or DATABASE_URL) to use PostgreSQL.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB", "cdsp"),
            "USER": env("POSTGRES_USER", "cdsp"),
            "PASSWORD": env("POSTGRES_PASSWORD", "cdsp"),
            "HOST": env("POSTGRES_HOST", "db"),
            "PORT": env("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 60,
            "ATOMIC_REQUESTS": True,
        }
    }

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-au"
TIME_ZONE = "UTC"  # store UTC; display in Pacific/Port_Moresby at the UI layer
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 8
CSRF_COOKIE_SAMESITE = "Lax"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],  # deny by default
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"anon": "30/min", "user": "300/min"},
}

LOGIN_URL = "web:login"
LOGIN_REDIRECT_URL = "web:dashboard"
LOGOUT_REDIRECT_URL = "web:login"

SPECTACULAR_SETTINGS = {
    "TITLE": "Breast Cancer Clinical Decision-Support API",
    "DESCRIPTION": "Clinical decision support only. Not a diagnostic device. Synthetic data in non-production.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

from pathlib import Path

import environ

BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
BASE_DIR = BACKEND_ROOT

env = environ.Env(
    DEBUG=(bool, True),
)

environ.Env.read_env(PROJECT_ROOT / ".env")


SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DEBUG")

ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1"],
)


INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "axes",
    "accounts",
    "candidates",
    "recruitment",
    "interviews",
    "calling",
    "agents",
    "auditlog",
]


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "axes.middleware.AxesMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "config.urls"


TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [FRONTEND_ROOT / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST", default="localhost"),
        "PORT": env("DB_PORT", default="5432"),
        "CONN_MAX_AGE": 60,
    }
}


AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]


PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": ("django.contrib.auth.password_validation.MinimumLengthValidator"),
        "OPTIONS": {
            "min_length": 10,
        },
    },
    {
        "NAME": ("django.contrib.auth.password_validation.CommonPasswordValidator"),
    },
    {
        "NAME": ("django.contrib.auth.password_validation.NumericPasswordValidator"),
    },
]


AXES_FAILURE_LIMIT = 5
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]


CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}


LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Karachi"
USE_I18N = True
USE_TZ = True


STATIC_URL = "static/"
STATIC_ROOT = PROJECT_ROOT / "var" / "static"
STATICFILES_DIRS = [FRONTEND_ROOT / "static"]

MEDIA_URL = "media/"
MEDIA_ROOT = PROJECT_ROOT / "var" / "media"


LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"


SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

EMAIL_VERIFICATION_LIFETIME_SECONDS = env.int(
    "EMAIL_VERIFICATION_LIFETIME_SECONDS",
    default=86400,
)
EMAIL_VERIFICATION_REQUEST_LIMIT = env.int(
    "EMAIL_VERIFICATION_REQUEST_LIMIT",
    default=3,
)
EMAIL_VERIFICATION_REQUEST_WINDOW_SECONDS = env.int(
    "EMAIL_VERIFICATION_REQUEST_WINDOW_SECONDS",
    default=900,
)
EMAIL_VERIFICATION_RESEND_LIMIT = env.int(
    "EMAIL_VERIFICATION_RESEND_LIMIT",
    default=3,
)
EMAIL_VERIFICATION_RESEND_WINDOW_SECONDS = env.int(
    "EMAIL_VERIFICATION_RESEND_WINDOW_SECONDS",
    default=3600,
)
EMAIL_VERIFICATION_INVALID_ATTEMPT_LIMIT = env.int(
    "EMAIL_VERIFICATION_INVALID_ATTEMPT_LIMIT",
    default=10,
)
EMAIL_VERIFICATION_INVALID_ATTEMPT_WINDOW_SECONDS = env.int(
    "EMAIL_VERIFICATION_INVALID_ATTEMPT_WINDOW_SECONDS",
    default=3600,
)

CURRENT_AI_CONSENT_POLICY_VERSION = env(
    "CURRENT_AI_CONSENT_POLICY_VERSION",
    default="ai-processing-v1",
)


# File-upload security limits
MAX_RESUME_UPLOAD_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2_621_440
FILE_UPLOAD_PERMISSIONS = 0o600
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o700

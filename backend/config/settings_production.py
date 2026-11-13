from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

from .settings import *


def _require_non_empty_list(name):
    values = tuple(value.strip() for value in env.list(name, default=[]) if value.strip())
    if not values:
        raise ImproperlyConfigured(f"{name} must be explicitly configured.")
    return list(values)


def _validate_hosts(hosts):
    for host in hosts:
        if (
            host == "*"
            or host.startswith(".")
            or "://" in host
            or "/" in host
            or any(character.isspace() for character in host)
        ):
            raise ImproperlyConfigured("ALLOWED_HOSTS contains an unsafe value.")


def _validate_csrf_origins(origins):
    for origin in origins:
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
            or "*" in parsed.netloc
        ):
            raise ImproperlyConfigured(
                "CSRF_TRUSTED_ORIGINS must contain explicit HTTPS origins."
            )


if env.bool("DEBUG", default=False):
    raise ImproperlyConfigured("Production settings cannot run with DEBUG enabled.")
DEBUG = False
# The hosted deployment is text-only. Do not permit requests to initialize
# local Piper, Faster-Whisper, or Silero adapters even if an environment value
# is supplied accidentally.
SPEECH_FEATURE_ENABLED = False

_unsafe_secret_values = {
    "change-me",
    "replace-me",
    "replace-with-a-long-random-secret",
}
if len(SECRET_KEY) < 50 or SECRET_KEY.lower() in _unsafe_secret_values:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be a non-default production value of at least 50 characters."
    )

ALLOWED_HOSTS = _require_non_empty_list("ALLOWED_HOSTS")
_validate_hosts(ALLOWED_HOSTS)

CSRF_TRUSTED_ORIGINS = _require_non_empty_list("CSRF_TRUSTED_ORIGINS")
_validate_csrf_origins(CSRF_TRUSTED_ORIGINS)

database_config = DATABASES["default"]
if database_config.get("ENGINE") not in {
    "django.db.backends.postgresql",
    "django.db.backends.postgresql_psycopg2",
}:
    raise ImproperlyConfigured("Production requires PostgreSQL.")
if not all(
    database_config.get(key) for key in ("NAME", "USER", "PASSWORD", "HOST", "PORT")
):
    raise ImproperlyConfigured(
        "Production PostgreSQL configuration is incomplete."
    )

database_sslmode = env("DATABASE_SSLMODE", default="require")
if database_sslmode not in {"require", "verify-ca", "verify-full"}:
    raise ImproperlyConfigured("Production PostgreSQL must use an approved SSL mode.")
database_config.setdefault("OPTIONS", {})["sslmode"] = database_sslmode
database_config["CONN_HEALTH_CHECKS"] = True
database_config["CONN_MAX_AGE"] = env.int("DATABASE_CONN_MAX_AGE", default=60)

_redis_url = env("REDIS_URL")
redis_url = urlsplit(_redis_url)
if redis_url.scheme != "rediss" or not redis_url.hostname:
    raise ImproperlyConfigured("Production Redis must use an explicit rediss:// URL.")

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [_redis_url],
            "capacity": 1500,
            "expiry": 60,
        },
    }
}

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": ("whitenoise.storage.CompressedManifestStaticFilesStorage"),
    },
}

SECURE_SSL_REDIRECT = env.bool(
    "SECURE_SSL_REDIRECT",
    default=True,
)
if not SECURE_SSL_REDIRECT:
    raise ImproperlyConfigured("Production HTTPS redirection cannot be disabled.")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

SECURE_HSTS_SECONDS = env.int(
    "SECURE_HSTS_SECONDS",
    default=0,
)
if SECURE_HSTS_SECONDS < 0:
    raise ImproperlyConfigured("SECURE_HSTS_SECONDS cannot be negative.")
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=False,
)
SECURE_HSTS_PRELOAD = env.bool(
    "SECURE_HSTS_PRELOAD",
    default=False,
)
if SECURE_HSTS_SECONDS == 0 and (
    SECURE_HSTS_INCLUDE_SUBDOMAINS or SECURE_HSTS_PRELOAD
):
    raise ImproperlyConfigured(
        "HSTS subdomain and preload flags require a positive HSTS duration."
    )
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

if env.bool("DJANGO_TRUST_PROXY_HEADERS", default=False):
    SECURE_PROXY_SSL_HEADER = (
        "HTTP_X_FORWARDED_PROTO",
        "https",
    )
    USE_X_FORWARDED_HOST = True

MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "OPTIONS": {
            "host": env("EMAIL_HOST", default="localhost"),
            "port": env.int("EMAIL_PORT", default=587),
            "use_tls": env.bool("EMAIL_USE_TLS", default=True),
            "username": env("EMAIL_HOST_USER", default=""),
            "password": env("EMAIL_HOST_PASSWORD", default=""),
            "timeout": env.int("EMAIL_TIMEOUT", default=10),
        },
    },
}

DEFAULT_FROM_EMAIL = env(
    "DEFAULT_FROM_EMAIL",
    default="noreply@example.com",
)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured": {
            "format": ("{asctime} {levelname} {name} {module} {message}"),
            "style": "{",
        },
        "safe_request": {
            "format": "{asctime} {levelname} {name} request_event",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "structured",
        },
        "safe_request_console": {
            "class": "logging.StreamHandler",
            "formatter": "safe_request",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django.security": {
            "handlers": ["safe_request_console"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["safe_request_console"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.server": {
            "handlers": ["safe_request_console"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["safe_request_console"],
            "level": "ERROR",
            "propagate": False,
        },
        "axes": {
            "handlers": ["safe_request_console"],
            "level": "WARNING",
            "propagate": False,
        },
        "channels": {
            "handlers": ["safe_request_console"],
            "level": "WARNING",
            "propagate": False,
        },
        "channels_redis": {
            "handlers": ["safe_request_console"],
            "level": "WARNING",
            "propagate": False,
        },
        "daphne": {
            "handlers": ["safe_request_console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

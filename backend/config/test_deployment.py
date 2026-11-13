import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.test import Client
from django.urls import reverse

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"

PRODUCTION_ENV_KEYS = {
    "ALLOWED_HOSTS",
    "CSRF_TRUSTED_ORIGINS",
    "DATABASE_CONN_MAX_AGE",
    "DATABASE_SSLMODE",
    "DATABASE_URL",
    "DB_HOST",
    "DB_NAME",
    "DB_PASSWORD",
    "DB_PORT",
    "DB_USER",
    "DEBUG",
    "DJANGO_READ_DOT_ENV",
    "DJANGO_SECRET_KEY",
    "DJANGO_SETTINGS_MODULE",
    "DJANGO_TRUST_PROXY_HEADERS",
    "REDIS_URL",
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    "SECURE_HSTS_PRELOAD",
    "SECURE_HSTS_SECONDS",
    "SECURE_SSL_REDIRECT",
    "SPEECH_FEATURE_ENABLED",
}

VALID_PRODUCTION_ENV = {
    "ALLOWED_HOSTS": "demo.example.test",
    "CSRF_TRUSTED_ORIGINS": "https://demo.example.test",
    "DATABASE_SSLMODE": "require",
    "DATABASE_URL": (
        "postgresql://test-user:test-password@db.example.test:5432/test-database"
    ),
    "DEBUG": "False",
    "DJANGO_READ_DOT_ENV": "False",
    "DJANGO_SECRET_KEY": (
        "unit-test-only-9W!f3Q@p7L#v2N$x8R%k4T&z6M*e1C-b5Y_s0G+h"
    ),
    "DJANGO_SETTINGS_MODULE": "config.settings_production",
    "DJANGO_TRUST_PROXY_HEADERS": "True",
    "REDIS_URL": "rediss://test-user:test-password@cache.example.test:6379/0",
    "SECURE_HSTS_INCLUDE_SUBDOMAINS": "False",
    "SECURE_HSTS_PRELOAD": "False",
    "SECURE_HSTS_SECONDS": "0",
    "SECURE_SSL_REDIRECT": "True",
    "SPEECH_FEATURE_ENABLED": "True",
}

SETTINGS_PROBE = """
from django.conf import settings

assert settings.DEBUG is False
assert settings.SESSION_COOKIE_SECURE is True
assert settings.CSRF_COOKIE_SECURE is True
assert settings.SECURE_SSL_REDIRECT is True
assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"
assert settings.DATABASES["default"]["OPTIONS"]["sslmode"] == "require"
assert settings.DATABASES["default"]["CONN_HEALTH_CHECKS"] is True
assert settings.CHANNEL_LAYERS["default"]["BACKEND"] == (
    "channels_redis.core.RedisChannelLayer"
)
assert settings.SECURE_PROXY_SSL_HEADER == (
    "HTTP_X_FORWARDED_PROTO",
    "https",
)
assert settings.SECURE_HSTS_SECONDS == 0
assert settings.SECURE_HSTS_INCLUDE_SUBDOMAINS is False
assert settings.SECURE_HSTS_PRELOAD is False
assert settings.SPEECH_FEATURE_ENABLED is False
assert settings.STORAGES["staticfiles"]["BACKEND"] == (
    "whitenoise.storage.CompressedManifestStaticFilesStorage"
)
assert "{message}" not in settings.LOGGING["formatters"]["safe_request"]["format"]
for logger_name in (
    "axes",
    "channels",
    "channels_redis",
    "daphne",
    "django.db.backends",
    "django.request",
    "django.security",
    "django.server",
):
    assert settings.LOGGING["loggers"][logger_name]["handlers"] == [
        "safe_request_console"
    ]
assert not hasattr(settings, "DATABASE_URL")
assert not hasattr(settings, "REDIS_URL")
print("production-settings-ok")
"""


def _run_production_settings(overrides=None, missing=()):
    process_env = os.environ.copy()
    for key in PRODUCTION_ENV_KEYS:
        process_env.pop(key, None)
    process_env.update(VALID_PRODUCTION_ENV)
    process_env.update(overrides or {})
    for key in missing:
        process_env.pop(key, None)
    process_env["PYTHONPATH"] = str(BACKEND_ROOT)
    return subprocess.run(
        [sys.executable, "-c", SETTINGS_PROBE],
        cwd=PROJECT_ROOT,
        env=process_env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_health_endpoint_is_fixed_safe_and_cache_disabled():
    response = Client().get(reverse("health"))

    assert response.status_code == 200
    assert response.content == b"ok\n"
    assert response.headers["Content-Type"] == "text/plain; charset=utf-8"
    assert response.headers["Cache-Control"] == "no-store"
    for forbidden_text in (
        b"database",
        b"redis",
        b"secret",
        b"version",
        b"settings",
    ):
        assert forbidden_text not in response.content.lower()


def test_health_endpoint_allows_head_and_rejects_mutation_methods():
    client = Client()

    head_response = client.head(reverse("health"))
    assert head_response.status_code == 200
    assert head_response.content == b""

    for method in (client.post, client.put, client.patch, client.delete):
        assert method(reverse("health")).status_code == 405


def test_protected_media_is_not_served_by_project_urls():
    response = Client().get("/media/private-document.pdf")

    assert response.status_code == 404


def test_valid_production_settings_are_fail_closed_and_secure():
    result = _run_production_settings()

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "production-settings-ok"


@pytest.mark.parametrize(
    ("overrides", "missing"),
    [
        ({}, ("DJANGO_SECRET_KEY",)),
        ({"DJANGO_SECRET_KEY": "replace-with-a-long-random-secret"}, ()),
        ({}, ("ALLOWED_HOSTS",)),
        ({"ALLOWED_HOSTS": "*"}, ()),
        ({}, ("CSRF_TRUSTED_ORIGINS",)),
        ({"CSRF_TRUSTED_ORIGINS": "http://demo.example.test"}, ()),
        ({"DEBUG": "True"}, ()),
        ({"DATABASE_URL": "sqlite:///not-production.sqlite3"}, ()),
        ({"DATABASE_SSLMODE": "disable"}, ()),
        ({"REDIS_URL": "redis://cache.example.test:6379/0"}, ()),
        ({"SECURE_SSL_REDIRECT": "False"}, ()),
        ({"SECURE_HSTS_PRELOAD": "True"}, ()),
    ],
)
def test_unsafe_production_configuration_is_rejected(overrides, missing):
    result = _run_production_settings(overrides=overrides, missing=missing)

    assert result.returncode != 0
    combined_output = f"{result.stdout}\n{result.stderr}".lower()
    assert "production-settings-ok" not in combined_output
    for private_value in (
        VALID_PRODUCTION_ENV["DJANGO_SECRET_KEY"],
        VALID_PRODUCTION_ENV["DATABASE_URL"],
        VALID_PRODUCTION_ENV["REDIS_URL"],
    ):
        assert private_value.lower() not in combined_output

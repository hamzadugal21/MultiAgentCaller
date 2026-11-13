# ruff: noqa: E402, F403, I001
"""Fail-closed settings for the disposable local QA database.

This module intentionally does not read ``.env`` and cannot fall back to the
ordinary development database.  It is for synthetic, explicitly authorized QA
only; model-driven actions remain disabled unless a later QA adapter enables a
separate, narrow feature gate.
"""

import os
import re
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ImproperlyConfigured(f"{name} is required for isolated QA settings.")
    return value


def _validate_qa_database_url(database_url: str) -> None:
    parsed = urlsplit(database_url)
    database_name = parsed.path.lstrip("/")
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ImproperlyConfigured("QA_DATABASE_URL must use PostgreSQL.")
    if not parsed.hostname or not parsed.username or not database_name:
        raise ImproperlyConfigured("QA_DATABASE_URL is incomplete.")
    if not database_name.startswith("hireflow_qa_"):
        raise ImproperlyConfigured("QA database name must use the hireflow_qa_ prefix.")
    if not parsed.username.startswith("hireflow_qa_"):
        raise ImproperlyConfigured("QA database role must use the hireflow_qa_ prefix.")


if os.environ.get("HIREFLOW_QA_MODE") != "1":
    raise ImproperlyConfigured("HIREFLOW_QA_MODE=1 is required for QA settings.")
if os.environ.get("QA_DATABASE_ISOLATION_ACK") != "disposable":
    raise ImproperlyConfigured("QA_DATABASE_ISOLATION_ACK=disposable is required.")

_qa_database_url = _require("QA_DATABASE_URL")
_qa_secret_key = _require("QA_DJANGO_SECRET_KEY")
_validate_qa_database_url(_qa_database_url)

# Set these before importing the shared settings module so this process never
# reads .env or considers the ordinary DATABASE_URL/DB_* configuration.
os.environ["DJANGO_READ_DOT_ENV"] = "False"
os.environ["DJANGO_SECRET_KEY"] = _qa_secret_key
os.environ["DATABASE_URL"] = _qa_database_url

from .settings import *  # noqa: E402,F403


DEBUG = False
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]
MAILERS = {
    "default": {
        "BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    }
}
MEDIA_ROOT = PROJECT_ROOT / "var" / "qa-media"  # noqa: F405
ADMIN_INTERFACE_ENABLED = False

_qa_tunnel_host = os.environ.get("QA_TUNNEL_HOST", "").strip().lower()
if _qa_tunnel_host:
    if (
        len(_qa_tunnel_host) > 253
        or not re.fullmatch(
            r"(?=.{1,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
            r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?",
            _qa_tunnel_host,
        )
    ):
        raise ImproperlyConfigured("QA_TUNNEL_HOST must be one exact hostname.")
    ALLOWED_HOSTS.append(_qa_tunnel_host)
    CSRF_TRUSTED_ORIGINS = [f"https://{_qa_tunnel_host}"]
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
else:
    CSRF_TRUSTED_ORIGINS = []
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_SSL_REDIRECT = False

# These switches are accepted only inside this already fail-closed QA settings
# module.  The adapter and browser endpoint still re-check the exact database,
# role, authorization, consent, tenant, state, and audit boundaries.
QA_MODEL_ACTIONS_ENABLED = os.environ.get("HIREFLOW_QA_MODEL_ACTIONS") == "1"
QA_BROWSER_VOICE_ENABLED = os.environ.get("HIREFLOW_QA_BROWSER_VOICE") == "1"

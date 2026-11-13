"""Subprocess checks for the QA settings fail-closed contract without a DB connection."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _run_with(
    environment: dict[str, str],
    statement: str | None = None,
) -> subprocess.CompletedProcess[str]:
    child_environment = os.environ.copy()
    child_environment.update(environment)
    child_environment["HIREFLOW_QA_MODEL_ACTIONS"] = environment.get(
        "HIREFLOW_QA_MODEL_ACTIONS", ""
    )
    child_environment["HIREFLOW_QA_BROWSER_VOICE"] = environment.get(
        "HIREFLOW_QA_BROWSER_VOICE", ""
    )
    child_environment["DJANGO_SETTINGS_MODULE"] = "config.settings_qa"
    backend_root = str(Path(__file__).resolve().parent.parent)
    child_environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, (backend_root, child_environment.get("PYTHONPATH")))
    )
    return subprocess.run(
        [
            sys.executable,
            "-c",
            statement
            or (
                "import django; django.setup(); from django.conf import settings; "
                "print(settings.DATABASES['default']['NAME'], "
                "settings.QA_MODEL_ACTIONS_ENABLED, "
                "settings.QA_BROWSER_VOICE_ENABLED)"
            ),
        ],
        capture_output=True,
        check=False,
        env=child_environment,
        text=True,
    )


def test_qa_settings_fail_closed_without_explicit_isolation_configuration():
    result = _run_with(
        {
            "HIREFLOW_QA_MODE": "",
            "QA_DATABASE_ISOLATION_ACK": "",
            "QA_DATABASE_URL": "",
            "QA_DJANGO_SECRET_KEY": "",
        }
    )

    assert result.returncode != 0
    assert "HIREFLOW_QA_MODE=1 is required" in result.stderr


def test_qa_settings_accept_only_synthetic_qa_configuration_without_enabling_actions():
    result = _run_with(
        {
            "HIREFLOW_QA_MODE": "1",
            "QA_DATABASE_ISOLATION_ACK": "disposable",
            "QA_DATABASE_URL": (
                "postgresql://hireflow_qa_runner:synthetic-password@127.0.0.1:5432/"
                "hireflow_qa_release"
            ),
            "QA_DJANGO_SECRET_KEY": "q" * 64,
        }
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "hireflow_qa_release False False"


def test_qa_settings_require_explicit_narrow_activation_switches():
    result = _run_with(
        {
            "HIREFLOW_QA_MODE": "1",
            "QA_DATABASE_ISOLATION_ACK": "disposable",
            "QA_DATABASE_URL": (
                "postgresql://hireflow_qa_runner:synthetic-password@127.0.0.1:5432/"
                "hireflow_qa_release"
            ),
            "QA_DJANGO_SECRET_KEY": "q" * 64,
            "HIREFLOW_QA_MODEL_ACTIONS": "1",
            "HIREFLOW_QA_BROWSER_VOICE": "1",
        }
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "hireflow_qa_release True True"


def test_qa_settings_rejects_non_qa_database_or_role_names():
    result = _run_with(
        {
            "HIREFLOW_QA_MODE": "1",
            "QA_DATABASE_ISOLATION_ACK": "disposable",
            "QA_DATABASE_URL": "postgresql://developer:synthetic@127.0.0.1:5432/development",
            "QA_DJANGO_SECRET_KEY": "q" * 64,
        }
    )

    assert result.returncode != 0
    assert "QA database name must use the hireflow_qa_ prefix" in result.stderr


def test_qa_tunnel_configuration_is_exact_https_and_hides_admin():
    result = _run_with(
        {
            "HIREFLOW_QA_MODE": "1",
            "QA_DATABASE_ISOLATION_ACK": "disposable",
            "QA_DATABASE_URL": (
                "postgresql://hireflow_qa_runner:synthetic-password@127.0.0.1:5432/"
                "hireflow_qa_release"
            ),
            "QA_DJANGO_SECRET_KEY": "q" * 64,
            "QA_TUNNEL_HOST": "demo.example.test",
        },
        (
            "import django; django.setup(); from django.conf import settings; "
            "from django.urls import get_resolver; "
            "print(settings.ALLOWED_HOSTS[-1], settings.CSRF_TRUSTED_ORIGINS[0], "
            "settings.SESSION_COOKIE_SECURE, settings.CSRF_COOKIE_SECURE, "
            "settings.SECURE_SSL_REDIRECT, settings.ADMIN_INTERFACE_ENABLED, "
            "any(str(pattern.pattern) == 'admin/' for pattern in "
            "get_resolver().url_patterns))"
        ),
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == (
        "demo.example.test https://demo.example.test True True True False False"
    )

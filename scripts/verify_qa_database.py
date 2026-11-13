"""Read-only proof that config.settings_qa targets the disposable QA database."""

# ruff: noqa: E402

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import django
from django.conf import settings
from django.core.management import call_command
from django.db import connection

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_qa")

django.setup()


def main() -> None:
    expected_database = "hireflow_qa_release"
    expected_role = "hireflow_qa_runner"
    configured_name = settings.DATABASES["default"]["NAME"]
    configured_user = settings.DATABASES["default"]["USER"]
    if configured_name != expected_database:
        raise RuntimeError("QA database name guard failed.")
    if configured_user != expected_role:
        raise RuntimeError("QA database role guard failed.")

    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database(), current_user")
        database_name, database_user = cursor.fetchone()

    if database_name != configured_name or database_user != configured_user:
        raise RuntimeError("Connected database identity does not match QA configuration.")

    call_command("check", verbosity=0)
    print(
        "QA isolation verified: "
        f"database={database_name}; role={database_user}; "
        "settings=config.settings_qa; "
        f"model_actions_enabled={settings.QA_MODEL_ACTIONS_ENABLED}"
    )


if __name__ == "__main__":
    main()

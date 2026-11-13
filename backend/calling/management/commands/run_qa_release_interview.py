"""Run the isolated synthetic QA release interview evidence workflow."""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from calling.qa_release import (
    QaReleaseError,
    prepare_manual_browser_fixture,
    run_qa_release_interview,
    validate_qa_label,
)


class Command(BaseCommand):
    help = "Run real local AI components against the isolated disposable QA database."

    def add_arguments(self, parser):
        parser.add_argument("--label")
        parser.add_argument("--prepare-manual", action="store_true")

    def handle(self, *args, **options):
        label = options["label"] or f"QA_RELEASE_{timezone.now():%Y%m%d%H%M%S}"
        try:
            validate_qa_label(label)
            report = {"automated": run_qa_release_interview(label=label)}
            if options["prepare_manual"]:
                report["manual"] = prepare_manual_browser_fixture(
                    label=f"QA_MANUAL_{timezone.now():%Y%m%d%H%M%S}"
                )
        except QaReleaseError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(json.dumps(report, indent=2, sort_keys=True))

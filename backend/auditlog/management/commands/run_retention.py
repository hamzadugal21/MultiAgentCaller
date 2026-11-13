from django.core.management.base import BaseCommand, CommandError

from auditlog.retention_services import (
    CURRENT_RETENTION_POLICY_VERSION,
    DEFAULT_BATCH_SIZE,
    DEFAULT_RETENTION_DAYS,
    RETENTION_RESOURCE_TYPES,
    RetentionServiceError,
    apply_retention,
    preview_retention,
)


class Command(BaseCommand):
    help = "Preview or apply a bounded privacy-safe retention batch."

    def add_arguments(self, parser):
        parser.add_argument(
            "category",
            choices=tuple(RETENTION_RESOURCE_TYPES),
        )
        parser.add_argument(
            "--policy-version",
            default=CURRENT_RETENTION_POLICY_VERSION,
        )
        parser.add_argument(
            "--retention-days",
            type=int,
            default=DEFAULT_RETENTION_DAYS,
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
        )
        parser.add_argument(
            "--run-id",
            help="UUID used to make an applied run replay-safe.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply anonymization. Without this flag the command is read-only.",
        )

    def handle(self, *args, **options):
        if options["apply"] and not options["run_id"]:
            raise CommandError(
                "Applied retention requires an explicit --run-id UUID."
            )
        try:
            if options["apply"]:
                result = apply_retention(
                    category=options["category"],
                    run_id=options["run_id"],
                    policy_version=options["policy_version"],
                    retention_days=options["retention_days"],
                    batch_size=options["batch_size"],
                )
            else:
                result = preview_retention(
                    category=options["category"],
                    policy_version=options["policy_version"],
                    retention_days=options["retention_days"],
                    batch_size=options["batch_size"],
                )
        except RetentionServiceError as error:
            raise CommandError(str(error)) from error

        self.stdout.write(
            " ".join(
                (
                    f"category={result.category}",
                    f"mode={result.execution_mode}",
                    f"result={result.result}",
                    f"eligible={result.eligible_count}",
                    f"processed={result.processed_count}",
                    f"replayed={str(result.replayed).lower()}",
                )
            )
        )

# Release Readiness

This is a local release-candidate handoff, not evidence of a production release. Manual QA, QA bug fixes, Git commit/push, provider setup, and deployment require later explicit approval.

## Implemented and locally validated

- Candidate signup, email verification, profile/consent, protected resume workflow, job application, scheduling, and simulated interview lifecycle.
- Recruiter company-scoped job, applicant, interview, and human-review workflows; administrator provisioning through authorized routes/Django admin.
- Deterministic rubric evaluation is advisory only. An active verified recruiter with company review authority must explicitly finalize `advance` or `decline`; no model or evaluation score can make an employment decision.
- Immutable audit, consent, finalized-evaluation, rubric, and retention evidence. Retention is bounded and dry-run by default.
- Fixed `/health/` liveness response, protected-media non-routing, fail-closed production settings, lightweight Render build/start artifacts, and simulated-only hosted-demo boundary.

## Local validation

Run from the repository root:

```powershell
$env:OPENBLAS_NUM_THREADS = "1"
.\.venv\Scripts\python.exe backend\manage.py check
.\.venv\Scripts\python.exe backend\manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m ruff check backend ai_system ml tests
git diff --check
git status --short --branch
```

The latest complete local run passed 308 tests. See [test coverage](../../tests/README.md) and [production preflight](PRODUCTION_PREFLIGHT.md) for scope and limitations.

## Production preflight and migration precautions

Follow [Production Preflight](PRODUCTION_PREFLIGHT.md) before any provider action. Configure private values only in the provider environment; never track them. Required future variable names are:

- `DJANGO_SETTINGS_MODULE`, `DJANGO_READ_DOT_ENV`, `DJANGO_SECRET_KEY`, `DEBUG`
- `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`
- `DATABASE_URL` or `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`; `DATABASE_SSLMODE`, `DATABASE_CONN_MAX_AGE`
- `REDIS_URL`, `DJANGO_TRUST_PROXY_HEADERS`, `SECURE_SSL_REDIRECT`
- `SECURE_HSTS_SECONDS`, `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD`
- `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_TIMEOUT`, `DEFAULT_FROM_EMAIL`

Before an approved production migration, review `showmigrations`, `makemigrations --check --dry-run`, and `migrate --plan` against an authorized isolated database. Take a provider-managed, verified backup first once backup capability exists. Do not reverse immutable-trigger or data migrations casually; use a reviewed forward corrective migration or an isolated restore rehearsal. No production migration, backup, or restore has been run by this repository.

## Retention procedure

Preview only; this is read-only:

```powershell
.\.venv\Scripts\python.exe backend\manage.py run_retention simulated_interview_answers
```

The alternate supported category is `transcript_segments`. Applying a run requires explicit `--apply` plus an operator-supplied replay-safe `--run-id`; it must follow documented policy review, a dry-run count, and authorized operational approval. Do not run retention against real data automatically. See [incident response](../security/INCIDENT_RESPONSE.md) and the [backup/restore checklist](../../database/docs/BACKUP_RESTORE.md).

## Expected warnings and deferred provider work

- `check --deploy` is expected to report HSTS subdomain/preload warnings while staged rollout keeps those flags disabled. Do not silence them prematurely.
- Local Windows validation emits two Daphne asyncio deprecations and one pytest-cache permission warning; these do not invalidate the 308-test result.
- External protected media storage, malware scanning, email delivery, provider monitoring, backups/restore rehearsal, Neon/Upstash/Render setup, a database migration execution plan, post-deployment smoke testing, and a public URL are not configured.
- The hosted demonstration, if approved later, must use only synthetic data and clearly label its interview as simulated.

## Next phase

Perform manual cross-browser/UI and operator QA. Address only reproduced QA defects, then obtain separate approval for a reviewed commit, GitHub push, and any provider/deployment activity.

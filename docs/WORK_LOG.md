# Work Log

Append new entries in chronological order. Do not rewrite historical entries. Record verified outcomes, exact test results, warnings, errors, blockers, and commit identifiers without including secrets or private candidate data.

## 2026-10-22 — Week 1 secure foundation

Commit `7b3581c` — `chore: establish secure week 1 foundation`

- Created the Django 6.1/PostgreSQL project foundation and seven domain applications.
- Added the custom email user model, candidate-only public signup, three roles, role dashboards, Argon2, login throttling configuration, and POST-only logout.
- Added core recruitment, interview, call, agent, audit, candidate, resume, consent, evaluation, escalation, and retention schema foundations.
- Added resume format/size checks, privacy-safe authentication auditing, keyed audit hashes, and PostgreSQL protection against audit-event update/deletion.
- Added development/production settings, requirements, templates, stylesheet, security policy, and automated tests.

## 2026-10-22 — Case-insensitive email integrity

Commit `3e9ec9b` — `fix: enforce case-insensitive user emails`

- Canonicalized complete email addresses to lowercase in `UserManager.create_user()`.
- Added PostgreSQL constraint `accounts_user_email_ci_unique` using `Lower("email")`.
- Added migration `accounts.0002_user_accounts_user_email_ci_unique` without rewriting applied history.
- Added tests for manager normalization, direct-save duplicate rejection, and case-insensitive signup rejection.

## 2026-10-22 — Project structure reorganization

Commit `614aba6` — `chore: reorganize project structure`

- Moved Django management, configuration, applications, migrations, and app tests under `backend/` while preserving app labels and Git history.
- Moved shared templates and static source assets under `frontend/`.
- Added `database/`, `ai_system/`, `ml/`, `docs/`, `scripts/`, `tests/`, and `var/` responsibility boundaries.
- Updated Django roots, root environment-file path, template/static/media paths, pytest Python path, Ruff source root, ignore rules, and README commands.
- Verified template/static discovery, PostgreSQL access, ASGI/WSGI imports, migration history, and absence of legacy duplicate paths.

## 2026-10-22 — Week 1 validation baseline

- Tests: **28 passed**.
- Django system check: **0 issues**.
- Migration drift: **no changes detected**.
- Applied accounts migrations: `0001_initial`, `0002_user_accounts_user_email_ci_unique`.
- Dependency check: **no broken requirements**.
- Ruff: **all checks passed**.
- Known non-failing warnings: two Daphne warnings about Windows asyncio policy APIs deprecated for Python 3.16, and one pytest-cache permission warning.
- Week 1 completion: **100%**.
- Week 2 product completion: **0%**.
- Overall four-week completion: **25%**.

## 2026-10-22 — Persistent project context

- Added the repository-wide agent operating guide, authoritative AI handoff, four-week roadmap, decision log, append-only work log, and architecture guide.
- Added an ignored local four-prompt counter under `var/agent-state/` with a tracked directory placeholder.
- No Week 2 product functionality was implemented.
- Validation: Django system check reported 0 issues; migration check reported no changes; 28 tests passed with 3 known warnings in 2.92 seconds; dependency check found no broken requirements; Ruff passed; Git diff check passed.
- Commit message: `docs: add persistent project context`. The containing commit is discoverable from Git; subsequent agents must verify `HEAD` before work.

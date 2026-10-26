# AI Handoff — MultiAgent Recruitment Caller

This is the authoritative handoff document for another AI assistant. Read it after `AGENTS.md`, then verify its snapshot against Git and the source before changing code.

Last updated: 2026-10-26 (Asia/Karachi)

## Project identity

- **Project:** MultiAgent Recruitment Caller
- **Purpose:** Build a browser-based recruitment platform in which specialized AI agents can conduct, assist with, evaluate, monitor, and audit candidate screening interviews.
- **Final intended product:** A secure recruitment workflow covering candidate onboarding, job applications, scheduling, browser-based voice screening, local speech processing, coordinated specialist agents, evidence-based evaluation, escalation, auditability, and mandatory human review for consequential employment decisions.
- **Implementation constraint:** Python-first.
- **Technology constraint:** Prefer free and open-source components; do not introduce paid or closed dependencies without an explicit decision.
- **Delivery target:** Four development weeks, tracked in `docs/ROADMAP.md`.

## Current Git and progress snapshot

- **Current branch:** `feat/week-2-core-workflows`
- **Current commit:** `eb48e50` — lightweight Render deployment plan.
- **Latest clean checkpoint:** `eb48e50` — lightweight Render deployment plan.
- **Week 1:** 100% complete.
- **Current week:** Week 2, 10% complete. Milestones 2.1A and 2.1B are implemented and validated; 2.1B remains uncommitted pending review.
- **Overall project:** 28% complete.
- **Automated tests:** 97 passing; the Milestone 2.1B focused audit/candidate/recruitment suite has 77 passing tests.

## Current technology stack

The pinned foundation includes Python 3.14, Django 6.1, Django Channels/Daphne, PostgreSQL through Psycopg, django-environ, WhiteNoise, django-axes, django-ratelimit, Argon2, pytest, and Ruff. Current settings configure django-axes, Argon2, PostgreSQL, and WhiteNoise. Production settings configure Redis-backed Channels and Django 6.1 `MAILERS`; development uses an in-memory channel layer and console mailer.

The requirements also pin the planned local speech and ML stack: Faster Whisper for speech-to-text, Piper for text-to-speech, Silero VAD for voice activity detection, PyTorch, Sentence Transformers, scikit-learn, spaCy, NumPy, and pandas. These dependencies being present does not mean the inference or voice pipeline is implemented.

`requirements/render.txt` is the lightweight dependency boundary for a future free Render demonstration. It includes only `requirements/base.txt`, excludes the local AI/ML stack, and does not configure deployment. The initial hosted demonstration is planned to label AI-call behavior as simulated; the real Whisper/Piper/PyTorch pipeline remains locally runnable.

The persistent plan and deferred decisions are documented in the [Render deployment plan](development/RENDER_DEPLOYMENT.md). Deployment remains a Week 4 task.

## Repository structure

```text
frontend/      Django templates, shared static assets, design references
backend/       Django configuration, applications, migrations, app tests
database/      Database documentation, diagrams, safe utilities
ai_system/     Planned orchestration, agents, prompts, safety, approvals
ml/            Planned pipelines, training, inference, evaluation, artifacts
docs/          Architecture, roadmap, decisions, work log, handoff
scripts/       Development, maintenance, and validation utilities
tests/         Future integration, system, and end-to-end tests
var/           Ignored runtime media, static output, logs, local agent state
```

Root files retain repository-wide configuration and documentation. Django templates live in `frontend/templates/`, shared source assets in `frontend/static/`, migrations in `backend/<app>/migrations/`, and runtime output under `var/`.

## Django applications

- `accounts`: Custom email-based user model, candidate-only public signup, login/logout, three roles, role dashboards, authentication auditing, and automatic candidate-profile creation.
- `candidates`: Candidate profiles, skills, resume metadata/storage models, safe randomized upload paths, and PDF/DOCX size and structure validation.
- `recruitment`: Companies, recruiter profiles, job postings, skill requirements, applications, interview questions, and job FAQs.
- `interviews`: Interview schedules, evaluation rubrics and criteria, candidate evaluations, criterion scores, and reviewer fields.
- `calling`: Call sessions, transcript segments, call events, performance metrics, consent, and optional recording metadata.
- `agents`: Versioned agent definitions, runs, actions, handoffs, approval fields, and escalation records.
- `auditlog`: Immutable keyed audit events, security incidents, data-retention records, and the in-review append-only consent-history implementation. PostgreSQL triggers protect audit events and consent evidence from database-level update and deletion.

Only the accounts web flow currently has implemented views and templates. Most other applications currently provide schema foundations, not finished product workflows.

## Planned AI agents

- **Calling Orchestrator:** Coordinate the call lifecycle, turn-taking, timeouts, and handoffs.
- **Candidate Profile Agent:** Retrieve consented candidate and application context without exposing unnecessary private data.
- **Interview Agent:** Ask approved questions and manage conversational interview flow.
- **Evaluation Agent:** Produce rubric-based scores, evidence, confidence, and an advisory recommendation for human review.
- **FAQ Agent:** Answer approved job and process questions from controlled sources.
- **Scheduling Agent:** Assist with interview availability, confirmation, and rescheduling.
- **Safety Agent:** Semantically detect prompt injection, bias, coercion, privacy concerns, and unsafe conversational content. It supplements and cannot override deterministic policy enforcement.
- **Escalation Agent:** Route candidate requests, uncertainty, safety events, and technical failures to authorized humans.

These agents have database definitions but no operational orchestration implementation yet. Auditing is not a generative-agent responsibility: ordinary Python domain services decide when an event is mandatory, validate a strict event specification, sanitize its metadata, and persist the immutable event. Future agent runtimes may only submit structured events through narrow service adapters.

## PostgreSQL architecture

PostgreSQL is the required relational database. Django migrations define UUID-centered recruitment, interview, call, agent, and audit records with foreign keys, indexes, uniqueness rules, conditional constraints, and numeric/range checks. Important database safeguards include case-insensitive user-email uniqueness and PostgreSQL protection against updating or deleting audit events. The current Milestone 2.1B worktree adds append-only consent evidence and a matching PostgreSQL immutability trigger; its migrations are applied locally but remain uncommitted pending review. Django migrations must remain with their applications.

`auditlog.ConsentRecord` has UUID `id`; protected candidate, optional application, optional interview schedule, and optional recorded-by relationships; `general_ai_processing`/`ai_interview` type; `granted`/`revoked` action; policy version; `profile`/`application`/`interview_confirmation`/`admin_assisted`/`legacy_import` source; timezone-aware recorded time; globally unique UUID idempotency key; and optional request/correlation UUIDs. Named checks prevent invalid general/interview context and require a non-legacy actor. Named indexes cover candidate/type/time, application/type/time, schedule/time, action/time, request ID, and correlation ID.

## Authentication and authorization

- The custom `accounts.User` model authenticates with email and has candidate, recruiter, and administrator roles.
- `UserManager.create_user()` canonicalizes the complete email address to lowercase.
- A `Lower("email")` database constraint prevents case-variant duplicates.
- Public signup accepts candidate fields only and always creates a candidate.
- Recruiter and administrator accounts require trusted administrative creation.
- Role checks are enforced server-side for the existing dashboards.
- Password hashing prefers Argon2, with Django password validation enabled.
- django-axes limits repeated login failures; logout is POST-only and CSRF-protected by Django middleware.

## Security rules and boundaries

- Never access or commit `.env`; only placeholder configuration belongs in `.env.example`.
- Never place secrets or private candidate content in Git or context documentation.
- Resume files are limited to PDF/DOCX, 5 MB, structurally checked, randomly renamed, and stored under runtime media rather than static assets.
- Malware scanning is required before production document processing and is not yet implemented.
- Candidate AI-processing and interview consent Boolean fields are mutable caches. The current Milestone 2.1B implementation derives effective consent from append-only, policy-versioned history and requires workflow enforcement before processing.
- Call recording defaults to disabled and requires explicit consent before it can be enabled.
- Agent tools must be allowlisted and sensitive actions must use approval records.
- Authentication events are sanitized and audit events are hash-protected and immutable.
- Production requires HTTPS, secure cookies, trusted origins, restricted database access, protected media, encrypted backups, monitoring, and dependency review.

## Human-approval boundary

AI may screen, summarize, score against an approved rubric, and recommend. It must not autonomously make a final hiring, rejection, or other consequential employment decision. An authorized human must review relevant evidence and approve the final outcome. Safety, privacy, bias, policy, high-impact, and low-confidence cases must be escalated.

## Completed work

- Secure Django foundation and pinned requirements.
- PostgreSQL schema and migrations for all seven applications.
- Email authentication, candidate-only signup, role-aware dashboards, and POST-only logout.
- Argon2 hashing, login throttling configuration, secure upload validation, authentication audit events, and immutable audit protection.
- Database-level case-insensitive email uniqueness.
- Django 6.1 development and production `MAILERS` configuration.
- Monorepo-style frontend/backend/database/AI/ML/docs/scripts/tests/var structure with updated paths and tooling.
- Persistent agent operating guide, handoff, roadmap, decision log, work log, architecture documentation, and ignored local prompt counter.
- Deterministic domain-audit service with a frozen caller command, immutable Week 2 event registry, specification-owned canonical actions, required and allowed metadata rules, safe UUID normalization, bounded payload validation, and safe mandatory-failure exceptions.
- Validated lightweight Render dependency manifest that includes only the base Django web stack and deliberately excludes heavy local AI/ML dependencies.
- Append-only, policy-versioned consent evidence with deterministic grant/revoke/resolution services, mutable cache synchronization, strict actor/scope checks, idempotent replay, deterministic auditing, legacy import, and PostgreSQL immutability protection. This work is validated but remains uncommitted pending review.

## Current work

Milestone 2.1A is implemented, validated, and checkpointed on `feat/week-2-core-workflows`. The lightweight Render dependency manifest and persistent deployment plan are committed at `eb48e50`; the approved web dependencies are installed in the local environment and the Render manifest still resolves only through `requirements/base.txt`.

Milestone 2.1B is implemented, validated, and ready for its milestone commit. Migrations `auditlog.0003` through `0005` are applied locally. The focused suite passes 77 tests and the complete suite passes 97 tests. Email verification has not begun.

## Pending work

- Review and commit Milestone 2.1B append-only consent history.
- Later Milestone 2.1 policy work: email-verification foundation, shared authorization conventions, and explicit workflow transition services.
- Candidate profile editing and secure resume upload workflow.
- Recruiter/company/job and application management workflows.
- Interview scheduling, invitations, consent enforcement, and evaluation UI.
- Channels/Redis browser call transport and call state management.
- Local STT, TTS, and VAD integration.
- Agent orchestration, tool allowlists, safety checks, escalation, and human approvals.
- Evaluation pipeline, cross-application tests, end-to-end tests, observability, retention jobs, production hardening, and deployment documentation.

## Known limitations and blockers

- **Limitations:** Non-account applications are primarily schema foundations. No operational voice pipeline, agent orchestration, ML inference, malware scanner, recruiter workflow, candidate resume UI, or end-to-end workflow exists yet. Development Channels is in-memory. No Figma screenshots have been supplied yet.
- **Blockers:** None recorded. External design screenshots will be needed before pixel-accurate frontend implementation.

## Known non-failing warnings

The validated pytest run emits three warnings:

- Two Daphne deprecation warnings for Windows asyncio policy APIs planned for removal in Python 3.16.
- One pytest-cache permission warning for `.pytest_cache`; it does not affect test execution.

On the current low-memory Windows host, the unbounded pytest process twice failed during native-library allocation. Final focused and complete runs passed with the process-local `OPENBLAS_NUM_THREADS=1` setting; project configuration and runtime behavior were not changed.

## Validation commands

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe backend\manage.py check
.\.venv\Scripts\python.exe backend\manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m ruff check backend
git diff --check
git status --short
```

## Exact next recommended task

Review the validated Milestone 2.1B diff and approve a focused consent-history commit. Do not begin email verification until that approval.

Relevant files:

- `backend/auditlog/models.py`
- `backend/auditlog/consent_services.py`
- `backend/auditlog/services.py`
- `backend/auditlog/migrations/0003_consentrecord.py`
- `backend/auditlog/migrations/0004_backfill_legacy_consents.py`
- `backend/auditlog/migrations/0005_protect_consent_records.py`
- `backend/auditlog/test_consent_services.py`
- `requirements/production.txt`
- `docs/development/RENDER_DEPLOYMENT.md`
- `docs/DECISIONS.md`

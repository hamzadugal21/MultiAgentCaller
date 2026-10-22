# AI Handoff — MultiAgent Recruitment Caller

This is the authoritative handoff document for another AI assistant. Read it after `AGENTS.md`, then verify its snapshot against Git and the source before changing code.

Last updated: 2026-10-22 23:13 +05:00 (Asia/Karachi)

## Project identity

- **Project:** MultiAgent Recruitment Caller
- **Purpose:** Build a browser-based recruitment platform in which specialized AI agents can conduct, assist with, evaluate, monitor, and audit candidate screening interviews.
- **Final intended product:** A secure recruitment workflow covering candidate onboarding, job applications, scheduling, browser-based voice screening, local speech processing, coordinated specialist agents, evidence-based evaluation, escalation, auditability, and mandatory human review for consequential employment decisions.
- **Implementation constraint:** Python-first.
- **Technology constraint:** Prefer free and open-source components; do not introduce paid or closed dependencies without an explicit decision.
- **Delivery target:** Four development weeks, tracked in `docs/ROADMAP.md`.

## Current Git and progress snapshot

- **Current branch:** `main`
- **Current commit:** `HEAD` (the commit containing this handoff; resolve with `git rev-parse --short HEAD`).
- **Latest clean checkpoint entering this documentation task:** `614aba6` — project structure reorganization.
- **Week 1:** 100% complete.
- **Current week:** Week 2, 0% product functionality complete. The directory preparation does not count as a Week 2 feature.
- **Overall project:** 25% complete, based on one completed week out of the four-week plan.
- **Automated tests:** 28 passing.

## Current technology stack

The pinned foundation includes Python 3.14, Django 6.1, Django Channels/Daphne, PostgreSQL through Psycopg, django-environ, WhiteNoise, django-axes, django-ratelimit, Argon2, pytest, and Ruff. Current settings configure django-axes, Argon2, PostgreSQL, and WhiteNoise. Production settings configure Redis-backed Channels and Django 6.1 `MAILERS`; development uses an in-memory channel layer and console mailer.

The requirements also pin the planned local speech and ML stack: Faster Whisper for speech-to-text, Piper for text-to-speech, Silero VAD for voice activity detection, PyTorch, Sentence Transformers, scikit-learn, spaCy, NumPy, and pandas. These dependencies being present does not mean the inference or voice pipeline is implemented.

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
- `auditlog`: Immutable keyed audit events, security incidents, and data-retention records. PostgreSQL triggers protect audit events from database-level update and deletion.

Only the accounts web flow currently has implemented views and templates. Most other applications currently provide schema foundations, not finished product workflows.

## Planned AI agents

- **Calling Orchestrator:** Coordinate the call lifecycle, turn-taking, timeouts, and handoffs.
- **Candidate Profile Agent:** Retrieve consented candidate and application context without exposing unnecessary private data.
- **Interview Agent:** Ask approved questions and manage conversational interview flow.
- **Evaluation Agent:** Produce rubric-based scores, evidence, confidence, and an advisory recommendation for human review.
- **FAQ Agent:** Answer approved job and process questions from controlled sources.
- **Scheduling Agent:** Assist with interview availability, confirmation, and rescheduling.
- **Safety Agent:** Detect safety, privacy, bias, prompt-injection, and policy risks and block unsafe actions.
- **Escalation Agent:** Route candidate requests, uncertainty, safety events, and technical failures to authorized humans.
- **Audit Agent:** Record privacy-safe agent actions, decisions, handoffs, and outcomes.

These agents have database definitions but no operational orchestration implementation yet.

## PostgreSQL architecture

PostgreSQL is the required relational database. Django migrations define UUID-centered recruitment, interview, call, agent, and audit records with foreign keys, indexes, uniqueness rules, conditional constraints, and numeric/range checks. Important database safeguards include case-insensitive user-email uniqueness and PostgreSQL protection against updating or deleting audit events. Django migrations must remain with their applications.

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
- Candidate AI-processing and interview consent fields exist; workflows must enforce them before processing.
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

## Current work

No product feature implementation is active. The repository is ready for the first Week 2 product task.

## Pending work

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

The current pytest run emits three warnings:

- Two Daphne deprecation warnings for Windows asyncio policy APIs planned for removal in Python 3.16.
- One pytest-cache permission warning for `.pytest_cache`; it does not affect test execution.

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

Implement the first Week 2 vertical slice: authenticated candidate profile editing and secure resume upload/replacement, enforcing candidate ownership, consent, existing PDF/DOCX validation, one-active-resume semantics, protected runtime storage, and audit events. Add focused model/form/view/authorization/upload tests before expanding recruiter workflows.

Relevant files:

- `backend/candidates/models.py`
- `backend/candidates/validators.py`
- `backend/candidates/views.py`
- `backend/candidates/tests.py`
- `backend/accounts/views.py`
- `backend/accounts/urls.py`
- `frontend/templates/accounts/candidate_dashboard.html`
- `frontend/templates/`
- `frontend/static/`
- `backend/config/settings.py`
- `backend/auditlog/models.py`
- `SECURITY.md`

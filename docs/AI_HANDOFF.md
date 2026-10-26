# AI Handoff — MultiAgent Recruitment Caller

This is the authoritative handoff document for another AI assistant. Read it after `AGENTS.md`, then verify its snapshot against Git and the source before changing code.

Last updated: 2026-10-27 (Asia/Karachi)

## Project identity

- **Project:** MultiAgent Recruitment Caller
- **Purpose:** Build a browser-based recruitment platform in which specialized AI agents can conduct, assist with, evaluate, monitor, and audit candidate screening interviews.
- **Final intended product:** A secure recruitment workflow covering candidate onboarding, job applications, scheduling, browser-based voice screening, local speech processing, coordinated specialist agents, evidence-based evaluation, escalation, auditability, and mandatory human review for consequential employment decisions.
- **Implementation constraint:** Python-first.
- **Technology constraint:** Prefer free and open-source components; do not introduce paid or closed dependencies without an explicit decision.
- **Delivery target:** Four development weeks, tracked in `docs/ROADMAP.md`.

## Current Git and progress snapshot

- **Current branch:** `feat/week-3-ai-interview-runtime`
- **Current commit:** `2bd2710` — deterministic Week 3 call-session foundation.
- **Latest validated product checkpoint:** `2bd2710` — Week 3 Milestone 3.1.
- **Week 1:** 100% complete.
- **Current week:** Week 3, 15% complete. Milestone 3.1 is committed and validated.
- **Overall project:** 54% complete.
- **Automated tests:** 165 passing, including the Week 2 pre-interview suite and deterministic call-session foundation.

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
tests/         Cross-application integration/security; future system/E2E tests
var/           Ignored runtime media, static output, logs, local agent state
```

Root files retain repository-wide configuration and documentation. Django templates live in `frontend/templates/`, shared source assets in `frontend/static/`, migrations in `backend/<app>/migrations/`, and runtime output under `var/`.

## Django applications

- `accounts`: Custom email-based user model, candidate-only public signup, login/logout, three roles, role dashboards, authentication auditing, automatic candidate-profile creation, and secure email-verification services/pages.
- `candidates`: Candidate profile/consent pages, skills, protected resume upload/download, randomized storage, PDF/DOCX validation and bounded extraction, processing transitions, and successful-only replacement.
- `recruitment`: Administrator company/recruiter provisioning, company-scoped job management, skills/questions/FAQs, candidate browsing, secure applications, withdrawal, and audit-derived history.
- `interviews`: Secure invitations, confirmation, rescheduling, cancellation/expiry, plus planned evaluation rubrics/criteria, candidate evaluations, scores, and reviewer fields.
- `calling`: Deterministic call-session creation/lifecycle/authorization/auditing plus schema foundations for transcript segments, call events, performance metrics, and disabled-by-default recording metadata.
- `agents`: Versioned agent definitions, runs, actions, handoffs, approval fields, and escalation records.
- `auditlog`: Immutable keyed audit events, security incidents, data-retention records, and append-only policy-versioned consent history. PostgreSQL triggers protect audit events and consent evidence from database-level update and deletion.

Accounts, candidates, recruitment, and interview scheduling provide tested server-rendered Week 2 workflows. Calling now has a tested deterministic domain foundation, while its simulated browser experience is next. Agents, speech execution, and evaluation remain later Week 3/4 work.

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

PostgreSQL is the required relational database. Django migrations define UUID-centered recruitment, interview, call, agent, and audit records with foreign keys, indexes, uniqueness rules, conditional constraints, and numeric/range checks. Important safeguards include case-insensitive unique user email, immutable audit/consent evidence, inactive-by-default replacement resumes, one current schedule per application, one pending reschedule request, and unique invitation idempotency/token digests. All Week 2 migrations are applied and drift-free. Django migrations remain with their applications.

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
- Email verification uses signed expiring single-purpose tokens, keyed token/email digests, single-use row-locked consumption, resend invalidation, configurable throttles, and deterministic privacy-safe audit events. Raw tokens are returned only to the delivery caller and are never stored.

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
- Append-only, policy-versioned consent evidence with deterministic grant/revoke/resolution services, mutable cache synchronization, strict actor/scope checks, idempotent replay, deterministic auditing, legacy import, and PostgreSQL immutability protection.
- Secure email-verification challenge, pages, and enforcement with HMAC email binding, signed 24-hour tokens, resend/email-change invalidation, single-use consumption, cache-backed rate limits, and deterministic audits.
- Deterministic transition tables and transactional services for job, application, interview-schedule, resume-processing, and consent state. Resume activation preserves the prior active resume until processing succeeds; scheduling has minimal invitation-expiry and reschedule-request persistence.
- Candidate-only profile editing and consent controls, generic verification request/resend/confirmation pages, protected resume upload/download, SHA-256 metadata, bounded PDF/DOCX extraction outside long transactions, and successful-only resume replacement.
- Administrator-controlled company/recruiter provisioning boundaries, recruiter verification/capabilities, company-isolated job management and publishing transitions, job skills/questions/FAQs, and authenticated-candidate-only open-job browsing.
- Secure application creation with verified-email/open-job/deadline/active-resume checks, duplicate prevention, optional append-only AI-interview consent, scoped recruiter/candidate views, audit-derived history, and pre-call withdrawal that cancels the current schedule transactionally.
- Secure interview invitation and scheduling with company-scoped recruiter authority, signed single-purpose tokens stored only as keyed-HMAC digests, persisted expiry/delivery/idempotency state, current-consent and verified-email confirmation, candidate reschedule requests, recruiter approval/rejection, cancellation/expiry, email notification, and deterministic audits.
- Deterministic call-session creation and lifecycle with one session per confirmed schedule, persisted idempotency, simulated mode, current-consent gates, candidate/company authorization, scheduled-window enforcement, explicit terminal states, database constraints, transactional audit rollback, and legacy-state migration.

## Current work

Week 2 remains complete at checkpoint `064100a`. Week 3 Milestone 3.1 is committed at `2bd2710` on `feat/week-3-ai-interview-runtime`; the full suite passes 165 tests. The current task is Milestone 3.2: a deterministic, server-rendered simulated interview lifecycle using approved job questions.

## Pending work

- Candidate/recruiter simulated interview pages and deterministic question/answer progression.
- Channels/Redis browser call transport and authorized real-time state updates.
- Local STT, TTS, and VAD integration.
- Agent orchestration, tool allowlists, safety checks, escalation, and human approvals.
- Operational agent/evaluation pipeline, observability, retention jobs, production hardening, and deployment execution.

## Known limitations and blockers

- **Limitations:** No simulated interview UI, operational voice pipeline, WebSocket call transport, agent orchestration, ML inference, malware scanner, final human-review UI, or production deployment exists yet. Development Channels is in-memory. Resume checks are structural parsing controls, not malware scanning. Templates remain intentionally minimal because no Figma screenshots have been supplied.
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

Implement Week 3 Milestone 3.2: the deterministic HTTP/server-rendered simulated interview lifecycle with approved job questions, candidate-only answer submission, recruiter-safe progress visibility, POST/CSRF enforcement, and privacy-safe audits. Do not begin WebSockets until this flow is validated.

Relevant files:

- `backend/calling/models.py`
- `backend/calling/services.py`
- `backend/calling/test_call_session_services.py`
- `backend/recruitment/models.py`
- `backend/interviews/models.py`
- `backend/agents/models.py`
- `backend/auditlog/services.py`
- `ai_system/README.md`
- `docs/ARCHITECTURE.md`
- `docs/ROADMAP.md`

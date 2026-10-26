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
- **Current commit:** `da6cf21` — deterministic interview coordinator.
- **Latest validated product checkpoint:** `da6cf21` — Week 3 Milestone 3.5.
- **Week 1:** 100% complete.
- **Current week:** Week 3, 90% complete. Milestones 3.1 through 3.5 are committed and validated.
- **Overall project:** 73% complete.
- **Automated tests:** 186 passing, including the Week 2 pre-interview suite, simulated interview, WebSocket security, voice-adapter fallback, and deterministic coordinator coverage.

## Current technology stack

The pinned foundation includes Python 3.14, Django 6.1, Django Channels/Daphne, PostgreSQL through Psycopg, django-environ, WhiteNoise, django-axes, django-ratelimit, Argon2, pytest, and Ruff. Current settings configure django-axes, Argon2, PostgreSQL, and WhiteNoise. Production settings configure Redis-backed Channels and Django 6.1 `MAILERS`; development uses an in-memory channel layer and console mailer.

The requirements also pin the planned local speech and ML stack: Faster Whisper for speech-to-text, Piper for text-to-speech, Silero VAD for voice activity detection, PyTorch, Sentence Transformers, scikit-learn, spaCy, NumPy, and pandas. These dependencies being present does not mean the inference or voice pipeline is implemented.

Typed transient-audio interfaces and optional lazy local adapters now exist for Silero VAD, Faster Whisper, and the pinned piper-plus package. They load models locally only when called and return safe structured unavailable/failure results. This is an adapter boundary, not an operational browser voice pipeline; no model was downloaded, selected, trained, or executed during validation.

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
- `calling`: Deterministic call-session creation/lifecycle/authorization/auditing, server-rendered simulated question/answer progression, authenticated session-scoped WebSocket status transport, and schema foundations for transcript segments, call events, performance metrics, and disabled-by-default recording metadata.
- `agents`: Versioned agent definitions, runs, actions, handoffs, approval fields, and escalation records.
- `auditlog`: Immutable keyed audit events, security incidents, data-retention records, and append-only policy-versioned consent history. PostgreSQL triggers protect audit events and consent evidence from database-level update and deletion.

Accounts, candidates, recruitment, interview scheduling, and the simulated interview provide tested server-rendered workflows. Calling has a deterministic domain, HTTP fallback, and authorized status WebSocket. Agents, speech execution, and evaluation remain later Week 3/4 work.

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

Week 3 now includes a model-free `DeterministicInterviewCoordinator`, not a generative agent. It exposes only status, start, pause, cancel, and submit-answer commands through a candidate-scoped Django adapter. It selects approved job questions one at a time and returns fixed structured directives. The broader specialist-agent runtime remains planned.

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
- Candidate-owned simulated interview pages with approved active job questions, bounded private answers, deterministic ordering and completion, idempotent submission, pause/resume/cancel controls, recruiter/admin safe progress pages, POST/CSRF enforcement, and answer-free audit metadata.
- Authenticated Channels status WebSocket with exact candidate/company/admin authorization, per-session groups, reauthorization before delivery, server-derived allowlisted payloads, event isolation, safe disconnect handling, and optional on-commit broadcasting. Development remains in-memory; production retains the existing Redis channel layer.
- Typed transient audio and optional local Silero VAD, Faster Whisper STT, and piper-plus TTS adapters with lazy/local-only loading, bounded text/audio handling, fixed safe failure codes, unsupported-input/output fallbacks, and no recording persistence.
- Versioned deterministic interview coordinator with an immutable five-action allowlist, candidate-only narrow tool adapter, approved-question sequencing, structured stop/failure results, and no generative, messaging, arbitrary-data, or employment-decision authority.

## Current work

Week 2 remains complete at checkpoint `064100a`. Week 3 Milestones 3.1 through 3.5 are committed at `2bd2710`, `473ea99`, `a64e9be`, `40789e2`, and `da6cf21` on `feat/week-3-ai-interview-runtime`; the full suite passes 186 tests. The next task is Milestone 3.6: safety, escalation, failure recovery, and complete Week 3 integration/security validation.

## Pending work

- Week 3 safety/escalation integration and complete simulated runtime security validation.
- Browser audio transport and live integration of the optional STT, TTS, and VAD adapters remain beyond the deterministic Week 3 baseline unless safely completed after required controls.
- Agent orchestration, tool allowlists, safety checks, escalation, and human approvals.
- Operational agent/evaluation pipeline, observability, retention jobs, production hardening, and deployment execution.

## Known limitations and blockers

- **Limitations:** No operational voice pipeline, audio transport, agent orchestration, generative inference, malware scanner, final human-review UI, or production deployment exists yet. Voice adapters are optional boundaries and were tested with injected synthetic engines, not live hardware or models. The current WebSocket carries status only, and the interview remains an explicitly labelled text simulation; development Channels is in-memory. Resume checks are structural parsing controls, not malware scanning. Templates remain intentionally minimal because no Figma screenshots have been supplied.
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

Implement Week 3 Milestone 3.6: deterministic timeout/expiry and unsafe-state recovery, explicit privacy-safe human escalation flags, service-failure fallback, consent-revocation/candidate-exit coverage, and a complete confirmed-interview-to-completed-simulation integration/security test. Do not add hiring outcomes, generative models, audio recording, or deployment.

Relevant files:

- `backend/calling/models.py`
- `backend/calling/services.py`
- `ai_system/voice/interfaces.py`
- `ai_system/interview/coordinator.py`
- `ai_system/README.md`
- `backend/calling/services.py`
- `backend/calling/models.py`
- `backend/calling/coordinator_tools.py`
- `backend/agents/models.py`
- `backend/auditlog/services.py`
- `backend/recruitment/models.py`
- `backend/interviews/models.py`
- `backend/agents/models.py`
- `backend/auditlog/services.py`
- `ai_system/README.md`
- `docs/ARCHITECTURE.md`
- `docs/ROADMAP.md`

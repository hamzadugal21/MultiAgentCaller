# Decision Log

Append new decisions; do not rewrite accepted historical decisions unless a later entry explicitly supersedes one.

## 2026-10-22 — Python-first ecosystem

- **Decision:** Implement the application and AI/ML integration primarily in Python.
- **Reason:** Django, speech, ML, and evaluation components can share one well-supported ecosystem.
- **Consequences:** Prefer Python libraries and services; justify non-Python components when they materially improve the system.
- **Status:** Accepted.

## 2026-10-22 — Free and open-source components

- **Decision:** Prefer free and open-source technology throughout the project.
- **Reason:** Keep the system locally operable, inspectable, and free from mandatory paid APIs.
- **Consequences:** Paid or closed services require an explicit future decision and must not become silent dependencies.
- **Status:** Accepted.

## 2026-10-22 — Django backend

- **Decision:** Use Django 6.1 with server-rendered views and Django Channels.
- **Reason:** Django provides mature authentication, ORM, security middleware, forms, templates, and administration in Python.
- **Consequences:** Backend code, configuration, migrations, and application tests live under `backend/`.
- **Status:** Accepted.

## 2026-10-22 — PostgreSQL database

- **Decision:** Use PostgreSQL as the required relational database.
- **Reason:** The domain needs transactions, constraints, indexed relationships, conditional uniqueness, and database-level audit protection.
- **Consequences:** Development and tests require PostgreSQL; schema changes use Django migrations and PostgreSQL-specific protections may be used deliberately.
- **Status:** Accepted.

## 2026-10-22 — Django templates and static frontend

- **Decision:** Build the browser frontend with Django HTML templates and shared CSS/JavaScript/static assets.
- **Reason:** The initial product does not require a separate JavaScript application and benefits from Django's integrated security model.
- **Consequences:** Templates live in `frontend/templates/` and source assets in `frontend/static/`.
- **Status:** Accepted.

## 2026-10-22 — Figma screenshots guide the UI

- **Decision:** Implement the frontend against screenshots supplied from Figma.
- **Reason:** The supplied visual references are the intended design source.
- **Consequences:** Store references in `frontend/design/figma-screenshots/`; pixel-accurate design work waits for those references.
- **Status:** Accepted.

## 2026-10-22 — Custom email-based user model

- **Decision:** Use `accounts.User` with email as `USERNAME_FIELD` and no username.
- **Reason:** Recruitment identities are email-centered and a custom model avoids a later disruptive authentication migration.
- **Consequences:** All user relationships use `AUTH_USER_MODEL`; complete email addresses are canonicalized to lowercase.
- **Status:** Accepted.

## 2026-10-22 — Candidate, recruiter, and administrator roles

- **Decision:** Model three explicit account roles.
- **Reason:** Each user type has distinct workflow and authorization needs.
- **Consequences:** Role enforcement is server-side; object-level authorization must accompany role checks in future workflows.
- **Status:** Accepted.

## 2026-10-22 — Public signup creates candidates only

- **Decision:** Ignore privileged role fields during public signup and always create a candidate.
- **Reason:** Self-service creation of recruiter or administrator accounts would be a privilege-escalation risk.
- **Consequences:** Recruiter and administrator accounts require trusted administrative creation.
- **Status:** Accepted.

## 2026-10-22 — Argon2 password hashing

- **Decision:** Make Argon2 the preferred Django password hasher.
- **Reason:** Use a modern memory-hard password hashing algorithm while retaining Django's migration-compatible fallback hashers.
- **Consequences:** `argon2-cffi` is required and authentication tests verify the stored algorithm.
- **Status:** Accepted.

## 2026-10-22 — Database-level case-insensitive email uniqueness

- **Decision:** Enforce `Lower("email")` uniqueness with constraint `accounts_user_email_ci_unique` in addition to form checks and manager normalization.
- **Reason:** Direct model writes and concurrent requests must not create case-variant duplicate identities.
- **Consequences:** PostgreSQL rejects duplicates even when `UserManager` is bypassed; the applied migration must not be rewritten.
- **Status:** Accepted.

## 2026-10-22 — Django 6.1 MAILERS configuration

- **Decision:** Use Django 6.1 `MAILERS` in development and production rather than deprecated legacy email settings.
- **Reason:** Match the current framework API and its deprecation timeline.
- **Consequences:** Development uses the console backend; production SMTP options come from private environment configuration.
- **Status:** Accepted.

## 2026-10-22 — Multi-agent recruitment calling

- **Decision:** Use a calling orchestrator plus profile, interview, evaluation, FAQ, scheduling, safety, escalation, and audit agents.
- **Reason:** Separate responsibilities improve control, testing, observability, and safety boundaries.
- **Consequences:** Agent versions, runs, actions, handoffs, approvals, and escalations are persisted; operational orchestration remains to be implemented.
- **Status:** Accepted.

## 2026-10-22 — Human review for final employment decisions

- **Decision:** AI must not autonomously make final hiring or rejection decisions.
- **Reason:** Employment decisions are consequential and require accountable human judgment.
- **Consequences:** AI evaluations are advisory; authorized human review and approval are mandatory, with escalation for risk or uncertainty.
- **Status:** Accepted.

## 2026-10-22 — Local open-source speech and ML components

- **Decision:** Plan for Faster Whisper STT, Piper TTS, Silero VAD, and open-source Python ML tooling.
- **Reason:** Support local operation, data control, auditability, and the free/open-source requirement.
- **Consequences:** Model artifacts and datasets remain outside Git; quality, latency, licensing, privacy, and hardware behavior require evaluation.
- **Status:** Accepted.

## 2026-10-22 — Structured monorepo layout

- **Decision:** Organize the repository into `frontend/`, `backend/`, `database/`, `ai_system/`, `ml/`, `docs/`, `scripts/`, `tests/`, and `var/`.
- **Reason:** Separate source, documentation, runtime state, and specialized AI/ML concerns while keeping one versioned project.
- **Consequences:** Root configuration remains at the repository root and path-aware tooling points to `backend/` and `frontend/`.
- **Status:** Accepted.

## 2026-10-22 — Django migrations stay with applications

- **Decision:** Keep migrations in `backend/<app>/migrations/`; do not move them to `database/`.
- **Reason:** Django migration discovery, app labels, dependencies, and applied history rely on application-local modules.
- **Consequences:** `database/` is limited to documentation, diagrams, safe utilities, and maintenance material.
- **Status:** Accepted.

## 2026-10-22 — Runtime-generated files use var

- **Decision:** Store collected static output, uploaded media, logs, and local agent state under `var/`.
- **Reason:** Keep runtime data separate from source and make ignore boundaries explicit.
- **Consequences:** Runtime contents are ignored; only `.gitkeep` placeholders are tracked. Private files and real backups are never committed.
- **Status:** Accepted.

## 2026-10-22 — Git-based workflow

- **Decision:** Use small validated Git checkpoints and preserve rename/migration history.
- **Reason:** Reviewable commits and clean checkpoints make recovery and AI handoff safer.
- **Consequences:** Agents inspect Git before edits, stage only intended files, avoid destructive history operations, and do not push without authorization.
- **Status:** Accepted.

## 2026-10-22 — Security and audit requirements

- **Decision:** Treat authorization, consent, upload safety, privacy-safe logging, immutable audit trails, retention, and human approval as core architecture.
- **Reason:** Recruitment data and AI-assisted decisions are sensitive and consequential.
- **Consequences:** Security controls require tests and audit coverage; failures and escalations must be visible rather than silently bypassed.
- **Status:** Accepted.

## 2026-10-22 — No credentials or private candidate files in Git

- **Decision:** Exclude secrets, private configuration, resumes, recordings, transcripts, datasets, model artifacts, logs, and real backups from Git.
- **Reason:** Prevent data exposure and keep the repository safe to share.
- **Consequences:** `.env` is never accessed by coding agents, runtime/private data uses ignored paths, and documentation contains no private values.
- **Status:** Accepted.

## 2026-10-23 — Deterministic domain auditing

- **Decision:** Mandatory domain auditing is an ordinary Python service, not a generative agent. Each registered event has a fixed category, resource type, canonical action, actor requirement, required metadata set, and metadata-key allowlist. Callers cannot supply action prose, and the registry is immutable after initialization.
- **Reason:** Whether a consequential action must be audited and which privacy fields are permitted are security policy decisions that must be deterministic and testable.
- **Consequences:** Views, domain services, authentication/security handlers, and future narrow agent-tool adapters use the same validated service. Mandatory domain-audit failures raise safe exceptions; existing authentication auditing may remain best-effort. The existing `AgentDefinition` value `audit` is unchanged during Week 2, but it does not authorize an LLM to make audit-policy decisions.
- **Status:** Accepted and implemented for the Milestone 2.1A foundation. This supersedes only the generative Audit Agent portion of the 2026-10-22 multi-agent decision; the stored `audit` enum value remains unchanged for migration compatibility.

## 2026-10-23 — Layered safety and narrow agent tools

- **Decision:** Deterministic Python controls enforce authorization, consent, state transitions, tool allowlists, approvals, rate limits, and protected fields. A future semantic Safety Agent may detect conversational risks but may never override those controls. Future agents receive narrow typed services, never unrestricted ORM, SQL, filesystem, model-name, field-name, or recipient access.
- **Reason:** Model output is untrusted and cannot be the authority for hard security or employment-workflow policy.
- **Consequences:** Week 2 builds shared service boundaries; no speculative agent adapters or fake agent tests are added before operational agents exist.
- **Status:** Accepted; deterministic audit boundary implemented, remaining controls planned.

## 2026-10-23 — Consent, verification, and document-processing evidence

- **Decision:** Consent history will be append-only with a unique idempotency key; consent and its audit event will share one transaction without a mandatory one-to-one relation. Effective-consent cache changes will lock the relevant profile or application row. Email verification will use signed, expiring, single-purpose tokens and keyed-HMAC email digests. Resume parsing will occur outside long database transactions, and the old resume remains active until a replacement succeeds.
- **Reason:** Mutable booleans, plain digests, and long parsing transactions are insufficient evidence and operational safeguards for sensitive recruitment processing.
- **Consequences:** Append-only consent history is implemented with profile/application locking, deterministic auditing, and legacy evidence that cannot authorize a current policy. Each new explicit action uses a new idempotency key and creates immutable history; network retries must reuse the original key. Effective consent is controlled by the latest action across policy versions. The email-verification foundation is implemented; workflow enforcement/pages and resume processing remain planned. Parser validation is not malware protection, and no wall-clock parser timeout is promised without subprocess isolation.
- **Status:** Accepted. Consent history and email-verification foundations are implemented and validated; the remaining workflow items are planned.

## 2026-10-26 — Email-verification token and privacy boundary

- **Decision:** Email verification uses a versioned Django-signed random token, a keyed-HMAC token digest, and a separate keyed-HMAC binding to the user's current normalized email. Challenges are single-use, expiring, row-locked during consumption, invalidated on resend/email change, and rate-limited through configurable cache counters.
- **Reason:** Raw tokens, plain email digests, replayable links, and unbounded verification attempts would expose account and identity data.
- **Consequences:** The database stores no raw token or raw URL. Audit metadata contains only safe reason/delivery codes and challenge UUIDs. Public request pages must return generic responses, and application/interview services must enforce `email_verified` later.
- **Status:** Accepted and implemented as the Milestone 2.1C foundation; delivery pages and domain enforcement remain Week 2 work.

## 2026-10-26 — Shared deterministic workflow transitions

- **Decision:** Job, application, interview-schedule, resume-processing, and consent states use immutable transition tables and narrow transactional Python services. Callers do not assign status fields directly.
- **Reason:** A single policy boundary makes role, ownership, prerequisite, side-effect, and audit behavior consistent for views, admin actions, and future narrow tools.
- **Consequences:** New resumes start inactive and replace the current resume only after successful processing. Interview invitations have persisted expiry, reschedule proposals have minimal review persistence, and invalid or terminal transitions fail safely. User-facing views must call these services in later milestones.
- **Status:** Accepted and implemented as the Milestone 2.1D foundation.

## 2026-10-26 — Interview invitation token and delivery boundary

- **Decision:** Interview invitations use a deterministic, versioned signed payload derived from a unique caller-supplied idempotency UUID, while PostgreSQL stores only its keyed-HMAC digest, expiry, idempotency key, and safe delivery state. Confirmation is row-locked and single-use.
- **Reason:** This permits safe network/email retry without storing raw bearer tokens and makes expiry, replay, delivery failure, and rescheduling behavior auditable.
- **Consequences:** Invitations expire at the earlier of 48 hours or scheduled start. Candidate verification plus current general/application consent are required at invitation and confirmation. Email recipients are derived from the application, errors use safe codes, and reschedule approval issues a new pending invitation.
- **Status:** Accepted and implemented for Milestone 2.5.

## 2026-10-23 — Lightweight Render demonstration dependencies

- **Decision:** Render's free demonstration build will install `requirements/render.txt`, which includes only `requirements/base.txt`. Heavy local AI/ML packages are intentionally excluded, and the hosted demonstration will initially use a clearly labelled simulated AI-call mode.
- **Reason:** Keep the cloud demonstration small and practical without replacing the project's real local open-source speech and ML pipeline.
- **Consequences:** The Whisper, Piper, and PyTorch pipeline remains locally runnable through the existing ML requirements. No object-storage dependency is selected until the storage provider is finalized. Render services, build commands, health endpoints, storage, and production environment configuration remain deferred to the final deployment milestone.
- **Status:** Accepted; lightweight dependency boundary added, deployment not configured.

## 2026-10-27 — Deterministic call-session lifecycle before real-time transport

- **Decision:** Build the interview runtime around one simulated `CallSession` per confirmed schedule, with explicit `pending`, `ready`, `active`, `paused`, and terminal states controlled by transactional Python services before adding WebSockets, Redis, speech engines, or generative orchestration.
- **Reason:** Authorization, consent, schedule eligibility, idempotency, failure handling, timestamps, and mandatory auditing must remain deterministic and testable independently of transport or model availability.
- **Consequences:** Candidate access is ownership-scoped; verified recruiters are company-scoped and require candidate-review capability; administrators remain explicit trusted actors. Current email verification and general/application consent are rechecked for entry into ready/active states. Persistent audio recording remains disabled by the service, and call audits contain only allowlisted identifiers, codes, state changes, and the simulated-mode flag.
- **Status:** Accepted and implemented for Week 3 Milestone 3.1.

## 2026-10-27 — Approved-question simulated interview boundary

- **Decision:** The first operational interview experience is a server-rendered text simulation that selects only active job-owned interview questions in deterministic order. Candidate answers are bounded private database records and never copied into audit metadata or recruiter operational status pages.
- **Reason:** Prove ownership, consent, state, idempotency, question progression, cancellation, privacy, and failure behavior before introducing real-time transport or model-driven dialogue.
- **Consequences:** Mutations are POST-only and CSRF-protected. Only the candidate may start, pause, resume, answer, or complete; authorized recruiters/administrators may see safe status and cancel but cannot impersonate the candidate. Audit records contain question identifiers and indexes, not answer text.
- **Status:** Accepted and implemented for Week 3 Milestone 3.2.

## 2026-10-27 — WebSocket transport carries server-derived status only

- **Decision:** Channels WebSockets may carry only an allowlisted server-derived call-session status snapshot. PostgreSQL remains authoritative; development uses the in-memory channel layer and production uses the already configured Redis layer only for delivery, not as an alternate workflow authority.
- **Reason:** Real-time updates must not bypass domain services or leak answer, transcript, résumé, token, prompt, or secret data across sessions or companies.
- **Consequences:** Each connection uses Django session authentication and exact object-level authorization, joins a UUID-derived per-session group, reauthorizes before every outgoing update, ignores caller-supplied event payloads, and closes safely on authorization or channel-layer failure. HTTP remains the deterministic fallback.
- **Status:** Accepted and implemented for Week 3 Milestone 3.3.

## 2026-10-27 — Optional local voice adapters with deterministic fallback

- **Decision:** Define typed transient-audio contracts separately from lazy local Silero VAD, Faster Whisper STT, and piper-plus TTS adapters. Model loading is local-only, adapter failures return fixed safe codes, and the deterministic text simulation remains the required fallback.
- **Reason:** Voice/model availability varies by device and platform and must not control authorization, consent, call state, or basic interview availability.
- **Consequences:** No model is selected or trained here, no raw audio is audited, no recording is persisted, no wall-clock timeout is promised without process isolation, and heavy ML dependencies remain excluded from `requirements/render.txt`.
- **Status:** Accepted and implemented for Week 3 Milestone 3.4.

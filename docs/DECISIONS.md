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
- **Consequences:** These items remain planned for later Week 2 milestones. Parser validation is not malware protection, and no wall-clock parser timeout is promised without subprocess isolation.
- **Status:** Accepted and planned; not implemented in Milestone 2.1A.

## 2026-10-23 — Lightweight Render demonstration dependencies

- **Decision:** Render's free demonstration build will install `requirements/render.txt`, which includes only `requirements/base.txt`. Heavy local AI/ML packages are intentionally excluded, and the hosted demonstration will initially use a clearly labelled simulated AI-call mode.
- **Reason:** Keep the cloud demonstration small and practical without replacing the project's real local open-source speech and ML pipeline.
- **Consequences:** The Whisper, Piper, and PyTorch pipeline remains locally runnable through the existing ML requirements. No object-storage dependency is selected until the storage provider is finalized. Render services, build commands, health endpoints, storage, and production environment configuration remain deferred to the final deployment milestone.
- **Status:** Accepted; lightweight dependency boundary added, deployment not configured.

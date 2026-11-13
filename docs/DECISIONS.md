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

## 2026-10-27 — Model-free coordinator with an exact action allowlist

- **Decision:** The first interview coordinator is deterministic Python with a versioned policy and exactly five commands: status, start, pause, cancel, and submit answer. Its Django adapter calls only candidate-scoped call-session services.
- **Reason:** Question selection and workflow progression must be secure and testable before any generative behavior is considered.
- **Consequences:** Only active job-owned questions are returned one at a time. Persisted role, ownership, consent, schedule, transition, idempotency, and audit controls remain in domain services. Unsupported, malformed, or failed commands stop with fixed safe codes. The coordinator cannot send messages, use arbitrary tools/ORM/paths, or make hiring decisions.
- **Status:** Accepted and implemented for Week 3 Milestone 3.5.

## 2026-10-28 — Deterministic human escalation and expiry boundary

- **Decision:** Extend the model-free coordinator with one `request_human` action and implement expiry, candidate-requested assistance, and technical-failure escalation as deterministic transactional Python services. Escalation descriptions and audit actions are policy-owned, not caller prose.
- **Reason:** A candidate must be able to stop and request authorized assistance, while runtime failures and due sessions must enter safe reviewable states without relying on a generative model or silently continuing.
- **Consequences:** Active candidate requests pause the session; technical failure atomically marks it failed; due sessions expire through row-locked transitions. UUID idempotency supports safe retry, mandatory audit failure rolls back state and escalation together, and audit metadata contains only allowlisted identifiers/codes. No escalation service makes an employment decision.
- **Status:** Accepted and implemented for Week 3 Milestone 3.6.

## 2026-10-31 — Deterministic evaluation with separate human finalization

- **Decision:** Calculate evaluation scores and advisory recommendations deterministically from a versioned, fully weighted job rubric. Store bounded criterion evidence and confidence, but require a separate explicit action by an authorized company recruiter to record either `advance` or `decline`.
- **Reason:** An advisory score must never silently become a consequential employment decision. Requiring persisted reviewer authority, a completed interview, an approved rubric, and a separate finalization action makes the boundary testable and auditable.
- **Consequences:** The advisory recommendation cannot change application state. Human `advance` moves an interviewed application to shortlisted; human `decline` moves it to rejected. Finalization and application transitions occur in one transaction with mandatory allowlisted audit events. Final evaluations and their scores are immutable at both model and PostgreSQL-trigger levels. Audit metadata excludes answers, transcripts, résumés, reviewer notes, and evidence prose. This workflow does not claim legal compliance and does not introduce a generative evaluation agent.
- **Status:** Accepted and implemented for the first Week 4 milestone.

## 2026-10-31 — Dry-run-first bounded retention

- **Decision:** The first executable retention policy anonymizes only private simulated-answer and transcript text belonging to sufficiently old terminal call sessions. The command is read-only by default; mutation requires `--apply`, a bounded batch, transactional row locks, a unique replay-safe run UUID, a normalized retention record, and mandatory privacy-safe auditing.
- **Reason:** Retention must reduce private-content exposure without silently deleting governance evidence, breaking referential integrity, leaking content through operations, or applying an unreviewed file-deletion policy.
- **Consequences:** Questions, timing, ownership relationships, immutable audits, consent history, finalized evaluations, applications, escalations, incidents, and retention evidence remain intact. Resume/media deletion and broader profile/application anonymization remain excluded until storage behavior and legal/privacy requirements are reviewed. The initial age period is a technical default, not legal advice or guaranteed compliance.
- **Status:** Accepted and implemented as the Week 4 retention/incident-readiness foundation.

## 2026-10-31 — Fail-closed production and staged deployment boundary

- **Decision:** Keep development behavior unchanged while requiring production to reject debug mode, placeholder/short signing keys, wildcard hosts, non-HTTPS trusted origins, non-PostgreSQL databases, weak database SSL modes, plaintext Redis, and disabled HTTPS redirects. Trust reverse-proxy headers only through an explicit environment flag and begin HSTS with a zero-duration observation stage before increasing duration or enabling subdomain/preload coverage.
- **Reason:** A future hosted demonstration must not become insecure because configuration is missing or copied from development, while premature HSTS preload could permanently affect unverified hostnames. Request/access logging must not disclose token-bearing URLs or private request content.
- **Consequences:** `render.yaml`, `build.sh`, `.python-version`, a fixed liveness endpoint, isolated production-settings tests, and a preflight checklist are tracked. Daphne access logging is disabled in the planned start command, Django request/security logs use fixed messages, PostgreSQL and Redis require encrypted transport, and build does not run migrations. External media storage, email, migration execution, backups, monitoring, cloud accounts, and actual deployment remain explicit blockers; the hosted mode remains simulated and synthetic-only.
- **Status:** Accepted and implemented as repository-side Week 4 deployment preparation; no infrastructure or deployment exists.

## 2026-10-31 — Candidate-reviewed local transcription boundary

- **Decision:** Browser microphone clips may be processed transiently by an explicitly configured local Faster-Whisper base model only for an active, eligible candidate-owned simulated interview question. The service returns editable text and never submits or persists it automatically.
- **Reason:** Candidate control and privacy require the existing typed answer workflow to remain authoritative while still allowing local speech-to-text assistance without a third-party API or persistent recording.
- **Consequences:** Audio is bounded, rate-limited, decoded in memory, discarded, and excluded from media, logs, audit metadata, WebSockets, and recruiter/admin views. The local model download is an explicit script action under ignored `var/models/`; server startup never downloads a model. Failure leaves typed entry usable. Manual microphone QA is required because no local model was present during automated validation.
- **Status:** Accepted and implemented for Week 4; no live model inference was claimed.

## 2026-11-03 — Pakistan-only scheduling and display boundary

- **Decision:** Ordinary profile, invitation, and reschedule forms do not expose a timezone field. The legacy persisted timezone columns remain for schema compatibility, but services accept only the configured `Asia/Karachi` business timezone and display interview times in that timezone.
- **Reason:** The product supports Pakistan only, so client-supplied IANA timezone values would create misleading scheduling behavior.
- **Consequences:** Timestamps remain timezone-aware and are stored safely in UTC by Django. Tampered form values are ignored by allowlisted forms, non-Pakistan direct service values are rejected, and legacy record values are not trusted for display.
- **Status:** Accepted and implemented in the uncommitted release-candidate worktree.

## 2026-11-04 â€” Explicit local speech-model verification boundary

- **Decision:** Keep Faster-Whisper CPU/int8 offline-only loading, Silero VAD, and Piper Plus as optional local adapters. Download the selected model weights only through explicit scripts into ignored `var/models/`, then verify them with an in-memory synthetic smoke script.
- **Reason:** Installed packages and mocked adapter tests do not establish that actual model files load or perform inference. Explicit setup avoids a server-start download and keeps audio out of storage.
- **Consequences:** The local Faster-Whisper base and Silero VAD models, plus a native Piper Plus English-capable voice, have successfully loaded and run synthetic local inference. The Piper voice has corpus-derived terms recorded in its downloaded `NOTICE.md`; it must not be redistributed or deployed until those terms are reviewed. The legacy Piper `espeak`-configured voice remains incompatible with `piper-plus==2.0.2` and is not the configured default. Browser microphone QA, real-world quality evaluation, and deployment remain deferred.
- **Status:** Accepted and implemented in the uncommitted release-candidate worktree.

## 2026-11-04 — Local interview-reasoning model quality gate

- **Decision:** Do not enable the first tested 0.5B CPU-local Qwen ONNX model as an operational interview agent.
- **Reason:** It loaded real local weights and produced structured output, but ten synthetic scenario checks showed unreliable contextual action selection. Model availability and schema validity are not evidence of safe agent quality.
- **Consequences:** The deterministic coordinator, consent/authorization services, and human escalation boundary remain the only execution authority. The isolated read-only prototype may be retained for evaluation, but it has no HTTP integration and cannot act on its proposals. A stronger provenance-reviewed local model must pass real contextual and safety evaluation before model-driven advice is enabled.
- **Status:** Accepted as a safety gate; no generative agent is operational.

## 2026-11-04 — Detached shared Qwen 3B and local RAG foundation

- **Decision:** Use Qwen's official Qwen2.5-3B-Instruct Q4_K_M GGUF through an isolated local `llama.cpp` loopback process for shared proposal generation, with one concurrent generation. Use a pinned local MiniLM ONNX embedder and process-local hybrid index while schema changes remain unapproved.
- **Reason:** The prior 0.5B ONNX model failed contextual quality. The 3B model supports repeated offline structured generation on the Windows CPU host, while an in-process native runtime would increase Django crash risk. pgvector would require an unapproved database change.
- **Consequences:** Agent proposals are validated against nine immutable contracts and never directly execute tools, ORM, SQL, filesystem, network, or employment decisions. RAG retrieval is filtered by caller-supplied authorized company/candidate/consent context before ranking, but is never an authorization system. Current 26/30 synthetic expected-action performance is insufficient to enable candidate-facing generation.
- **Status:** Accepted for detached evaluation and shared infrastructure only.

## 2026-11-04 — Contract-derived schema constraints for detached local LLM proposals

- **Decision:** Request a local JSON schema from the isolated Qwen runtime, with `action` constrained to the registered agent contract's immutable allowlist, while retaining server-side schema validation and fail-closed fallback.
- **Reason:** A real Calling Orchestrator evaluation produced an unregistered action despite a prompt-only allowlist. The local runtime constraint prevents malformed action shapes before deterministic validation.
- **Consequences:** The model remains a proposal source only; the constrained schema does not authorize a tool, ORM mutation, workflow transition, hiring outcome, or candidate-facing use. Django services and the bounded runner remain authoritative.
- **Status:** Accepted and implemented for detached Task 2 evaluation.

## 2026-11-04 — QA database isolation before model-driven workflow writes

- **Decision:** A Qwen proposal may trigger an allowlisted Django service only in a separately provisioned disposable PostgreSQL QA database with an isolated credential configuration and explicit QA-only settings. The adapter must fail closed if that database cannot be verified.
- **Reason:** The current pytest configuration reuses the development settings' Django-managed test database and cannot prove separation from ordinary development records under the required QA policy.
- **Consequences:** No model-driven write-path adapter or state-changing AI QA may run against current development/production settings. Existing deterministic test coverage remains valid, but a new isolated QA configuration is a prerequisite for the requested full model-to-Django integration scenarios.
- **Status:** Accepted and blocking Task 3 integration execution.

## 2026-11-05 — QA-only sequential model integration and local demo boundary

- **Decision:** Permit model-proposed Django writes only in `config.settings_qa`, only when the exact `hireflow_qa_release` database and `hireflow_qa_runner` role are reverified and the narrow action gate is explicitly enabled. Run transient Piper/Silero/Whisper turns first, release their model objects, then start the single-concurrency Qwen worker and allow only validated `continue` proposals through the existing deterministic coordinator. Keep browser model actions disabled; expose only candidate-authorized transient VAD/STT and QA Piper playback.
- **Reason:** The laptop cannot reliably hold all speech models and Qwen concurrently, and the public/browser boundary must not gain model-write authority. A loopback disconnect observed under overlapping load confirmed the need for sequential ownership and safe runtime exception containment.
- **Consequences:** The QA command uses three synthetic turns, permission-filtered MiniLM sources, deterministic persistence/auditing, and a non-final advisory evaluation. QA tunnel configuration accepts one exact HTTPS hostname, uses secure cookies, hides Django admin, binds Daphne to loopback, and sends no email. No migration or real candidate-facing activation is introduced.
- **Status:** Accepted and implemented in code; final persisted execution remains blocked until QA variables are restored to the active process.

## 2026-11-06 — Supervise and sequence native QA models under Windows commit limits

- The QA release management command runs its read-only database identity verifier before local model preparation and rechecks the identity inside the workflow immediately before writes.
- Piper/Silero/Faster-Whisper run in a short-lived child with database/settings secrets removed from its environment. Qwen is started while the parent is lightweight, before Django imports, and is attached to the command through an in-process preflight registry.
- Windows llama.cpp children use a kill-on-close job object so parent termination cannot orphan inference. Startup diagnostics retain only bounded native lines internally and expose category/exit-code metadata, not raw commands or paths.
- On this constrained laptop the QA command prefers the ignored local Q3_K_S derivative when present. Q4_K_M remains the source/primary quality artifact; the derivative is a release-demo memory fallback and requires separate broader quality evidence before wider use.

## 2026-11-06 — Production demonstration is text-only

- **Decision:** Force `SPEECH_FEATURE_ENABLED=False` in `config.settings_production`, regardless of environment input. Local settings retain optional speech for development and isolated QA.
- **Reason:** Render's lightweight deployment boundary excludes local speech models and must not offer microphone, transcription, or TTS controls that cannot be served safely.
- **Consequences:** Production hides speech controls and refuses speech endpoints before adapter/model creation; the typed simulated-interview workflow remains available. No speech source, dependency, or local artifact is removed.
- **Status:** Accepted and implemented.

## 2026-11-13 — FAQ retries may narrow registered actions and retrieval scope

- **Decision:** A detached agent request may narrow, but never expand, its registry action set and may request a smaller bounded RAG result count. FAQ clarification recovery uses one retry with source-grounded actions and one top-ranked public source.
- **Reason:** Qwen 2.5 3B repeatedly selected clarification or unrelated evidence when several authorized sources were supplied. Narrowing preserves schema validation and prevents adding model authority or tools.
- **Consequences:** The runner and gateway reject action scopes outside the immutable registry. This mechanism does not execute actions and does not weaken authorization, consent, or RAG permission filtering.
- **Status:** Accepted and implemented.

## 2026-11-13 — Initialize Neon with fresh QA records

- **Decision:** Keep the newly migrated Neon schema and create only new synthetic administrator, recruiter, candidate, and company records. Do not copy local PostgreSQL data.
- **Reason:** The user explicitly rejected local-to-Neon record transfer and selected fresh administrator plus synthetic QA data.
- **Consequences:** Existing local accounts and passwords do not exist in Neon. New accounts require a private password setup; recruiter approval and candidate consent must follow their established workflows. No resumes, applications, or interviews are implicitly transferred.
- **Status:** Accepted and implemented.

## 2026-11-13 — Provision approved recruiter and separate synthetic QA logins

- **Decision:** After explicit user approval, attach the sole existing Neon recruiter to the active synthetic QA company and verify that profile via the existing audited administration service. Create separate synthetic QA admin, recruiter, and candidate accounts for role testing, with generated strong passwords kept in a private local file outside Git.
- **Reason:** The recruiter dashboard returned 403 because no RecruiterProfile existed, and the user requested independently usable QA logins for all portal roles.
- **Consequences:** The approved recruiter can access its dashboard; synthetic QA identities can test role flows. QA account email verification was set only for these new synthetic identities. Candidate AI consent and consequential interview/application state were not fabricated. Credentials must be retrieved securely and the temporary credential file removed after use.
- **Status:** Accepted and implemented.

## 2026-11-13 — Bounded Gemini website timeout and explicit job deadline feedback

- **Decision:** Allow up to 25 seconds for existing Gemini-backed website proposals, and show the validated expired-deadline reason for a rejected job publication.
- **Reason:** Live synthetic agent requests intermittently exceeded the previous 12-second bound, although identical 25-second calls succeeded. A QA job's expired deadline was hidden behind a generic state-change error.
- **Consequences:** Requests remain time-bounded and retain safe fallbacks; no model output gains authority. Publishing still requires the existing deterministic transition checks and a recruiter-selected future deadline.
- **Status:** Accepted and implemented.

## 2026-11-13 — User requests no outgoing email and no interview confirmation step

- **Decision:** Remove the website's candidate email-verification and interview-email workflows. The user explicitly chose no separate candidate confirmation requirement for newly scheduled interviews.
- **Reason:** The user wants an in-app recruitment workflow without email delivery or OTP/link steps.
- **Consequences:** Password authentication, candidate ownership, recruiter approval, AI consent, audit logging, schedule conflict checks, and no-rescheduling rules remain required. Email ownership will no longer be proved by the application; this changes the account-security model and must be clearly reported. Existing historical invitation/token data must remain intact while new schedules become usable without email.
- **Status:** Accepted and implemented.

## 2026-11-13 — Transition from local Qwen/llama.cpp inference to Google Gemini API for cloud deployment

- **Decision:** Use Google Gemini API (`gemini-3.1-flash-lite` or configured model via `GEMINI_API_KEY` / `GOOGLE_API_KEY`) as the remote LLM inference provider for candidate extraction, agent proposals, FAQ, and production deployment, completely eliminating local Qwen GGUF model weights, PyTorch, and llama.cpp binaries from cloud deployment packages.
- **Reason:** Local 3B/4B GGUF models require 2-4GB RAM, exceeding free cloud tier limits (Render Free tier has 512MB RAM). The existing Gemini integration uses Python standard library `urllib` without heavyweight SDKs, keeping cloud deployments lightweight and responsive.
- **Consequences:** Production requirements exclude heavy ML dependencies. `GEMINI_API_KEY` must be configured in hosting environment variables. Local development retains optional offline adapters without affecting cloud builds.
- **Status:** Accepted.

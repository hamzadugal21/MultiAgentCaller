# Architecture

This document describes both the implemented foundation and the planned system. Labels in the diagrams distinguish them; a planned box is not a claim of completed functionality.

## Status summary

Implemented today: Django configuration, PostgreSQL models/migrations, accounts web flow, role dashboards, resume validation, authentication audit signals, deterministic domain-audit validation, immutable audit/consent protection, append-only consent services, secure email-verification services, explicit workflow transition policies, templates/static discovery, and runtime path separation.

Planned: candidate/recruiter workflow views, browser audio transport, local speech execution, multi-agent orchestration, ML inference, safety enforcement services, human review UI, retention jobs, and end-to-end operations.

## Overall system architecture

```mermaid
flowchart LR
    U[Browser user] -->|HTTPS forms and pages| FE[Frontend templates and static assets<br/>Implemented foundation]
    FE --> DJ[Django backend<br/>Accounts flow implemented]
    DJ --> APPS[Domain applications<br/>Models implemented]
    APPS --> PG[(PostgreSQL<br/>Implemented)]
    DJ --> MEDIA[Protected runtime media<br/>var/media]
    DJ -. WebSocket audio .-> CH[Channels and Redis<br/>Planned runtime]
    CH -.-> ORCH[Agent orchestration<br/>Planned]
    ORCH -.-> SPEECH[Local STT, TTS, VAD<br/>Planned]
    ORCH -.-> ML[ML inference and evaluation<br/>Planned]
    DJ --> AUDIT[Deterministic domain audit service<br/>Implemented foundation]
    ORCH -.-> AUDIT
    REVIEW[Authorized human reviewer<br/>Planned workflow] -. approves .-> DJ
```

## Browser frontend

The frontend uses Django-rendered HTML in `frontend/templates/` and shared assets in `frontend/static/`. The existing pages cover signup, login, and role-specific dashboard shells. Future pages should remain server-authorized and follow supplied Figma screenshots. Browser code must not receive database credentials, private environment values, unrestricted media paths, or privileged agent tools.

## Django backend

`backend/manage.py` starts the Django project. `backend/config/` defines shared, development, and production settings plus ASGI/WSGI entry points. `PROJECT_ROOT` is the repository root, `BACKEND_ROOT` is `backend/`, `FRONTEND_ROOT` is `frontend/`, and `BASE_DIR` remains the backend compatibility alias.

The backend owns validation, authorization, consent checks, workflow transitions, database transactions, audit creation, and access to protected storage. Client-supplied roles, ownership identifiers, scores, agent permissions, and approval flags must never be trusted directly.

## PostgreSQL database

PostgreSQL is the authoritative transactional store. Django migrations remain inside each backend application. The schema uses foreign keys, indexes, check constraints, conditional uniqueness, and UUID identifiers. Important integrity boundaries include case-insensitive unique user emails, one active resume per candidate, one current schedule per application, bounded evaluation values, ordered call/agent events, and database-protected immutable audit and consent records.

## Authentication and role permissions

`accounts.User` authenticates by email and supports candidate, recruiter, and administrator roles. Public signup creates candidates only. Existing dashboard authorization is enforced in Django views. Future object-level checks must ensure candidates access only their own records and recruiters access only authorized company/job records. Administrator capability must not be inferred from request data.

## Email verification

`accounts.EmailVerificationChallenge` stores a challenge UUID, user, unique keyed token digest, keyed normalized-email binding, purpose version, creation/expiry/used/invalidation timestamps, and optional request UUID. Raw tokens and URLs are never persisted. Tokens contain a cryptographically random nonce and are signed with a dedicated versioned salt; the default lifetime is 24 hours.

Creation, resend, email-change invalidation, and consumption are deterministic services. Resend invalidates prior active challenges. Consumption locks the challenge row, verifies the signature, expiry, purpose, current email binding, active user, and unused/uninvalidated state, then sets `User.email_verified` in the same transaction as the mandatory audit event. Configurable request/resend/invalid-attempt limits use privacy-safe cache keys. User-facing generic-response pages and job/interview enforcement are implemented in later milestones.

## Candidate profiles and resume handling

Each candidate user receives one `CandidateProfile`. Candidate skills can be self-reported or derived from approved processing. `Resume` stores protected file metadata, processing status, extracted text, and a checksum field. New resumes default inactive. A deterministic processing service permits only pending-to-processing, processing-to-completed/failed, and failed-to-processing transitions; activation atomically replaces the prior active resume only after successful processing. Upload paths use random names; validators accept structurally plausible PDF/DOCX files up to 5 MB. Upload views, ownership enforcement, extraction, malware scanning, and retention execution remain planned.

## Recruitment domain

The recruitment schema connects companies and recruiter profiles to job postings, weighted skill requirements, applications, interview questions, and FAQs. Applications link a candidate and optional resume to one job and include consent for AI interviewing. Immutable transition maps and transactional services enforce job and application state changes, persisted role/capability checks, company isolation, and mandatory audits. User-facing management workflows remain planned for Week 2.

## Interview scheduling and evaluation

Schedules track start/end times, timezone, state, access-token hashes, invitation expiry, and rescheduling. `InterviewRescheduleRequest` stores a candidate proposal and its pending/approved/rejected/cancelled review state. A deterministic transition service enforces candidate confirmation, recruiter/company authority, system-only expiry, terminal states, atomic replacement activation, and mandatory audits. Rubrics contain weighted criteria; evaluations capture evidence, confidence, scores, advisory recommendations, model/prompt versions, and human-review fields. The operational scheduler and review interface are planned. Setting an evaluation as final must be restricted to an authorized human workflow.

## Calling sessions

The call schema records consent, lifecycle state, speech-engine identifiers, optional recording metadata, transcript segments, events, and metrics. Recording defaults to disabled. The planned runtime uses Channels with Redis in production for browser communication and must handle reconnects, timeouts, interruption, and clean termination without losing auditability.

## Recruitment call workflow

```mermaid
flowchart TD
    A[Job application<br/>Schema implemented] --> B[Human-approved interview invitation<br/>Planned workflow]
    B --> C[Candidate confirms schedule and consent<br/>Planned workflow]
    C --> D[Create call session<br/>Planned service]
    D --> E[Browser audio connection<br/>Planned]
    E --> F[VAD and STT<br/>Planned]
    F --> G[Orchestrator selects approved agent<br/>Planned]
    G --> H[Agent response and safety check<br/>Planned]
    H --> I[TTS response<br/>Planned]
    I -->|Next turn| F
    H -->|Risk, request, or failure| J[Human escalation<br/>Planned]
    G --> K[Audit events and call metrics<br/>Schema implemented]
    I --> L[Rubric-based advisory evaluation<br/>Planned]
    L --> M[Authorized human review and final decision<br/>Mandatory]
```

## Multi-agent orchestration

Agent definitions, versions, runs, actions, handoffs, approvals, and escalations have persistent models. The planned orchestrator controls which specialist receives a turn and which allowlisted tools it may use. Agents receive minimum necessary context and return structured, auditable results.

```mermaid
flowchart TB
    O[Calling Orchestrator<br/>Planned] --> P[Candidate Profile Agent]
    O --> I[Interview Agent]
    O --> F[FAQ Agent]
    O --> S[Scheduling Agent]
    O --> E[Evaluation Agent]
    P --> SAFE[Safety Agent]
    I --> SAFE
    F --> SAFE
    S --> SAFE
    E --> SAFE
    SAFE -->|Allowed| O
    SAFE -->|Risk or uncertainty| ESC[Escalation Agent]
    ESC --> HUMAN[Authorized human]
    O -. structured event request .-> AUD[Deterministic domain audit service]
    ESC -. structured event request .-> AUD
```

Deterministic Python policy enforcement remains authoritative for permissions, consent, transitions, tool allowlists, approvals, rate limits, and protected fields. The future semantic Safety Agent detects prompt injection, bias, coercion, privacy concerns, and unsafe conversational content but cannot override hard controls. The escalation agent must create a reviewable record and route it to a human; it must not silently resolve high-impact cases.

Future agents never receive unrestricted ORM, SQL, filesystem, model-name, field-name, or recipient access. Each tool must call a narrow Python service with validated input, authorization context, consent enforcement, idempotency where required, mandatory audit recording, structured output, and safe errors.

## Speech and ML components

The planned local speech path uses Silero VAD to find speech boundaries, Faster Whisper to transcribe, and Piper to synthesize responses. ML code belongs in `ml/`, while orchestration and safety policy belong in `ai_system/`. Models, datasets, checkpoints, and generated artifacts are ignored by Git. Evaluation must measure quality, bias, confidence, latency, and failure behavior before production use.

## Audit logging

`AuditEvent` records actors, categories, outcomes, severity, resource references, privacy-safe request metadata, chained fields, and a keyed integrity hash. Django blocks model-level modification/deletion and a PostgreSQL migration installs triggers that block bulk updates/deletes. Authentication signals record successful login, failed login with a hashed identifier, and logout.

The deterministic domain audit service accepts a frozen structured command, matches it to an immutable Week 2 event registry, and derives the human-readable action only from that registered specification. Each specification declares required and allowed metadata keys. The service normalizes UUID identifiers, enforces actor/resource requirements, and accepts only bounded allowlisted scalar metadata. It rejects missing required metadata, unknown events and metadata, nested private objects, credentials, raw tokens, document/transcript contents, and filesystem paths. Mandatory audit failures raise safe exceptions and can participate in the calling domain service's transaction. An LLM never decides whether auditing is required, which mandatory fields may be omitted, whether an event may change, or whether private content belongs in metadata. Previous-event hash chaining remains unimplemented by design.

## Consent history

The current Milestone 2.1B worktree adds `auditlog.ConsentRecord` as append-only governance evidence for general AI-processing and application-level AI-interview consent. Its exact fields are UUID `id`; protected `candidate`; consent type (`general_ai_processing` or `ai_interview`); action (`granted` or `revoked`); policy version; collection source (`profile`, `application`, `interview_confirmation`, `admin_assisted`, or `legacy_import`); optional protected application, interview schedule, and recorded-by user; timezone-aware recorded time; globally unique UUID idempotency key; and optional request/correlation UUIDs.

Named checks are `consent_general_no_context`, `consent_interview_has_app`, `consent_schedule_has_app`, and `consent_nonlegacy_has_actor`. Named indexes are `consent_candidate_type_time`, `consent_app_type_time`, `consent_schedule_time`, `consent_action_time`, `consent_request_id`, and `consent_correlation_id`. Model methods reject updates/deletes and PostgreSQL independently blocks both operations.

Deterministic consent services lock the mutable `CandidateProfile` or `JobApplication` cache owner, reload actor and schedule authority from PostgreSQL, validate scope and ownership, persist consent evidence, synchronize the Boolean cache, and record the mandatory audit event in one short transaction. Candidate-originated evidence requires the persisted actor to be the active candidate user with the candidate role; administrator evidence must use the `admin_assisted` source. An identical persisted idempotency key returns its existing record and reuse with different consent semantics is rejected. A different key represents a new explicit action and creates a new record and audit event, so network retries must reuse their original key.

Effective-consent checks read the latest record across all policy versions, ordered by recorded time and UUID. Consent is effective only when that latest action is granted under the requested non-legacy policy. A later revocation or different-policy action blocks the earlier grant; a later current-policy grant restores consent. Boolean caches follow every new latest action but are never the source of authority.

Audit events use `resource_type = "auditlog.ConsentRecord"`, the consent UUID as `resource_id`, and only allowlisted identifiers/codes; no wording or private prose is copied. Legacy true cache values become `legacy-unversioned` historical grants with no actor or migration-time audit event, then profile/application caches are reset so legacy evidence cannot authorize future processing. False caches do not create misleading revocations. This is technical evidence handling, not a claim of legal compliance.

## Data and security flow

```mermaid
flowchart LR
    INPUT[Untrusted browser input] --> VALIDATE[Django forms, validators,<br/>CSRF and authorization]
    VALIDATE -->|Accepted structured data| DB[(PostgreSQL)]
    VALIDATE -->|Approved upload| MEDIA[Protected var/media storage]
    MEDIA -. Planned malware and text processing .-> PROC[Isolated processing]
    DB -->|Minimum necessary context| AGENT[Planned agent tool boundary]
    PROC -. Redacted approved text .-> AGENT
    AGENT --> SAFETY[Safety and policy check]
    SAFETY -->|Low-risk advisory output| REVIEW[Authorized human review]
    SAFETY -->|Risk or uncertainty| ESC[Escalation queue]
    VALIDATE --> AUDIT[Sanitized immutable audit event]
    AGENT --> AUDIT
    REVIEW --> AUDIT
    ESC --> AUDIT
    SECRETS[Private environment configuration] --> DJANGO[Django server only]
    SECRETS -. never to .-> INPUT
    SECRETS -. never to .-> AGENT
```

## Human approval boundaries

AI can ask approved questions, summarize, identify evidence, calculate rubric-based advisory scores, and recommend review. It cannot independently publish jobs, change privileged roles, enable recording, disclose private data, resolve serious incidents, or make final hiring/rejection decisions unless a narrowly defined action is explicitly approved by an authorized human and policy permits it. Final employment outcomes always require human review.

## Runtime storage

- `var/media/`: uploaded resumes and any future protected recordings; contents ignored by Git.
- `var/static/`: collected static output; contents ignored by Git.
- `var/logs/`: runtime logs; contents ignored by Git.
- `var/agent-state/`: local non-secret agent counters/state; contents ignored except `.gitkeep`.
- `ml/artifacts/`, `ml/datasets/`, `ml/checkpoints/`: local generated or downloaded ML content; contents ignored by Git.

Real database backups, credentials, transcripts, candidate documents, and recordings must never be stored in tracked paths.

## Security boundaries

1. **Browser/server:** Validate all input, enforce CSRF, authenticate, authorize, and expose only necessary data.
2. **Server/database:** Use least-privilege credentials, transactions, constraints, and migrations; never embed secrets in code or docs.
3. **Uploads/processing:** Treat files as hostile, store outside static assets, scan before production processing, and enforce ownership and retention.
4. **Backend/agents:** Use allowlisted typed tools, minimum context, timeouts, structured outputs, redaction, and immutable audit events.
5. **AI/human decision:** Keep AI output advisory and require authorized human review for final employment decisions and serious escalations.
6. **Source/runtime:** Keep runtime data, model artifacts, secrets, and private candidate content outside Git.

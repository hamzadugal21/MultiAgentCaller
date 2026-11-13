# Four-Week Roadmap

Progress is based on completed, validated product work. Directory preparation alone does not count as product functionality.

## Week 1 — Secure foundation (100% complete)

### Objectives

Establish the secure Python/Django/PostgreSQL foundation, core domain schema, authentication, audit controls, repository structure, and repeatable validation.

### Tasks and deliverables

- Pin development, production, and ML dependencies.
- Configure Django development/production settings, PostgreSQL, Channels, static/media paths, and Django 6.1 `MAILERS`.
- Create the custom email user model and candidate, recruitment, interview, calling, agent, and audit schemas.
- Add candidate-only public signup, role dashboards, secure login/logout, and automatic candidate profiles.
- Add resume validation, Argon2 hashing, login throttling, sanitized authentication audit events, and immutable audit-event protection.
- Enforce database-level case-insensitive email uniqueness.
- Reorganize the repository into the approved top-level structure.
- Add persistent project-context documentation and agent operating rules.

### Required tests

- Authentication, role authorization, Argon2, logout method, duplicate email, audit events, database audit protection, and resume validation.
- Django system check, migration-drift check, dependency check, and Ruff.

### Security requirements

- No secrets or private candidate files in Git.
- Candidate-only public signup and server-side role checks.
- Protected uploads and immutable, privacy-safe audit records.
- Database constraints for critical integrity rules.

### Completion criteria

- All Week 1 migrations applied.
- 28 tests pass.
- Django, dependency, migration, Ruff, and Git diff checks pass.
- `main` contains the validated Week 1 and structure checkpoints.

## Week 2 — Core recruitment workflows (100% complete)

### Objectives

Turn the schema foundation into secure candidate, recruiter, job, application, and scheduling workflows using Django templates and shared static assets.

### Tasks and deliverables

- **Milestone 2.1 — policies and schema:** deterministic domain auditing, state-transition tables, append-only consent history, email-verification design, shared authorization/service conventions, and foundation tests. Milestones 2.1A through 2.1D are committed and validated.
- **Milestone 2.2 — candidate workflow:** candidate-only allowlisted profile editing, consent history controls, verification request/resend/confirmation pages, protected PDF/DOCX upload and download, bounded basic extraction, safe replacement, deterministic audits, and focused tests are committed and validated.
- **Milestone 2.3 — recruiter and jobs:** trusted administrator provisioning services/admin, persisted recruiter verification/capabilities, company-scoped job create/edit/state management, skills/questions/FAQs, authenticated candidate browsing, deterministic audits, and security tests are committed and validated.
- **Milestone 2.4 — applications:** verified candidate application creation, open/deadline checks, active-resume ownership, duplicate prevention, optional application consent, audit history, company/candidate isolation, and pre-call withdrawal with transactional schedule cancellation are committed and validated.
- **Milestone 2.5 — scheduling:** company-authorized recruiter invitations, deterministic signed tokens with keyed-HMAC storage, 48-hour/start-time expiry, idempotent delivery retry, candidate confirmation, current-consent checks, reschedule request/review, cancellation, expiry, notification email, UTC/IANA handling, audits, and tests are committed and validated.
- **Milestone 2.6 — integration and security:** a complete administrator-to-confirmed-interview integration test, cross-company/cross-candidate IDOR tests, mass-assignment and POST-only tests, CSRF enforcement, token/rate-limit/upload/consent/transition coverage, template escaping, audit privacy review, migration verification, and full validation are complete.
- Frontend work remains semantic and minimal until supplied Figma screenshots are available.

### Required tests

- Form, view, model, ownership, role, consent, upload, and audit tests.
- Cross-application tests covering candidate-to-application-to-schedule flow.
- Existing 28 tests must continue to pass.

### Security requirements

- Object-level authorization and least privilege.
- CSRF protection and safe POST-only mutations.
- File validation, protected media, private-data minimization, and no unsafe file serving.
- Human-controlled recruiter/administrator account creation.

### Completion criteria

- A candidate and recruiter can complete the core pre-interview workflow through tested server-rendered pages.
- Unauthorized cross-user and cross-company access is rejected.
- Consent history and deterministic audit records are enforced.
- Email verification is enforced before applications and interview confirmation.
- State changes use tested transition services rather than direct status assignment.
- No migration drift or failing validation remains.

## Week 3 — Secure simulated calling and runtime boundaries (100% complete)

### Objectives

Implement the secure deterministic browser simulation, optional local speech adapter boundaries, narrow coordination, safety controls, and escalation before any live voice or broader specialist-agent runtime.

### Tasks and deliverables

- **Milestone 3.1 — call-session foundation:** committed and validated deterministic session creation, explicit lifecycle transitions, schedule/application/candidate consistency, current-consent and confirmation gates, candidate/company authorization, idempotency, safe timestamps, privacy-safe audit events, and database constraints.
- **Milestone 3.2 — simulated interview lifecycle:** committed and validated server-rendered candidate/recruiter flow, approved deterministic question ordering, bounded private answer persistence, idempotent progression/completion, candidate exit controls, POST/CSRF protection, company isolation, safe status visibility, and privacy-safe audits.
- **Milestone 3.3 — WebSockets and Redis:** committed and validated authenticated, session-authorized status transport, server-derived allowlisted payloads, per-session group isolation, safe disconnect/failure behavior, in-memory development channels, and the existing Redis production channel layer. The HTTP simulation remains authoritative fallback.
- **Milestone 3.4 — voice adapter boundaries:** committed and validated typed transient-audio interfaces plus lazy local Silero VAD, Faster Whisper STT, and piper-plus TTS adapters with local-only model loading, safe structured failures, unsupported-microphone fallback, and no recording persistence.
- **Milestone 3.5 — interview coordinator:** committed and validated deterministic coordinator with a versioned policy, approved-question snapshots, a fixed action allowlist, candidate-only narrow Django tools, safe failure results, and no model, messaging, arbitrary ORM, or employment-decision capability.
- **Milestone 3.6 — safety and integration:** committed and validated deterministic timeout/expiry processing, candidate-requested human assistance, technical-failure escalation, fixed safe errors, idempotent replay/conflict handling, mandatory audit rollback, consent/cancellation boundaries, and a complete approved-question simulated interview integration test.
- Channels/Redis status delivery is implemented with PostgreSQL authority and HTTP fallback; browser audio transport and richer event/metric processing are deferred.
- Optional Silero VAD, Faster Whisper STT, and Piper TTS adapter boundaries are implemented; operational browser speech and turn-taking are deferred.
- The deterministic coordinator and escalation service are implemented; broader profile, FAQ, scheduling, semantic-safety, and evaluation agent runtimes are deferred.
- Consent enforcement, audit redaction, recording-disabled default, safe retries, and structured failures are implemented for the simulated runtime.

### Required tests

- Unit tests for audio adapters, coordination transitions, narrow tools, safety rules, and redaction.
- Integration tests for the simulated call lifecycle, failure/expiry, WebSocket isolation, and escalation.
- Deterministic fixtures must contain no real candidate data.

### Security requirements

- Treat candidate speech and retrieved text as untrusted input.
- Prevent prompt injection from authorizing tools or bypassing policy.
- Minimize private context and redact logs/transcripts.
- Require human approval for sensitive actions and final employment outcomes.

### Completion criteria

- A consented simulated browser interview completes through the deterministic coordinator without requiring speech models or live audio.
- Safety and escalation scenarios are tested and auditable.
- Failure recovery does not silently make or finalize decisions.

## Week 4 — Evaluation, integration, and production readiness (75% complete)

### Objectives

Complete human-reviewed evaluation, end-to-end integration, operational safeguards, documentation, and release readiness.

Deployment planning reference: [Render deployment plan](development/RENDER_DEPLOYMENT.md). This plan records deferred Week 4 work and does not represent an active deployment.

### Tasks and deliverables

- Rubric-based evidence, deterministic weighted scoring, confidence, advisory recommendations, and reviewer workflow. **Implemented and validated.**
- Recruiter review UI with explicit human-only shortlist/decline finalization. **Implemented and validated.**
- End-to-end candidate, recruiter, interview, call, evaluation, explicit human outcome, and audit scenario. **The synthetic candidate-to-human-review path is implemented and validated; broader escalation/operational scenarios remain.**
- ML quality, bias, safety, latency, and regression evaluation. **Deterministic scoring has synthetic repeatability, threshold, fairness, privacy, authorization, atomicity, and local query-budget coverage. Candidate-owned local Faster-Whisper transcription is integrated with transient audio, explicit text review, and injected regression coverage. Ignored local Faster-Whisper base, Silero VAD, and Piper Plus weights now pass a synthetic in-memory inference smoke check; real microphone and browser QA remain deferred. A detached Qwen3B shared proposal runtime, local permission-filtered RAG, and nine-agent contracts are implemented for evaluation only. Task 3's 100-case held-out Qwen run reached 99/100 contextual actions and 100/100 accepted schemas, but it remains detached and is not a release gate for live use.**
- **QA-isolated model-action integration:** **Implemented but not yet execution-complete.** The dedicated database was verified before a process restart, and the QA-only three-turn adapter, strict model-action gate, real local speech/RAG sequence, deterministic persistence, advisory evaluation, and audit checks are implemented. Three fail-closed attempts persisted no answers; the corrected sequence still needs a fresh verified run after QA variables are restored to this process. Real candidate-facing AI remains disabled.
- Retention/anonymization jobs, monitoring, protected backups, and incident procedures. **A dry-run-first bounded answer/transcript anonymization command, normalized audit-linked run evidence, incident runbook, and explicitly unverified backup/restore checklist are implemented; monitoring, provider backups, restore rehearsal, file retention, and broader legally reviewed policies remain.**
- Production configuration validation, fixed liveness endpoint, lightweight Render build/start boundary, deployment guidance, operator preflight, and release-candidate handoff. **Repository-side hardening and validation are implemented; manual QA, infrastructure, external media/email, migration execution, smoke testing, monitoring, backups, and deployment remain.**

### Required tests

- Full integration, system, end-to-end, security, permission, failure, and regression suites.
- Evaluation-quality and safety test sets using synthetic or approved non-private data.
- Production settings and deployment smoke tests.

### Security requirements

- HTTPS, secure cookies, trusted origins, restricted database roles, protected media, encrypted backups, and dependency review.
- Tested retention, deletion, incident, audit-integrity, and human-approval controls.
- No automatic final employment decisions.

### Completion criteria

- The documented end-to-end workflow is demonstrable and validated.
- Authorized humans control final decisions.
- Security, privacy, audit, recovery, and operational documentation match the implementation.
- All required checks pass from a clean checkout.

## Overall status

- Week 1: 100%
- Week 2: 100%
- Week 3: 100%
- Week 4: 75%
- Overall: 94%

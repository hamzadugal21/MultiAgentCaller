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

## Week 2 — Core recruitment workflows (0% complete)

### Objectives

Turn the schema foundation into secure candidate, recruiter, job, application, and scheduling workflows using Django templates and shared static assets.

### Tasks and deliverables

- Candidate profile editing and consent management.
- Secure resume upload, replacement, metadata, and ownership controls.
- Recruiter/company administration with verified role permissions.
- Job creation, editing, publishing, skill requirements, questions, and FAQs.
- Candidate application and withdrawal flow.
- Interview scheduling, invitation, confirmation, rescheduling, and cancellation flow.
- Frontend implementation based on supplied Figma screenshots when available.
- Audit events for consequential data access and changes.

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
- Consent and audit records are enforced.
- No migration drift or failing validation remains.

## Week 3 — Voice calling and multi-agent system (0% complete)

### Objectives

Implement the browser call runtime, local speech pipeline, orchestration, specialist agents, safety controls, and escalation.

### Tasks and deliverables

- Channels/Redis call connection, lifecycle, reconnect, event, and metric handling.
- Silero VAD, Faster Whisper STT, Piper TTS, and interruption/turn-taking flow.
- Calling orchestrator and profile, interview, FAQ, scheduling, safety, escalation, evaluation, and audit agent interfaces.
- Versioned prompts, allowlisted tools, bounded context, retries, timeouts, and structured outputs.
- Redaction, consent enforcement, recording-disabled default, and retention metadata.
- Human escalation and action-approval workflow.

### Required tests

- Unit tests for audio adapters, orchestration transitions, tools, prompts, safety rules, and redaction.
- Integration tests for simulated calls, failures, reconnects, handoffs, and escalation.
- Deterministic fixtures must contain no real candidate data.

### Security requirements

- Treat candidate speech and retrieved text as untrusted input.
- Prevent prompt injection from authorizing tools or bypassing policy.
- Minimize private context and redact logs/transcripts.
- Require human approval for sensitive actions and final employment outcomes.

### Completion criteria

- A consented simulated browser interview completes through the local speech and agent pipeline.
- Safety and escalation scenarios are tested and auditable.
- Failure recovery does not silently make or finalize decisions.

## Week 4 — Evaluation, integration, and production readiness (0% complete)

### Objectives

Complete human-reviewed evaluation, end-to-end integration, operational safeguards, documentation, and release readiness.

### Tasks and deliverables

- Rubric-based evidence, scoring, confidence, recommendations, and reviewer workflow.
- Recruiter review UI with explicit human finalization.
- End-to-end candidate, recruiter, interview, call, escalation, and audit scenarios.
- ML quality, bias, safety, latency, and regression evaluation.
- Retention/anonymization jobs, monitoring, protected backups, and incident procedures.
- Production configuration validation, deployment guidance, API documentation, and operator runbooks.

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
- Week 2: 0%
- Week 3: 0%
- Week 4: 0%
- Overall: 25%

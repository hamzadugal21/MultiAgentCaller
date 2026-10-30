# Work Log

Append new entries in chronological order. Do not rewrite historical entries. Record verified outcomes, exact test results, warnings, errors, blockers, and commit identifiers without including secrets or private candidate data.

## 2026-10-22 — Week 1 secure foundation

Commit `7b3581c` — `chore: establish secure week 1 foundation`

- Created the Django 6.1/PostgreSQL project foundation and seven domain applications.
- Added the custom email user model, candidate-only public signup, three roles, role dashboards, Argon2, login throttling configuration, and POST-only logout.
- Added core recruitment, interview, call, agent, audit, candidate, resume, consent, evaluation, escalation, and retention schema foundations.
- Added resume format/size checks, privacy-safe authentication auditing, keyed audit hashes, and PostgreSQL protection against audit-event update/deletion.
- Added development/production settings, requirements, templates, stylesheet, security policy, and automated tests.

## 2026-10-22 — Case-insensitive email integrity

Commit `3e9ec9b` — `fix: enforce case-insensitive user emails`

- Canonicalized complete email addresses to lowercase in `UserManager.create_user()`.
- Added PostgreSQL constraint `accounts_user_email_ci_unique` using `Lower("email")`.
- Added migration `accounts.0002_user_accounts_user_email_ci_unique` without rewriting applied history.
- Added tests for manager normalization, direct-save duplicate rejection, and case-insensitive signup rejection.

## 2026-10-22 — Project structure reorganization

Commit `614aba6` — `chore: reorganize project structure`

- Moved Django management, configuration, applications, migrations, and app tests under `backend/` while preserving app labels and Git history.
- Moved shared templates and static source assets under `frontend/`.
- Added `database/`, `ai_system/`, `ml/`, `docs/`, `scripts/`, `tests/`, and `var/` responsibility boundaries.
- Updated Django roots, root environment-file path, template/static/media paths, pytest Python path, Ruff source root, ignore rules, and README commands.
- Verified template/static discovery, PostgreSQL access, ASGI/WSGI imports, migration history, and absence of legacy duplicate paths.

## 2026-10-22 — Week 1 validation baseline

- Tests: **28 passed**.
- Django system check: **0 issues**.
- Migration drift: **no changes detected**.
- Applied accounts migrations: `0001_initial`, `0002_user_accounts_user_email_ci_unique`.
- Dependency check: **no broken requirements**.
- Ruff: **all checks passed**.
- Known non-failing warnings: two Daphne warnings about Windows asyncio policy APIs deprecated for Python 3.16, and one pytest-cache permission warning.
- Week 1 completion: **100%**.
- Week 2 product completion: **0%**.
- Overall four-week completion: **25%**.

## 2026-10-22 — Persistent project context

- Added the repository-wide agent operating guide, authoritative AI handoff, four-week roadmap, decision log, append-only work log, and architecture guide.
- Added an ignored local four-prompt counter under `var/agent-state/` with a tracked directory placeholder.
- No Week 2 product functionality was implemented.
- Validation: Django system check reported 0 issues; migration check reported no changes; 28 tests passed with 3 known warnings in 2.92 seconds; dependency check found no broken requirements; Ruff passed; Git diff check passed.
- Commit message: `docs: add persistent project context`. The containing commit is discoverable from Git; subsequent agents must verify `HEAD` before work.

## 2026-10-23 — Week 2 Milestone 2.1A deterministic audit foundation

- Branch: `feat/week-2-core-workflows`; base checkpoint: `d2b2b5f`.
- Added a deterministic Python domain-audit service with a frozen command type and explicit event specifications for profile, consent, email verification, resume, company/recruiter administration, job, application, and interview-scheduling domains.
- Added strict event/category/resource matching, specification-owned canonical actions, required and allowed metadata rules, an immutable registry, actor and UUID validation, payload bounds, private-data rejection, safe persistence errors, and caller-controlled transaction compatibility.
- Preserved the existing immutable `AuditEvent` model, PostgreSQL protection trigger, authentication audit signals, and `AgentDefinition` values. No migration was created and no operational AI agent was added.
- Added 34 tests covering valid creation, required fields and metadata, canonical action ownership, caller-action rejection, immutable and exact registry declarations, optional metadata, unknown events/keys, forbidden and oversized metadata, UUID normalization, actor snapshots, safe failures, and continued immutable model/queryset/database behavior.
- Validation: Django system check reported 0 issues; migration check reported no changes; 56 focused audit/account tests and 62 total tests passed; dependency check found no broken requirements; Ruff and Git diff checks passed.
- Known non-failing warnings: two Daphne Python 3.16 asyncio deprecation warnings and one pytest-cache permission warning.
- `JobApplication.__str__` and `AgentHandoff.__str__` contain the intended Unicode arrow `U+2192`, not a control character; no unrelated cleanup was made.
- Week 2 completion: **5%**. Overall four-week completion: **26%**.
- Checkpoint commit message: `feat: add deterministic domain audit service`; resolve the containing hash with Git.
- Next: wait for approval before beginning Milestone 2.1B policies/schema.

## 2026-10-23 — Automatic context checkpoint

- Branch: `feat/week-2-core-workflows`; commit: `988867b`; worktree: clean before the current task.
- Completed work: Milestone 2.1A deterministic domain audit service is committed and validated.
- Current task: prepare only a lightweight Render dependency manifest; no task files had changed at checkpoint time.
- Latest validation: Django system check reported 0 issues; migration check reported no changes; 56 focused audit/account tests and 62 total tests passed; dependency check found no broken requirements; Ruff and Git diff checks passed.
- Errors and blockers: none. Known warnings: two Daphne Python 3.16 asyncio deprecation warnings and one pytest-cache permission warning.
- Week 2 completion: **5%**. Overall four-week completion: **26%**.
- Next: create and validate `requirements/render.txt`, record the dependency decision, and wait for approval before committing; do not deploy or begin Milestone 2.1B.

## 2026-10-23 — Lightweight Render dependency preparation

- Added `requirements/render.txt` with only `-r base.txt`; `requirements/production.txt` remains unchanged.
- Confirmed the recursive dry-run includes the Django/Channels, Daphne, Redis, PostgreSQL, environment, static-file, authentication/security, and PDF/DOCX stack without the local ML manifest or its heavy packages.
- Recorded that the future free hosted demonstration will clearly label AI-call behavior as simulated while the real Whisper/Piper/PyTorch pipeline remains locally runnable.
- Deferred Render services, build commands, health endpoints, production settings, object storage, and deployment execution to the final deployment milestone.
- Validation: pip install dry-run completed successfully with every dependency already satisfied; pip check found no broken requirements; Django system check reported 0 issues; 62 tests passed; Ruff and Git diff checks passed.
- Known non-failing warnings: two Daphne Python 3.16 asyncio deprecation warnings and one pytest-cache permission warning. Errors and blockers: none.
- Changed tracked files: `requirements/render.txt`, `docs/DECISIONS.md`, `docs/AI_HANDOFF.md`, and `docs/WORK_LOG.md`.
- Week 2 completion remains **5%** and overall completion remains **26%** because this is deployment preparation, not product functionality.
- Next: review and approve this uncommitted manifest; do not deploy or begin Milestone 2.1B.

## 2026-10-23 — Persistent Render deployment plan

- Added `docs/development/RENDER_DEPLOYMENT.md` as the authoritative plan for a future completely free public CV demonstration.
- Recorded the planned Render, Neon, Upstash, future S3-compatible storage, and sanitized GitHub boundaries without creating accounts or connecting services.
- Clearly separated the hosted simulated AI-call mode from the real locally runnable Whisper/Piper/Silero VAD/PyTorch pipeline.
- Recorded the Week 4 deployment checklist, deferred provider and configuration decisions, synthetic-data requirement, and secret/media safety rules.
- Added short links from the README, AI handoff, and Week 4 roadmap without changing Week 2 ordering or completion percentages.
- This is deployment preparation only and does not count as Week 2 product functionality. No application code, runtime behavior, settings, dependencies, or deployment service was changed.
- Validation: all documented local paths resolve; no deferred deployment artifact exists; only the new Render manifest changed under `requirements/`; no application/runtime source path changed; Git diff check passed.
- Next: review the uncommitted dependency manifest and deployment documentation; do not deploy or begin Milestone 2.1B.

## 2026-10-26 — Automatic context checkpoint during Milestone 2.1B

- Branch: `feat/week-2-core-workflows`; commit: `eb48e50`; worktree: uncommitted Milestone 2.1B changes only.
- Completed work: Render preparation is committed at `eb48e50`; its dependencies are installed locally with every package already satisfied, the import smoke test prints `RENDER DEPENDENCIES ARE READY`, and pip reports no broken requirements. Nothing was deployed or pushed.
- Current task: append-only consent history. Added the consent schema and service implementation, three new auditlog migrations, audit-registry integration, and PostgreSQL-backed tests. Migrations `auditlog.0003` through `0005` are applied locally.
- Changed files at checkpoint: `backend/auditlog/models.py`, `backend/auditlog/services.py`, `backend/auditlog/consent_services.py`, migrations `0003`-`0005`, `backend/auditlog/tests.py`, `backend/auditlog/test_consent_services.py`, and `backend/auditlog/test_database_protection.py`, plus required context documents.
- Validation so far: migration generation found one pre-migration Python scope error, corrected before any migration was created; the first focused run found one stale audit test resource type, corrected immediately. The rerun passed 65 focused tests. Migration drift and Ruff checks passed before this checkpoint. Full-suite and final validation remain.
- Known warnings: two Daphne Python 3.16 asyncio deprecation warnings and one pytest-cache permission warning. Blockers: none.
- Week 2 completion remains **5%** and overall completion remains **26%** until Milestone 2.1B completes full validation.
- Next: finish full validation, update final test totals/progress, and present Milestone 2.1B for review without committing or starting email verification.

## 2026-10-26 — Milestone 2.1B append-only consent history ready for review

- Added `auditlog.ConsentRecord` with protected domain relationships, policy-versioned grant/revoke evidence, a global UUID idempotency key, request/correlation IDs, stable check constraints/indexes, model immutability, and PostgreSQL update/delete protection.
- Added deterministic general and application-interview grant/revoke/resolution services. They lock the mutable profile/application cache row, reload actor and schedule authority from PostgreSQL, enforce scope/ownership, synchronize caches, deduplicate identical state, support policy reconfirmation and schedule-linked evidence, and persist mandatory privacy-safe audit events in the same transaction.
- Added separate schema, legacy-backfill, and trigger migrations. Historical true caches become actorless `legacy-unversioned` grants without migration-time audit events; caches are reset, false values create no revocation, and current-policy re-consent is required.
- Applied auditlog migrations `0003`, `0004`, and `0005`. Django check found 0 issues and migration drift check found no changes.
- Validation: 26 new consent/immutability tests passed; 68 focused audit/candidate/recruitment tests passed; 88 complete tests passed; pip check, Ruff, and migration checks passed. The final pytest runs used process-local `OPENBLAS_NUM_THREADS=1` after the low-memory host rejected native allocations without it.
- Known non-failing warnings: two Daphne Python 3.16 asyncio deprecation warnings and one pytest-cache permission warning. No code blocker remains.
- Week 2 is **10%** complete and overall project progress is **28%**. Milestone 2.1B is uncommitted and ready for review.
- Next: approve a focused Milestone 2.1B commit; do not begin email verification before approval.

## 2026-10-26 — Milestone 2.1B consent integrity corrections

- Enforced persisted candidate role and ownership for candidate-originated consent; administrator assistance requires a persisted administrator/superuser and the explicit `admin_assisted` source.
- Corrected idempotency so only reuse of the same key replays an existing result. A different key always records a new explicit immutable action and audit event; callers must reuse a key for network retries.
- Corrected effective-consent resolution to inspect the latest record across every policy version. Only a latest grant under the requested non-legacy policy authorizes processing; later revocation or another-policy evidence blocks an older grant.
- Policy versions now use the exact deterministic-audit safe-code character rules before persistence.
- Added stale-role, recruiter denial, administrator-source, new-key history, safe policy-code, and general/application cross-policy ordering tests.
- Validation: Django check reported 0 issues; migration drift reported no changes; 77 focused tests and 97 complete tests passed; pip check, Ruff, and Git diff checks passed.
- Known warnings remain two Daphne Python 3.16 asyncio deprecations and one pytest-cache permission warning. No blocker remains.
- Next: commit Milestone 2.1B as `feat: add append-only consent history`, then begin the email-verification foundation.

Milestone commit: `bee8785` (`feat: add append-only consent history`).

## 2026-10-26 — Milestone 2.1C secure email-verification foundation

- Added `accounts.EmailVerificationChallenge` with UUID identity, user relationship, unique keyed token digest, keyed normalized-email binding, purpose version, expiry/used/invalidation timestamps, and optional request UUID.
- Added versioned Django signing with a cryptographically random nonce, 24-hour configurable lifetime, row-locked single-use consumption, resend invalidation, email-change invalidation, and configurable request/resend/invalid-attempt rate limits.
- Raw tokens, token URLs, email addresses, and plain email digests are not stored or audited. Requested, succeeded, failed, and invalidated events use deterministic allowlisted audit specifications.
- Added migration `accounts.0003_emailverificationchallenge`; it is applied and migration drift is absent.
- Added 14 focused model/service/security tests covering HMAC boundaries, consumption/replay, expiry, invalid tokens, resend, email changes, rate limits, audit privacy, database constraints, and audit-failure rollback.
- Validation: Django check reported 0 issues; 105 focused accounts/audit tests and 111 complete tests passed; pip check, Ruff, migration, and Git diff checks passed.
- Known warnings remain two Daphne Python 3.16 asyncio deprecations and one pytest-cache permission warning. No blocker remains.
- Week 2 is **15%** complete and overall progress is **29%**.
- Next: commit as `feat: add secure email verification foundation`, then implement deterministic transition/schema foundations.

Milestone commit: `8579159` (`feat: add secure email verification foundation`).

## 2026-10-26 — Milestone 2.1D deterministic workflow foundations

- Added immutable transition tables and transactional, audited services for job postings, job applications, interview schedules, resume processing/activation, and consent actions.
- Enforced persisted actor roles, recruiter verification/capabilities, company/candidate ownership, explicit allowed state edges, system-only expiry, terminal states, and safe failure codes.
- New resumes default inactive; the old active resume remains active through replacement processing and is atomically replaced only after successful completion.
- Added `InterviewSchedule.invitation_expires_at` and minimal `InterviewRescheduleRequest` persistence with schedule/status indexes, valid-time constraint, and one-pending-request constraint.
- Created and applied `candidates.0003_alter_resume_is_active` and `interviews.0002_interviewschedule_invitation_expires_at_and_more`; migration drift is absent.
- Added eight focused transition tests. Validation: 79 focused tests and 119 complete tests passed; Django check found 0 issues; pip check, Ruff, and Git diff checks passed.
- Known non-failing warnings: two Daphne Python 3.16 asyncio deprecations and one pytest-cache permission warning. The initial focused run exposed duplicate candidate-profile fixtures because the existing signal already creates profiles; the fixtures were corrected and the rerun passed.
- Week 2 is **20%** complete and overall progress is **31%**.
- Next: commit `feat: add deterministic workflow foundations`, then implement Milestone 2.2 candidate workflow.

Milestone commit: `6aab484` (`feat: add deterministic workflow foundations`).

## 2026-10-26 — Milestone 2.2 candidate workflow

- Added candidate-only, allowlisted profile editing and append-only general-consent grant/revoke actions. Role, ownership, protected fields, POST-only consent mutation, and deterministic audits are enforced.
- Added generic email-verification request/resend pages and a POST confirmation flow backed by the committed signed/HMAC challenge service. Tokens remain absent from storage and audit metadata.
- Added protected PDF/DOCX upload, randomized storage names, SHA-256 metadata, pending/inactive records, bounded pypdf/python-docx extraction outside long transactions, safe status codes, successful-only atomic activation, and owner-only downloads.
- Parsing enforces PDF page, DOCX archive-entry/expanded-size, and extracted-character limits. Structural validation is explicitly not described as malware scanning.
- Added ten candidate/verification view and workflow tests. Validation: 57 focused tests and 129 complete tests passed; Django check found 0 issues; migration drift is absent; pip check, Ruff, and Git diff checks passed.
- Known warnings remain two Daphne Python 3.16 asyncio deprecations and one pytest-cache permission warning. No blocker remains.
- Week 2 is **40%** complete and overall progress is **35%**.
- Next: commit `feat: add candidate profile consent and resume workflow`, then implement Milestone 2.3 recruiter/company/job workflows.

Milestone commit: `57f1cb3` (`feat: add candidate profile consent and resume workflow`).

## 2026-10-26 — Milestone 2.3 recruiter, company, and job workflow

- Added deterministic administrator-only company creation and recruiter provisioning with safe audit metadata; Django admin exposes trusted company/recruiter management and enforces recruiter-role selection.
- Added persisted recruiter authorization requiring active recruiter role, verified profile, active own company, and `can_manage_jobs` capability.
- Added company-scoped job create/edit/list/detail services and templates. Client-supplied company, creator, and status values are excluded; all jobs begin as drafts and publishing uses the transition service.
- Added job skill requirements, interview questions, FAQs, and authenticated-candidate-only browsing of open, unexpired jobs from active companies.
- Added seven focused security/workflow tests plus the transition suite. Validation: 10 focused tests and 136 complete tests passed; Django check found 0 issues; migration drift is absent; pip check, Ruff, and Git diff checks passed.
- Known warnings remain two Daphne Python 3.16 asyncio deprecations and one pytest-cache permission warning. No blocker remains.
- Week 2 is **60%** complete and overall progress is **40%**.
- Next: commit `feat: add recruiter company and job workflows`, then implement Milestone 2.4 application workflow.

Milestone commit: `44342b4` (`feat: add recruiter company and job workflows`).

## 2026-10-26 — Milestone 2.4 application workflow

- Added candidate-only application creation with persisted active-role and verified-email checks, open/active-company/deadline eligibility, candidate-owned completed active resume enforcement, and database-backed duplicate prevention.
- Application forms expose only resume, cover note, and optional AI-interview consent; candidate, status, company, and other protected fields cannot be mass assigned.
- Added optional append-only application interview consent, privacy-safe deterministic creation/status audits, candidate history views, and company-scoped recruiter review requiring `can_review_candidates`.
- Added candidate withdrawal before call start. A current pending/confirmed schedule is cancelled through the shared interview service inside the same transaction; withdrawal is blocked after a call has begun.
- Added eight focused application/security tests. Validation: 14 focused tests and 144 complete tests passed; Django check found 0 issues; migration drift is absent; pip check, Ruff, and Git diff checks passed.
- Known warnings remain two Daphne Python 3.16 asyncio deprecations and one pytest-cache permission warning. No blocker remains.
- Week 2 is **75%** complete and overall progress is **44%**.
- Next: commit `feat: add secure candidate application workflow`, then implement Milestone 2.5 scheduling.

Milestone commit: `4eb76b3` (`feat: add secure candidate application workflow`).

## 2026-10-26 — Milestone 2.5 interview invitation and scheduling workflow

- Added company-scoped recruiter invitation creation and notification, requiring verified candidate email plus current general and application AI consent.
- Invitation tokens use a versioned signed payload and keyed-HMAC digest; raw tokens are never stored or audited. Expiry is the earlier of 48 hours or scheduled start. Persisted idempotency and delivery state support safe retry after mail failure.
- Added row-locked, single-use candidate confirmation with schedule-linked consent evidence, UTC persistence, IANA timezone validation, cancellation, and system-only due expiration.
- Added candidate reschedule requests and recruiter approval/rejection. Approval atomically retires the old schedule, activates a new pending schedule, and creates a new invitation; rejection leaves the existing schedule unchanged.
- Created and applied `interviews.0003_interviewschedule_invitation_delivery_status_and_more`; migration drift is absent.
- Added nine focused scheduling/security tests. Validation: 46 focused tests and 153 complete tests passed; Django check found 0 issues; pip check, Ruff, and Git diff checks passed.
- The first focused run found a test retry with changed microseconds and a stale returned replacement object; the test now reuses identical semantics and the service refreshes the replacement before returning. No blocker remains.
- Known warnings remain two Daphne Python 3.16 asyncio deprecations and one pytest-cache permission warning.
- Week 2 is **90%** complete and overall progress is **48%**.
- Next: commit `feat: add interview invitation and scheduling workflow`, then complete Milestone 2.6 integration/security validation.

Milestone commit: `fd9a6e4` (`feat: add interview invitation and scheduling workflow`).

## 2026-10-26 — Milestone 2.6 integration/security and Week 2 completion

- Added a complete pre-interview integration test: administrator provisioning, recruiter job publication, candidate signup/verification/profile/consent/resume, job browsing/application, company-scoped review, invitation delivery, candidate confirmation, and consequential audit verification.
- Added CSRF enforcement with `Client(enforce_csrf_checks=True)` and template-escaping coverage. Existing focused suites cover cross-company/cross-candidate IDOR, mass assignment, GET mutation, invalid/expired/replayed tokens, upload abuse, email rate limits, unverified email, revoked consent, invalid transitions, audit privacy, and raw-token non-persistence.
- Hardened scheduling errors at the service boundary, prevented direct access to ineligible application pages, and made verification delivery failures return the same generic response without exposing mail internals.
- Final migration state includes accounts `0001`-`0003`, auditlog `0001`-`0005`, candidates `0001`-`0003`, interviews `0001`-`0003`, and recruitment `0001`, all applied with no drift.
- Validation after the integration changes: 48 focused integration/security tests and 156 complete tests pass; Django check reports 0 issues; pip check reports no broken requirements. The first final run stopped at two mechanical Ruff findings, which were corrected before the required complete rerun.
- Known non-failing warnings remain two Daphne Python 3.16 asyncio deprecations and one pytest-cache permission warning.
- Week 2 is **100%** complete and overall four-week progress is **50%**.
- Final Week 2 checkpoint: `064100a` (`feat: complete week 2 recruitment workflows`).
- Next: begin Week 3 only after review/approval.

## 2026-10-26 — Week 2 documentation synchronization

- Branch: `feat/week-2-core-workflows`; previous HEAD: `d26bf19`; validated Week 2 product checkpoint: `064100a`.
- Corrected the roadmap's overall project percentage to 50%, distinguished the documentation HEAD from the validated product checkpoint in the AI handoff, described committed `ConsentRecord` architecture instead of an uncommitted worktree, and updated the cross-application test README for the completed Week 2 integration/security coverage.
- No application code, tests, migrations, settings, dependencies, or runtime behavior changed.
- Week 2 remains **100%** complete and overall four-week progress remains **50%**.
- Next remains the Week 3 deterministic call-session/runtime boundary and simulated local call lifecycle; Week 3 has not started.

## 2026-10-27 — Week 3 Milestone 3.1 deterministic call-session foundation

- Created branch `feat/week-3-ai-interview-runtime` from Week 2 documentation checkpoint `40881db`; product commit: `2bd2710` (`feat: add deterministic call-session foundation`).
- Added one simulated call session per confirmed interview schedule, UUID creation idempotency, explicit lifecycle states, expiry/question/timestamp fields, stable database constraints/indexing, and a forward-only migration that safely maps legacy lifecycle values.
- Added transactional creation, actor-scoped reads, and transition services. They reload actors from PostgreSQL; enforce candidate ownership, recruiter capability/company isolation, administrator boundaries, confirmed/current schedules, verified email, current general/application consent, scheduled start limits, and system-only readiness/expiry/failure.
- Added nine canonical, allowlisted call-session audit specifications. Audit persistence is mandatory in the state-change transaction, and metadata excludes private candidate content, tokens, transcripts, resume text, and filesystem paths.
- Updated application withdrawal protection to use the authoritative `started_at` boundary after the lifecycle rename.
- Added nine PostgreSQL-backed service/security tests. Focused runs passed 80 calling/audit tests and 98 calling/audit/recruitment tests. Final validation passed 165 tests; Django check reported 0 issues; migrations applied with no drift; pip check, Ruff, and Git diff checks passed.
- The first migration-generation attempt found a Python nested-`Meta` scope error before creating a migration; it was corrected to use stable stored values. The first complete test run then found one Week 2 test using the retired `IN_PROGRESS` name; the withdrawal guard and test were updated, and the complete rerun passed.
- Known non-failing warnings remain two Daphne Python 3.16 asyncio deprecations and one pytest-cache permission warning.
- Week 3 is **15%** complete; overall four-week progress is **54%**.
- Next: implement Milestone 3.2's deterministic server-rendered simulated interview lifecycle before WebSockets, Redis runtime state, voice adapters, or generative orchestration.

## 2026-10-27 — Week 3 Milestone 3.2 simulated interview lifecycle

- Product commit: `473ea99` (`feat: add simulated interview lifecycle`).
- Added `calling.SimulatedInterviewResponse` with protected session/question relationships, deterministic question index, bounded service/form input, unique answer/idempotency constraints, and session/time indexing; migration `calling.0003_simulatedinterviewresponse` is applied with no drift.
- Added candidate pages to prepare, start, pause, resume, answer, complete, and cancel a clearly labelled text simulation. Only active job-owned questions are selected in deterministic order, at least one approved question is required, and repeat network submissions reuse UUID idempotency.
- Added company-scoped recruiter and administrator operational views. They expose status/progress but never candidate answer content, and they cannot perform candidate-only actions.
- All mutations are POST-only and use Django CSRF protection. Candidate ownership, current consent, verified email, schedule eligibility, state transitions, answer bounds, and audit rollback are enforced in services rather than templates.
- Added privacy-safe `call_session.answer_submitted` auditing with identifiers/index only. Answer text is private domain data and is not copied into audit metadata.
- Validation: 87 focused calling/audit tests and 172 complete tests passed; Django check reported 0 issues; all migrations are applied with no drift; pip check, Ruff, and Git diff checks passed.
- Known non-failing warnings remain two Daphne Python 3.16 asyncio deprecations and one pytest-cache permission warning. No blockers remain.
- Week 3 is **40%** complete; overall four-week progress is **60%**.
- Next: implement Milestone 3.3 authenticated, session-scoped Channels/WebSocket status transport while preserving the deterministic HTTP simulation as fallback.

## 2026-10-27 — Week 3 Milestone 3.3 authorized WebSocket status transport

- Product commit: `a64e9be` (`feat: add authorized call status websocket`).
- Replaced the HTTP-only ASGI callable with a Channels `ProtocolTypeRouter` while preserving Django HTTP handling. WebSocket routes use allowed-host origin validation and Django session authentication.
- Added exact call-session authorization at connection and before every outgoing update, UUID-derived per-session groups, server-derived allowlisted status snapshots, unsupported-message errors, and safe close behavior.
- Added on-commit status publishing after domain session changes. PostgreSQL remains authoritative; development uses the in-memory channel layer and production retains the existing Redis channel layer. Delivery failure is non-destructive because the validated HTTP simulation remains available.
- WebSocket payloads contain only event type, session UUID, lifecycle status, question index, and simulated-mode flag. Caller-supplied group payloads are ignored, preventing answer, transcript, résumé, token, prompt, path, or secret forwarding.
- Added two PostgreSQL-backed communicator tests covering unauthenticated denial, candidate ownership, cross-company recruiter denial, administrator access, safe error messages, per-session isolation, and server-derived payloads.
- Validation: 18 focused calling tests and 174 complete tests passed; Django check reported 0 issues; no migration drift; pip check and Ruff passed; supported ASGI import returned `ProtocolTypeRouter`; Git diff check passed.
- The initial WebSocket test run had two harness-only failures: an unconfigured test origin reached the origin validator first, and a session cookie was created inside async code. Cookie setup was moved to synchronous test setup and the configured localhost origin was used; the rerun passed.
- A first plain root Python ASGI smoke command lacked `backend/` on `sys.path`; the supported `backend/manage.py shell` check succeeded. No runtime configuration changed for that command issue.
- Known non-failing warnings remain two Daphne Python 3.16 asyncio deprecations and one pytest-cache permission warning. No blocker remains.
- Week 3 is **60%** complete; overall four-week progress is **65%**.
- Next: implement Milestone 3.4 optional local voice adapter boundaries without persisting recordings or changing the Render dependency boundary.

## 2026-10-27 — Week 3 Milestone 3.4 optional local voice adapters

- Product commit: `40789e2` (`feat: add optional local voice adapters`).
- Added typed transient mono PCM and structured VAD/STT/TTS/input/output contracts under `ai_system/voice/`.
- Added lazy local adapters under `ml/voice/` for Silero VAD, Faster Whisper, and the pinned piper-plus package. Faster Whisper is local-files-only and Piper requires a trusted local `.onnx` model; no model was downloaded or run during validation.
- Added deterministic unavailable/failed status codes, bounded transient audio/text, an unsupported microphone fallback, and a discarding output. Internal exception text and model paths are not returned.
- No raw audio is audited or persisted, no recording path is used, no wall-clock timeout is claimed without process isolation, and the deterministic text simulation remains independent and usable.
- Added eight synthetic adapter tests covering invalid PCM, lazy loading, VAD segments, STT bounds, missing TTS model, generated in-memory WAV, safe failures, and non-retention. No live microphone, voice hardware, or generative API test was added.
- Validation: 8 focused adapter tests and 182 complete tests passed; Django check reported 0 issues; no migration drift; pip check and Ruff across `backend`, `ai_system`, and `ml` passed; Git diff check passed.
- `requirements/render.txt`, `requirements/base.txt`, and `requirements/production.txt` were unchanged; heavy local ML dependencies remain outside the Render chain.
- Known non-failing warnings remain two Daphne Python 3.16 asyncio deprecations and one pytest-cache permission warning. No blocker remains.
- Week 3 is **75%** complete; overall four-week progress is **69%**.
- Next: implement Milestone 3.5's narrow deterministic interview coordinator and allowlisted action boundary without selecting a generative model.

## 2026-10-27 — Week 3 Milestone 3.5 deterministic interview coordinator

- Product commit: `da6cf21` (`feat: add deterministic interview coordinator`).
- Added a versioned, model-free coordinator with immutable action and state/directive maps. The exact commands are status, start, pause, cancel, and submit answer; unsupported or malformed commands stop with fixed safe codes.
- Added a narrow Django tool adapter that reloads candidate authority and calls only existing call-session state/answer services. It cannot expose arbitrary ORM, SQL, filesystem paths, model selection, recipients, external messaging, evaluation scores, or hiring outcomes.
- Coordinator snapshots expose one active, approved job-owned question at a time. Mutation services continue to enforce current consent, verified email, schedule window, ownership, state, idempotency, and mandatory privacy-safe audit records.
- Added four coordinator tests covering versioned start/question/progression/completion behavior, the exact action allowlist, recruiter impersonation denial, and internal-error redaction. No generative model or fake generative-agent test was added.
- Validation: 30 focused calling/coordinator tests and 186 complete tests passed; Django check reported 0 issues; no migration drift; pip check, Ruff across backend/AI/ML, and Git diff checks passed.
- Known non-failing warnings remain two Daphne Python 3.16 asyncio deprecations and one pytest-cache permission warning. No blocker remains.
- Week 3 is **90%** complete; overall four-week progress is **73%**.
- Next: complete Milestone 3.6 deterministic safety/escalation controls and Week 3 integration/security validation.

## 2026-10-28 — Week 3 Milestone 3.6 safety, escalation, and completion

- Product commit: `897aacc` (`feat: complete week 3 interview runtime`) on `feat/week-3-ai-interview-runtime`.
- Added deterministic row-locked expiry processing, candidate-requested human assistance, and atomic technical-failure escalation. Candidate requests pause active sessions; technical failures enter `failed`; neither path makes or implies an employment decision.
- Added UUID idempotency/replay/conflict handling, persisted actor and ownership authorization, canonical policy descriptions, fixed safe errors, privacy-safe `call_session.escalated` auditing, and transactional rollback when mandatory audit persistence fails.
- Added migration `agents.0002_agentescalation_idempotency_key_and_more`, applied successfully with no migration drift. It permits deterministic service-originated escalation records and adds safe reason/idempotency fields without editing prior migrations.
- Extended the model-free coordinator's exact allowlist with `request_human`, added a POST/CSRF-protected candidate control, and preserved the simulated HTTP path, recording-disabled default, and status-only WebSocket boundary.
- Added a synthetic cross-application Week 3 integration test covering confirmed schedule, current consent, approved question progression, completion, and private-data-free audits. Added focused expiry, escalation, authorization, idempotency, rollback, CSRF, IDOR, and coordinator tests.
- Validation: 109 focused audit/calling/agents/integration tests passed before final hardening; 65 focused safety/integration tests passed after idempotency hardening; the final complete suite passed **195 tests**. Django check reported 0 issues; migrations applied with no drift; pip check reported no broken requirements; Ruff across backend/AI/ML/tests and Git diff checks passed.
- The first focused run had one test-ordering failure because CSRF correctly rejected an IDOR request before object lookup; the test was split so CSRF and object authorization are independently verified. The initial migration command was blocked by the managed sandbox's base-Python boundary and succeeded unchanged with scoped permission.
- Known non-failing warnings remain two Daphne Python 3.16 asyncio deprecations and one pytest-cache permission warning. No blocker remains.
- Week 3 is **100%** complete; overall four-week progress is **75%**.
- Next: begin Week 4 deterministic advisory evaluation and authorized human-review design only after approval. Week 4 has not started.

## 2026-10-29 — Figma homepage implementation

- Branch: `feat/week-3-ai-interview-runtime`; documentation HEAD before the task: `5b37ca8`; latest validated Week 3 product checkpoint: `897aacc`.
- Implemented the Figma `Home / Desktop 1440` frame (`7:2`) as the public `accounts:home` Django route with semantic HTML and a dedicated responsive stylesheet. The page covers the approved navigation, hero, candidate-dashboard preview, benefits, recruitment process, trust section, final CTA, and footer without embedding a design screenshot or adding JavaScript.
- Added two homepage route/template/link tests. Validation reported 0 Django system-check issues, no migration drift, 39 focused account tests passed, 197 complete tests passed, no broken requirements, Ruff passed, and `git diff --check` passed.
- The first complete-test attempt encountered a low-memory failure while the temporary development server was running; the server was stopped and the clean rerun passed. Known non-failing warnings remain two Daphne Python 3.16 asyncio deprecations and one pytest-cache permission warning.
- The Figma file contains 16 approved desktop screens. One is now implemented to the route/responsive/check definition: **1/16 (6.25%)**. Week 3 backend/AI interview runtime remains **100%** at product checkpoint `897aacc`; conservative overall project progress remains **75%** because Week 4 product work has not started.
- Changed implementation files: `backend/accounts/views.py`, `backend/accounts/urls.py`, `backend/accounts/tests.py`, `frontend/templates/accounts/home.html`, and `frontend/static/accounts/css/home.css`. This entry and `docs/AI_HANDOFF.md` are the documentation updates for the completed task.
- Automated browser screenshot comparison was unavailable because the connected computer-use surface could not safely determine the active browser URL. No Figma file content was edited.
- Next: implement the public **`How It Works`** desktop frame (`37:20`) as the second responsive routed Django screen.

## 2026-10-29 — Figma How It Works implementation

- Implemented the public Figma `How It Works` frame (`37:20`) at `accounts:how_it_works` with the approved hero, five-step workflow, three role cards, transparency section, CTA, footer, and responsive desktop/tablet/mobile behavior.
- Reused the completed homepage's navigation, footer, color, button, focus, and mobile-menu styles. Updated the Home page's How It Works links to the real route without redesigning the completed screen.
- Downloaded the single 8px Figma bullet SVG into `frontend/static/accounts/img/teal-bullet.svg`; no temporary Figma URL or screenshot is used at runtime.
- Added two public route/template/link tests. Validation: Django check reported 0 issues; the page stylesheet and bullet asset were discoverable; 41 focused account tests passed; and `git diff --check` passed.
- Known non-failing warnings remain two Daphne Python 3.16 asyncio deprecations and one pytest-cache permission warning. The latest complete-suite validation remains 197 passing tests from the preceding homepage task.
- Figma Django frontend progress is **2/16 (12.5%)**. Week 3 backend/AI interview runtime remains **100%** at `897aacc`; conservative overall project progress remains **75%**.
- Next: implement **`Login`** (`39:29`) using the existing authentication view/form without changing authentication behavior.

## 2026-10-29 — Figma Login implementation

- Implemented the Figma `Login` frame (`39:29`) on the existing public `accounts:login` route as a responsive split brand/sign-in layout using the real `EmailLoginForm`.
- Preserved the existing `EmailLoginView`, django-axes throttling, authentication audit signals, CSRF token, validation errors, candidate/recruiter/administrator shared login, role-dashboard redirect, and candidate registration link.
- Added a small accessible password-visibility script. The displayed `Forgot password?` text is intentionally disabled because no password-reset workflow exists; no fake route or business behavior was introduced.
- Added a focused screen/form test. Validation: Django check reported 0 issues; `login.css` and `login.js` were discoverable; 42 focused account tests passed; and `git diff --check` passed.
- Known non-failing warnings remain two Daphne Python 3.16 asyncio deprecations and one pytest-cache permission warning.
- Figma Django frontend progress is **3/16 (18.75%)**. Week 3 backend/AI interview runtime remains **100%**; conservative overall progress remains **75%**.
- Next: implement **`Candidate Signup`** (`43:32`) around the existing candidate-only form and security behavior.

## 2026-10-30 — Figma Candidate Signup completion and context checkpoint

- Branch: `feat/week-3-ai-interview-runtime`; HEAD: `5b37ca8`; latest validated backend/AI product checkpoint: `897aacc`; worktree contains only the uncommitted Figma frontend, focused tests, and required context documentation.
- Completed Figma `Candidate Signup` (`43:32`) on the existing `accounts:signup` route with the real candidate-only form, accessible error handling, responsive layout, and an accurate verification-before-applying notice. No role, privilege, model, migration, or authentication behavior changed.
- Changed Signup files: `frontend/templates/accounts/signup.html`, `frontend/static/accounts/css/signup.css`, and `backend/accounts/tests.py`. The cumulative frontend worktree also contains the completed Home, How It Works, and Login screen files recorded above.
- Final validation: **201 complete tests passed**; Django check reported 0 issues; migration drift reported no changes; pip check found no broken requirements; Ruff passed across `backend`, `ai_system`, `ml`, and `tests`; and `git diff --check` passed.
- Errors/blockers: none. Known warnings: two Daphne Windows asyncio deprecations for Python 3.16 and one pytest-cache permission warning.
- Figma Django frontend progress is **4/16 (25%)**. Week 3 backend/AI interview runtime remains **100%**; conservative overall project progress remains **75%**.
- Current task: begin Candidate Dashboard only after this checkpoint. Exact next screen: **`Candidate Dashboard` (`15:3`)** using the existing candidate-only route, real available data, and safe empty states.

## 2026-10-30 — Figma Candidate Dashboard implementation

- Implemented Figma `Candidate Dashboard` (`15:3`) on the existing candidate-only `accounts:candidate_dashboard` route without changing models, migrations, authorization rules, or interview/application business logic.
- Added the approved responsive navy sidebar, welcome header, data-backed profile completion, application/interview/résumé summary cards, upcoming interview, recent applications, and helpful next-step cards. Candidate/profile/application/interview data is candidate-scoped; unavailable records use explicit safe empty states rather than sample business data.
- Preserved role protection, POST/CSRF email-verification actions, POST-only logout, and existing candidate routes. Added responsive desktop/tablet/mobile behavior, keyboard focus styling, semantic landmarks/headings, and accessible status text.
- Changed screen files: `backend/accounts/views.py`, `backend/accounts/tests.py`, `frontend/templates/accounts/candidate_dashboard.html`, and `frontend/static/accounts/css/candidate-dashboard.css`.
- Validation: **46 focused account tests passed**; Django system check reported 0 issues; Ruff passed for `backend/accounts`; Django staticfiles found `accounts/css/candidate-dashboard.css`; and `git diff --check` passed. The latest complete-suite result remains **201 passing tests** from the immediately preceding Candidate Signup checkpoint.
- Known non-failing warnings remain two Daphne Windows asyncio deprecations for Python 3.16 and one pytest-cache permission warning. No blocker remains; no commit was created.
- Figma Django frontend progress is **5/16 (31.25%)**. Week 3 backend/AI interview runtime remains **100%**; conservative overall project progress remains **75%**.
- Next: implement **`My Profile & AI Consent` (`16:10`)** around the existing candidate-only profile and deterministic consent workflows.

## 2026-10-30 — Figma My Profile & AI Consent implementation

- Implemented Figma `My Profile & AI Consent` (`16:10`) on the existing candidate-only `candidates:profile_edit` route with the shared candidate sidebar, responsive completion banner, personal-information fields, professional summary, persisted skills, consent status/details, and save/cancel actions.
- Preserved the existing seven-field `CandidateProfileForm` allowlist, candidate-only role guard, candidate ownership lookup, transactional profile audit event, POST/CSRF consent route, current-policy resolver, immutable consent history, deterministic consent audit behavior, and fixed candidate data boundaries. Account name/email are displayed read-only rather than made mass assignable.
- Consent controls use the real grant/revoke services and a fixed `return_to=profile` allowlist value. Current status is resolved from append-only history rather than trusting the Boolean cache alone. The Figma ON-state toggle asset is stored locally; no temporary Figma URL is used at runtime.
- Skills are rendered from existing `CandidateSkill` records. Skill mutation is deliberately not invented because the project has no supported candidate skill-editing route; an explicit empty state is shown instead.
- Changed screen files: `backend/candidates/views.py`, `backend/candidates/test_candidate_workflow.py`, `frontend/templates/candidates/profile_form.html`, `frontend/static/candidates/css/candidate-profile.css`, and `frontend/static/accounts/img/consent-toggle-on.svg`.
- Validation: **20 candidate tests passed** initially; the final combined candidate/account run passed **66 tests**; Django system check reported 0 issues; Ruff passed for `backend/candidates`; static discovery found the profile stylesheet and consent-toggle SVG; and `git diff --check` passed. The latest complete-suite result remains **201 passing tests** from the Candidate Signup checkpoint and was not re-claimed as a post-profile full run.
- Known non-failing warnings remain two Daphne Windows asyncio deprecations for Python 3.16 and one pytest-cache permission warning. No blocker remains; no commit was created.
- Figma Django frontend progress is **6/16 (37.5%)**. Candidate Portal progress is **3/6 (50%)** per the tracked screen grouping. Week 3 backend/AI interview runtime remains **100%**; conservative overall project progress remains **75%**.
- Next: implement **`My Résumé` (`20:13`)** using the existing protected upload, processing, replacement, list, and download workflows.

## 2026-10-30 — Figma My Résumé implementation

- Implemented Figma `My Résumé` (`20:13`) on the existing candidate-only `candidates:resume_list` route with the shared candidate sidebar, active résumé card, secure upload/replacement area, processing explanation, authorized previous-upload history, and privacy note.
- Reused the existing `ResumeUploadForm`, candidate-only role guard, owner-scoped queries, protected download view, PDF/DOCX and 5 MB validation, randomized private storage, SHA-256 calculation, bounded local parsing, safe failure statuses, and successful-only active-résumé replacement. No model, migration, storage, or processing rule changed.
- The list and upload routes now render one unified workspace. Only safe authorized metadata is displayed: original filename, file size, upload date, and processing/active state. Storage names, paths, checksums, extracted text, and other candidates' records are not exposed.
- Added the Figma upload icon as a local 24×24 SVG and used a native accessible file input across the drag-and-drop visual target. No screenshot, mockup, or temporary Figma URL is used at runtime.
- Changed screen files: `backend/candidates/views.py`, `backend/candidates/test_candidate_workflow.py`, `frontend/templates/candidates/resume_list.html`, `frontend/static/candidates/css/candidate-resume.css`, and `frontend/static/accounts/img/resume-upload.svg`.
- Validation: **25 focused candidate tests passed**; Django system check reported 0 issues; Ruff passed for `backend/candidates`; static discovery found the résumé stylesheet and upload SVG; and `git diff --check` passed. The latest complete-suite result remains **201 passing tests** and was not re-claimed as a post-résumé full run.
- Known non-failing warnings remain two Daphne Windows asyncio deprecations for Python 3.16 and one pytest-cache permission warning. Structural validation is not malware scanning. No blocker remains; no commit was created.
- Figma Django frontend progress is **7/16 (43.75%)**. Candidate Portal progress is **4/6 (66.67%)**. Week 3 backend/AI interview runtime remains **100%**; conservative overall project progress remains **75%**.
- Next: implement **`Browse Jobs` (`24:17`)** using the existing candidate-only open-job listing and real company/job data.

## 2026-10-30 — Figma Browse Jobs implementation

- Implemented Figma `Browse Jobs` (`24:17`) on the existing authenticated candidate view of `recruitment:job_list` with the shared responsive sidebar/header, real eligible-job cards, safe result count and empty state, authorized detail links, and profile helper.
- Preserved the existing visibility boundary: candidates receive only open, unexpired jobs from active companies. Draft, expired, inactive-company, and unauthorized records remain excluded. Recruiter job-list behavior is preserved through a compatibility template.
- Search, location/job-type/experience filters, sorting, and pagination are visibly disabled and explicitly described as unavailable because no existing backend support exists; no fake query behavior or business rule was added.
- Changed screen files: `backend/recruitment/views.py`, `backend/recruitment/test_job_workflow.py`, `frontend/templates/recruitment/job_list.html`, `frontend/templates/recruitment/recruiter_job_list.html`, and `frontend/static/recruitment/css/job-list.css`.
- Validation: **20 focused recruitment tests passed**; Django system check reported 0 issues; Ruff passed for `backend/recruitment`; Django staticfiles found `recruitment/css/job-list.css`; and `git diff --check` passed. The first focused run had one assertion mismatch caused by HTML around the result count; the assertion was corrected and both the targeted rerun and full recruitment suite passed.
- Known non-failing warnings remain two Daphne Windows asyncio deprecations for Python 3.16 and one pytest-cache permission warning. The latest complete-suite result remains **201 passing tests** and was not rerun for this screen.
- Figma Django frontend progress is **8/16 (50%)**. Candidate Portal progress is **5/6 (83.33%)**. Week 3 backend/AI interview runtime remains **100%**; conservative overall project progress remains **75%**. No commit was created.
- Next: implement **`Job Details & Apply` (`26:24`)** using the existing secure detail/application routes and application eligibility rules.

## 2026-10-30 — Automatic context checkpoint before Job Details

- Branch: `feat/week-3-ai-interview-runtime`; HEAD: `5b37ca8`; latest validated backend/AI product checkpoint: `897aacc`; worktree: dirty only with the eight documented Figma screens, focused tests, and context updates.
- Completed work: Home, How It Works, Login, Candidate Signup, Candidate Dashboard, My Profile & AI Consent, My Résumé, and Browse Jobs are implemented, focused-validated, and documented. Current changed files are the previously recorded account/candidate/recruitment views and tests, their templates/static assets, and these two context documents.
- Latest exact validation: **201 complete tests passed** at the Candidate Signup checkpoint; the latest **20 focused recruitment tests passed** after Browse Jobs; Django check reported 0 issues; Ruff, static discovery, and `git diff --check` passed.
- Errors/blockers: none. Known warnings: two Daphne Windows asyncio deprecations for Python 3.16 and one pytest-cache permission warning.
- Current task: implement only the visual job-detail portion of `Job Details & Apply` (`26:24`); the application-form visual redesign remains the exact next small task afterward.
- Week 3 remains **100%**; conservative overall project progress remains **75%**. No commit was created.

## 2026-10-30 — Figma Job Details visual section

- Implemented only the visual job-detail portion of Figma `Job Details & Apply` (`26:24`) on the existing candidate-authorized `recruitment:job_detail` route. The separate secure application form was not redesigned, so the screen is recorded as **partial**.
- Added the shared candidate sidebar with Browse Jobs active, breadcrumb, real job/company hero details and badges, About the role, responsibilities, minimum/preferred requirements, skills, company summary, back link, and a clear Apply now link to the existing application route. Save Job is visibly disabled because no saved-jobs backend exists.
- Preserved candidate visibility rules for open, unexpired jobs from active companies; draft, expired, and inactive-company detail requests remain hidden. No model, migration, route, application rule, service, API, JavaScript, or fake data was added. Recruiter detail rendering remains available through a compatibility template.
- Changed screen files: `backend/recruitment/views.py`, `backend/recruitment/test_job_workflow.py`, `frontend/templates/recruitment/job_detail.html`, `frontend/templates/recruitment/recruiter_job_detail.html`, and `frontend/static/recruitment/css/job-detail.css`.
- Validation: **1 focused Job Details route/access test passed**; Django system check reported 0 issues; Ruff passed for `backend/recruitment`; Django staticfiles found `recruitment/css/job-detail.css`; and `git diff --check` passed. The latest complete-suite result remains **201 passing tests** and was not rerun.
- Known non-failing warnings remain two Daphne Windows asyncio deprecations for Python 3.16 and one pytest-cache permission warning. No blocker remains; no commit was created.
- Fully completed frontend progress remains **8/16 (50%)**. `Job Details & Apply` is partial. Week 3 backend/AI interview runtime remains **100%**; conservative overall project progress remains **75%**.
- Next small task: style the existing secure application form and complete `Job Details & Apply` (`26:24`) without changing application business rules.

## 2026-10-30 — Figma Job Details & Apply completion

- Completed the application-form portion of Figma `Job Details & Apply` (`26:24`) on the existing candidate-only `recruitment:application_create` route. The previously completed job-detail section was preserved, so the full screen is now complete.
- Added a responsive application panel with the candidate sidebar, breadcrumb, real job summary, candidate-owned active résumé information and selector, existing cover-note field, existing optional AI-interview consent control, visible field/service errors, secure submit and back actions, and privacy/human-decision guidance.
- Preserved CSRF, candidate-only authorization, verified-email enforcement, candidate-owned active processed résumé checks, duplicate prevention, allowlisted fields, deterministic application auditing, and append-only consent history. No model, migration, route, service, or application business rule changed.
- Changed task files: `backend/recruitment/forms.py`, `backend/recruitment/views.py`, `backend/recruitment/test_application_workflow.py`, `frontend/templates/recruitment/application_form.html`, and `frontend/static/recruitment/css/application-form.css`.
- Validation: **10 focused application-workflow tests passed**; Django system check reported 0 issues; Ruff passed for the changed recruitment Python files; static discovery found `recruitment/css/application-form.css`; and `git diff --check` passed. The latest complete-suite result remains **201 passing tests** and was not rerun for this focused screen task.
- Known non-failing warnings remain two Daphne Windows asyncio deprecations for Python 3.16 and one pytest-cache permission warning. No blocker remains; no commit was created.
- Figma Django frontend progress is **9/16 (56.25%)**. The tracked Candidate Portal grouping is **6/6 (100%)**. Week 3 backend/AI interview runtime remains **100%**; conservative overall project progress remains **75%**.
- Next: implement **`My Applications & AI Interview` (`27:27`)** using the existing candidate-scoped application, scheduling, consent, and call-session behavior.

## 2026-10-30 — Figma My Applications & AI Interview implementation

- Implemented Figma `My Applications & AI Interview` (`27:27`) on the existing `recruitment:application_list` route with the shared responsive candidate sidebar, real summary counts, candidate-owned application rows, secure detail links, one featured confirmed future interview, readiness indicators, preparation guidance, and safe empty states.
- The interview card is built only from the signed-in candidate's current confirmed schedule, current-policy general/application consent, verified-email state, active processed résumé, and existing call-session state. It links only to the existing authorized candidate session and reschedule routes. It does not render answers, transcripts, private résumé data, invitation tokens, storage paths, or other candidates' records.
- Preserved recruiter functionality through a company-scoped compatibility template; recruiters do not receive the candidate-facing dashboard, and administrators remain denied by the existing role guard. No model, migration, scheduling rule, call-session rule, AI behavior, route, or service changed.
- Changed screen files: `backend/recruitment/views.py`, `backend/recruitment/test_application_workflow.py`, `frontend/templates/recruitment/application_list.html`, `frontend/templates/recruitment/recruiter_application_list.html`, and `frontend/static/recruitment/css/application-list.css`.
- Validation: **12 focused application-workflow tests passed**, followed by **12 focused interview-scheduling/candidate-call-session tests**; Django system check reported 0 issues; Ruff passed for the changed recruitment Python files; static discovery found `recruitment/css/application-list.css`; and `git diff --check` passed. The latest complete-suite result remains **201 passing tests** and was not rerun.
- Known non-failing warnings remain two Daphne Windows asyncio deprecations for Python 3.16 and one pytest-cache permission warning. No blocker remains; no commit was created.
- Figma Django frontend progress is **10/16 (62.5%)**. The tracked Candidate Portal grouping remains **6/6 (100%)**. Week 3 backend/AI interview runtime remains **100%**; conservative overall project progress remains **75%**.
- Next: implement **`Recruiter Dashboard` (`28:3`)** using existing recruiter-only, company-scoped data and permissions.

## 2026-10-30 — Figma Recruiter Dashboard implementation

- Implemented Figma `Recruiter Dashboard` (`28:3`) on the existing `accounts:recruiter_dashboard` route with the responsive recruiter sidebar/header, four real company metrics, recent applications, upcoming interviews, active job cards, safe empty states, and human-decision responsibility note.
- Strengthened the page boundary to require the persisted recruiter user to be active and in the recruiter role, the recruiter profile to be verified, the company to be active, and at least one recruiter capability. Jobs, applications, candidates, and schedules are queried only through the recruiter's company; actions are capability-gated and unsupported company-profile functionality is visibly unavailable.
- Candidate display uses a persisted name or the generic label `Candidate`, never an email fallback. No résumé content, answers, transcripts, invitation tokens, storage paths, audit metadata, internal identifiers, or other-company records are rendered.
- Changed task files: `backend/accounts/views.py`, `backend/accounts/tests.py`, `frontend/templates/accounts/recruiter_dashboard.html`, and `frontend/static/accounts/css/recruiter-dashboard.css`.
- Validation: **29 account tests passed**, followed by **31 focused recruitment/interview tests**; Django system check reported 0 issues; Ruff passed for the changed account Python files; static discovery found `accounts/css/recruiter-dashboard.css`; and `git diff --check` passed. The latest complete-suite result remains **201 passing tests** and was not rerun for this focused screen.
- Known non-failing warnings remain two Daphne Windows asyncio deprecations for Python 3.16 and one pytest-cache permission warning. No blocker remains; no commit was created.
- Figma Django frontend progress is **11/16 (68.75%)**. Candidate Portal remains **6/6 (100%)**; Recruiter Portal is **1/4 (25%)**; Admin Portal is **0/2 (0%)**. Week 3 backend/AI interview runtime remains **100%**; conservative overall project progress remains **75%**.
- Next: implement **`Manage Jobs` (`28:136`)** using the existing company-scoped job management routes and deterministic transitions.

## 2026-10-30 — Automatic context checkpoint before Manage Jobs

- Branch: `feat/week-3-ai-interview-runtime`; HEAD: `5b37ca8`; latest validated backend/AI product checkpoint: `897aacc`; worktree: dirty only with the eleven documented Figma screens, their focused tests, static assets, and context updates.
- Completed work: Home, How It Works, Login, Candidate Signup, all six tracked candidate-portal screens, and Recruiter Dashboard are implemented, focused-validated, and documented. Current changed files are the previously recorded account/candidate/recruitment views, forms, tests, templates, static assets, and these context documents.
- Latest exact validation: **201 complete tests passed** at the latest full-suite checkpoint; Recruiter Dashboard validation passed **29 account tests** and **31 focused recruitment/interview tests**; Django check reported 0 issues; Ruff, static discovery, and `git diff --check` passed.
- Errors/blockers: none. Known warnings: two Daphne Windows asyncio deprecations for Python 3.16 and one pytest-cache permission warning.
- Current task: implement only **`Manage Jobs` (`28:136`)** using existing verified-recruiter, capability, company-scope, and deterministic transition boundaries.
- Week 3 remains **100%**; Figma Django frontend progress is **11/16 (68.75%)**; conservative overall project progress remains **75%**. No commit was created.

## 2026-10-30 — Figma Manage Jobs implementation

- Implemented Figma `Manage Jobs` (`28:136`) on the recruiter branch of the existing `recruitment:job_list` route with the responsive recruiter shell, Manage Jobs active state, real Published/Drafts/Closed summaries, company-scoped job table, applicant counts, safe empty state, job-writing helper, and publishing note.
- Reused the existing persisted recruiter authorization in `recruiter_jobs()`: the recruiter user must be active, the profile verified, the company active, and `can_manage_jobs` enabled. Candidates continue to receive the separate Browse Jobs template from the shared route; administrators and ineligible recruiters remain denied.
- Reused the existing create/edit routes and deterministic POST/CSRF job-state route. Publish, reopen, and close controls are rendered only for states where the existing transition table permits them. No model, migration, workflow rule, API, or fake record was added.
- Search/filter/sort controls are visibly disabled with an honest unavailable note. Department cells say `Not specified` because the current `JobPosting` schema has no department field; no unsupported filter or department behavior is simulated.
- Changed task files: `backend/recruitment/views.py`, `backend/recruitment/test_job_workflow.py`, `frontend/templates/recruitment/recruiter_job_list.html`, and `frontend/static/recruitment/css/manage-jobs.css`.
- Validation: **13 focused job-workflow tests passed**, followed by **3 deterministic recruitment-transition tests**; Django system check reported 0 issues; Ruff passed for the changed recruitment Python files; static discovery found `recruitment/css/manage-jobs.css`; and `git diff --check` passed. The latest complete-suite result remains **201 passing tests** and was not rerun.
- Known non-failing warnings remain two Daphne Windows asyncio deprecations for Python 3.16 and one pytest-cache permission warning. No blocker remains; no commit was created.
- Figma Django frontend progress is **12/16 (75%)**. Candidate Portal remains **6/6 (100%)**; Recruiter Portal is **2/4 (50%)**; Admin Portal is **0/2 (0%)**. Week 3 backend/AI interview runtime remains **100%**; conservative overall project progress remains **75%**.
- Next: implement **`Applicants & Application Details` (`29:5`)** using existing company-scoped application review routes and permissions.

## 2026-10-30 — Figma Applicants list stage

- Implemented only the left applicant-list workspace from Figma `Applicants & Application Details` (`29:5`) on the recruiter branch of the existing `recruitment:application_list` route. The full screen remains **partial** because the right-side authorized application-detail panel has not been redesigned.
- Added the responsive recruiter shell with Applications active, header controls, visibly disabled search/job/status filters, applicant count, real company-scoped application cards, safe candidate initials/names, job title, applied date, persisted status, existing Review links, privacy note, and honest empty state.
- Preserved `recruiter_applications()` authorization: the persisted recruiter must be active, verified, and have `can_review_candidates`; returned applications remain restricted to the recruiter's company. Candidate names use a generic fallback rather than email, and the list renders no résumé filename/content, transcript/answer, invitation token, storage path, audit metadata, or other-company record.
- No selected row was invented because the existing list route has no selected-application context. The existing detail route and its résumé/interview/history behavior were not redesigned or changed.
- Changed task files: `backend/recruitment/views.py`, `backend/recruitment/test_application_workflow.py`, `frontend/templates/recruitment/recruiter_application_list.html`, and `frontend/static/recruitment/css/recruiter-applications.css`.
- Validation: **14 focused application-workflow tests passed**; Django system check reported 0 issues; Ruff passed for the changed recruitment Python files; static discovery found `recruitment/css/recruiter-applications.css`; and `git diff --check` passed. The latest complete-suite result remains **201 passing tests** and was not rerun.
- Known non-failing warnings remain two Daphne Windows asyncio deprecations for Python 3.16 and one pytest-cache permission warning. No blocker remains; no commit was created.
- Fully completed Figma Django frontend progress remains **12/16 (75%)**. `Applicants & Application Details` is partial at the applicant-list stage; Recruiter Portal remains **2/4 complete plus 1 partial**. Week 3 backend/AI interview runtime remains **100%**; conservative overall project progress remains **75%**.
- Next small task: implement the **right-side authorized application-detail panel** for `Applicants & Application Details` (`29:5`).

## 2026-10-30 — Figma Applicants & Application Details completion

- Confirmed the documented Stage A applicant-list workspace was already complete, then implemented only the remaining right-side authorized detail panel for Figma `Applicants & Application Details` (`29:5`) on the existing recruiter application-detail route.
- Reused the company-scoped `recruiter_applications()` authorization and existing list shell. The selected detail shows safe candidate identity, location, experience, persisted skills, verified-email state, current-policy processing/interview consent, résumé filename and processing status, application status, current interview schedule, permitted scheduling/session actions, and audit-derived application history. The selected row appears only when the existing detail route supplies selected-application context; the two-column workspace stacks on narrower screens.
- Kept recruiter résumé viewing visibly unavailable because no recruiter-authorized download route exists. No résumé text, storage path, checksum, interview answer/transcript, invitation credential, private audit metadata, other-company data, model, migration, route, API, or business rule was added or exposed.
- Changed task files: `backend/recruitment/views.py`, `backend/recruitment/test_application_workflow.py`, `frontend/templates/recruitment/recruiter_application_list.html`, `frontend/static/recruitment/css/recruiter-applications.css`, `docs/AI_HANDOFF.md`, and `docs/WORK_LOG.md`.
- Validation: **25 focused application and interview-scheduling tests passed**; Django system check reported 0 issues; Ruff passed for the changed recruitment Python files; Django staticfiles found `recruitment/css/recruiter-applications.css`; and `git diff --check` passed. The complete suite was not run for this focused task; the latest verified full-suite result remains **201 passing tests**.
- Known non-failing warnings: two Daphne Windows asyncio deprecations and one pytest-cache permission warning. No blocker remains; no commit was created and `.env` was untouched.
- Figma Django frontend progress is **13/16 (81.25%)**. Candidate Portal remains **6/6 (100%)**; Recruiter Portal is **3/4 (75%)**; Admin Portal is **0/2 (0%)**. Week 3 backend/AI interview runtime remains **100%**; conservative overall project progress remains **75%**.
- Next: implement **Interview Management** (`30:8`) using existing recruiter-scoped scheduling and call-session routes.

## 2026-10-30 — Figma Interview Management implementation

- Implemented Figma `Interview Management` (`30:8`) on the existing `calling:recruiter_session_list` route with the shared responsive recruiter shell, Interviews active state, real schedule summaries, honest disabled status filters, responsive upcoming-interview rows, selected schedule details, invitation/confirmation state, current-policy readiness indicators, supported schedule/session actions, company-scoped reschedule review, safe empty states, and the human-decision privacy note.
- The page now uses current company schedules rather than only schedules that already have call sessions. Access is limited to persisted active recruiters with a verified profile, active company, and `can_review_candidates`; candidates and administrators are denied this recruiter screen. Existing administrator call-session review services and detail authorization were not changed.
- Reused the existing application-selection route for the Schedule Interview entry point, call-session detail route when a session exists, invitation retry and schedule cancellation POST/CSRF actions, and reschedule approval/decline POST/CSRF actions. Recruiter-initiated rescheduling and tabs remain visibly unavailable because the backend has no corresponding recruiter route or filter behavior.
- No invitation token, private delivery error, résumé data, answer/transcript content, audit metadata, internal display identifier, other-company record, model, migration, API, business rule, or fake interview was added or exposed.
- Changed task files: `backend/calling/views.py`, `backend/calling/test_call_session_services.py`, `frontend/templates/calling/recruiter_session_list.html`, `frontend/static/calling/css/recruiter-interviews.css`, `docs/AI_HANDOFF.md`, and `docs/WORK_LOG.md`.
- Validation: the first four-test run reported three failures from a missing `django.utils.timezone` import in the new view; the import was added and the same run passed **4 tests**. Final focused validation passed **59 calling, interview-scheduling, and application tests**; Django system check reported 0 issues; Ruff passed for the changed calling Python files; Django staticfiles found `calling/css/recruiter-interviews.css`; and `git diff --check` passed. The complete suite was not run; the latest verified full-suite result remains **201 passing tests**.
- Known non-failing warnings: two Daphne Windows asyncio deprecations and one pytest-cache permission warning. No blocker remains; no commit was created and `.env` was untouched.
- Figma Django frontend progress is **14/16 (87.5%)**. Candidate Portal remains **6/6 (100%)**; Recruiter Portal is **4/4 (100%)**; Admin Portal is **0/2 (0%)**. Week 3 backend/AI interview runtime remains **100%**; conservative overall project progress remains **75%**.
- Next: implement **Admin Dashboard** (`32:3`) using the existing administrator-only route and trusted provisioning boundaries.

## 2026-10-30 — Automatic context checkpoint before Admin Dashboard

- Branch: `feat/week-3-ai-interview-runtime`; HEAD: `5b37ca8`; worktree: dirty only with the fourteen documented Figma screen implementations, their focused tests/static assets, and context updates.
- Completed work: Home, How It Works, Login, Candidate Signup, all six candidate-portal screens, and all four recruiter-portal screens are implemented, focused-validated, and documented. The current task is **Admin Dashboard** (`32:3`); no Admin Dashboard changes have started at this checkpoint.
- Current changed files are the previously documented account, candidate, recruitment, calling, and interview-facing views/forms/tests/templates/static assets plus `docs/AI_HANDOFF.md` and `docs/WORK_LOG.md`; no migration, model, deployment, or environment file is part of the worktree.
- Exact latest validation: **59 calling, interview-scheduling, and application tests passed** for Interview Management; Django system check reported 0 issues; Ruff, static discovery, and `git diff --check` passed. The latest complete-suite checkpoint remains **201 passing tests**.
- Errors/blockers: the prior missing `django.utils.timezone` import was corrected and its failing tests were rerun successfully; no blocker remains. Known warnings are two Daphne Windows asyncio deprecations and one pytest-cache permission warning.
- Week 3 backend/AI interview runtime remains **100%**; Figma Django frontend progress is **14/16 (87.5%)**; conservative overall project progress remains **75%**.
- Exact next task: implement and focused-validate **Admin Dashboard** (`32:3`) without changing provisioning rules, models, migrations, or unrelated screens.

## 2026-10-30 — Figma Admin Dashboard implementation

- Implemented Figma `Admin Dashboard` (`32:3`) on the existing administrator-only `accounts:admin_dashboard` route with the responsive navy administrator shell, Dashboard active state, real platform metrics, recent company activity, recruiter verification state, privacy-safe platform activity, honest empty states, existing trusted provisioning links, and the administrative accountability/human-control note.
- Preserved the administrator role boundary and existing Django admin/provisioning services. Staff administrators receive existing Django admin Add Company, Add Recruiter, company-management, and recruiter-review links; role administrators without staff access receive honest disabled controls. No provisioning, approval, deletion, notification, audit-browser, model, migration, API, or business workflow was invented.
- Platform activity is restricted to an explicit event-type allowlist and fixed display labels. The page never renders audit metadata, descriptions, resource identifiers, actor email snapshots, or stored action prose; recruiter display falls back to a generic label rather than email.
- Changed task files: `backend/accounts/views.py`, `backend/accounts/tests.py`, `frontend/templates/accounts/admin_dashboard.html`, `frontend/static/accounts/css/admin-dashboard.css`, `docs/AI_HANDOFF.md`, and `docs/WORK_LOG.md`.
- Validation: **57 account tests passed**, followed by **141 focused account, recruitment-administration, and audit tests**; Django system check reported 0 issues; Ruff passed for `backend/accounts`; Django staticfiles found `accounts/css/admin-dashboard.css`; and `git diff --check` passed. The first sandboxed command could not launch the virtual environment's base Python because of managed filesystem permission; the identical validation was rerun successfully with approved execution permission. The complete suite was not run; the latest verified full-suite result remains **201 passing tests**.
- Known non-failing warnings: two Daphne Windows asyncio deprecations and one pytest-cache permission warning. No product blocker remains; no commit was created and `.env` was untouched.
- Figma Django frontend progress is **15/16 (93.75%)**. Candidate Portal remains **6/6 (100%)**; Recruiter Portal is **4/4 (100%)**; Admin Portal is **1/2 (50%)**. Week 3 backend/AI interview runtime remains **100%**; conservative overall project progress remains **75%**.
- Next: implement **Companies & Recruiters Management** (`33:4`) using existing trusted provisioning and Django admin boundaries.

## 2026-10-30 — Figma Companies & Recruiters Management completion

- Implemented the final approved Figma desktop screen, `Companies & Recruiters Management` (`33:4`), through the existing administrator-only `accounts:admin_dashboard` route using the explicit `?section=management` presentation state. The default Admin Dashboard remains intact and now links to the management overview.
- Added the responsive administrator shell with Companies active, safe company/recruiter sections, real recruiter and open-job counts, company/access status, creation/update context, initials and name fallbacks, existing Django admin Add/Manage/Review links for staff administrators, honest disabled search/filter controls, responsive overflow/card behavior, empty states, and the access/accountability note.
- Preserved role checks and trusted provisioning boundaries. Non-administrators remain denied; role administrators without Django staff access receive read-only data and disabled mutation controls. No model, migration, API, verification rule, deletion workflow, fake record, AI behavior, or management business rule was added. No email address, phone number, candidate private data, résumé, answer/transcript, token, storage path, secret, or raw audit metadata is displayed.
- Changed task files: `backend/accounts/views.py`, `backend/accounts/tests.py`, `frontend/templates/accounts/admin_dashboard.html`, `frontend/templates/accounts/admin_management.html`, `frontend/static/accounts/css/admin-management.css`, `docs/AI_HANDOFF.md`, and `docs/WORK_LOG.md`. The ignored local prompt counter was incremented to `1` according to `AGENTS.md`.
- Validation: **57 focused account tests passed**; **141 focused account, recruitment-administration, and audit tests passed**; and the complete suite passed **243 tests** with `OPENBLAS_NUM_THREADS=1`. Django system check reported 0 issues; migration drift reported no changes; pip check found no broken requirements; Ruff passed across `backend`, `ai_system`, `ml`, and `tests`; Django staticfiles found `accounts/css/admin-management.css`; and `git diff --check` passed.
- Known non-failing warnings: two Daphne Windows asyncio deprecations and one pytest-cache permission warning. No blocker remains; no commit was created and `.env` was untouched.
- All **16/16 Figma desktop screens are implemented, focused/full-suite validated, and documented**. Candidate Portal is **6/6**, Recruiter Portal is **4/4**, and Admin Portal is **2/2**. Week 3 backend/AI interview runtime remains **100%**. Conservative overall project progress remains **75%** because Week 4 manual QA, evaluation, production readiness, deployment, and final documentation remain incomplete.
- Exact next task: perform a final manual UI/QA review, inspect the cumulative frontend diff, and create one reviewed frontend commit only after approval.

## 2026-10-30 — Reviewed Figma frontend checkpoint

- Branch: `feat/week-3-ai-interview-runtime`; reviewed frontend product commit: `00c601a` (`feat: implement responsive Figma frontend`). The commit contains only the documented frontend-facing account/candidate/recruitment/calling views and forms, their focused tests, all responsive templates, local CSS/JavaScript/SVG assets, and no context documents or private/runtime files.
- Pre-commit review inspected Git status, diff statistics, whitespace, changed names, substantive backend-facing diffs, test additions, template mutation/CSRF patterns, and all untracked static assets. No unrelated user changes, remote Figma URLs, credentials, private candidate data, generated runtime output, or temporary assets were found. The three SVG files are intentional small local interface assets.
- Final pre-commit validation passed **243 complete tests** with `OPENBLAS_NUM_THREADS=1`; Django system check reported 0 issues; migration drift reported no changes; pip check found no broken requirements; Ruff passed across `backend`, `ai_system`, `ml`, and `tests`; and `git diff --check` plus `git diff --cached --check` passed.
- Known non-failing warnings remain two Daphne Windows asyncio deprecations and one pytest-cache permission warning. Initial staging was blocked by managed `.git/index.lock` permissions; the identical explicit staging operation succeeded with approved Git metadata write permission and did not alter the intended file set.
- No push, merge, rebase, amend, deployment, environment access, or branch change occurred. The ignored local context counter remains outside Git.
- All **16/16 Figma desktop screens remain implemented and validated**, but the project remains **75% overall** because Week 4 evaluation, production readiness, deployment, final documentation, and hands-on cross-browser/UI QA remain incomplete.
- Exact next task: conduct hands-on desktop/tablet/mobile and keyboard-accessibility UI QA against the committed screens, then proceed only with an approved Week 4 scope.

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

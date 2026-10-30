# AI Handoff — MultiAgent Recruitment Caller

This is the authoritative handoff document for another AI assistant. Read it after `AGENTS.md`, then verify its snapshot against Git and the source before changing code.

Last updated: 2026-10-30 (Asia/Karachi)

## Project identity

- **Project:** MultiAgent Recruitment Caller
- **Purpose:** Build a browser-based recruitment platform in which specialized AI agents can conduct, assist with, evaluate, monitor, and audit candidate screening interviews.
- **Final intended product:** A secure recruitment workflow covering candidate onboarding, job applications, scheduling, browser-based voice screening, local speech processing, coordinated specialist agents, evidence-based evaluation, escalation, auditability, and mandatory human review for consequential employment decisions.
- **Implementation constraint:** Python-first.
- **Technology constraint:** Prefer free and open-source components; do not introduce paid or closed dependencies without an explicit decision.
- **Delivery target:** Four development weeks, tracked in `docs/ROADMAP.md`.

## Current Git and progress snapshot

- **Current branch:** `feat/week-3-ai-interview-runtime`
- **Current documentation state:** synchronized after the reviewed Figma frontend checkpoint; verify the latest Git HEAD for the context-only documentation commit.
- **Current product commit:** `00c601a` — reviewed responsive Figma frontend implementation.
- **Latest validated product checkpoint:** `00c601a` — all 16 responsive Figma screens plus the previously committed Week 3 runtime.
- **Week 1:** 100% complete.
- **Current week:** Week 3, 100% complete. Milestones 3.1 through 3.6 are committed and validated.
- **Overall project:** 75% complete.
- **Automated tests:** The latest complete suite has **243 passing tests**. The final administrator-screen validation also passed 57 focused account tests and 141 focused account, recruitment-administration, and audit tests.
- **Figma implementation:** All 16 approved desktop frames are implemented as responsive, routed Django screens: Home (`7:2`), How It Works (`37:20`), Login (`39:29`), Candidate Signup (`43:32`), Candidate Dashboard (`15:3`), My Profile & AI Consent (`16:10`), My Résumé (`20:13`), Browse Jobs (`24:17`), Job Details & Apply (`26:24`), My Applications & AI Interview (`27:27`), Recruiter Dashboard (`28:3`), Manage Jobs (`28:136`), Applicants & Application Details (`29:5`), Interview Management (`30:8`), Admin Dashboard (`32:3`), and Companies & Recruiters Management (`33:4`): **16/16 (100%)**. This does not mean Week 4 evaluation, production readiness, deployment, or final manual UI QA is complete.

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
ai_system/     Deterministic coordinator/voice contracts; planned broader agents
ml/            Optional local voice adapters; planned inference/evaluation
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
- `agents`: Versioned agent definitions, runs, actions, handoffs, approval fields, escalation records, and deterministic privacy-safe escalation services.
- `auditlog`: Immutable keyed audit events, security incidents, data-retention records, and append-only policy-versioned consent history. PostgreSQL triggers protect audit events and consent evidence from database-level update and deletion.

Accounts, candidates, recruitment, interview scheduling, and the simulated interview provide tested server-rendered workflows. Calling has a deterministic domain, HTTP fallback, authorized status WebSocket, expiry processing, and human-escalation boundary. Operational speech execution, broader specialist agents, and evaluation remain later work.

## Planned AI agents

- **Calling Orchestrator:** Coordinate the call lifecycle, turn-taking, timeouts, and handoffs.
- **Candidate Profile Agent:** Retrieve consented candidate and application context without exposing unnecessary private data.
- **Interview Agent:** Ask approved questions and manage conversational interview flow.
- **Evaluation Agent:** Produce rubric-based scores, evidence, confidence, and an advisory recommendation for human review.
- **FAQ Agent:** Answer approved job and process questions from controlled sources.
- **Scheduling Agent:** Assist with interview availability, confirmation, and rescheduling.
- **Safety Agent:** Semantically detect prompt injection, bias, coercion, privacy concerns, and unsafe conversational content. It supplements and cannot override deterministic policy enforcement.
- **Escalation Agent:** Route candidate requests, uncertainty, safety events, and technical failures to authorized humans.

These specialist agents have database definitions but no unrestricted or generative operational runtime. Auditing is not a generative-agent responsibility: ordinary Python domain services decide when an event is mandatory, validate a strict event specification, sanitize its metadata, and persist the immutable event. Future agent runtimes may only submit structured events through narrow service adapters.

Week 3 includes a model-free `DeterministicInterviewCoordinator`, not a generative agent. It exposes only status, start, pause, cancel, submit-answer, and request-human commands through a candidate-scoped Django adapter. It selects approved job questions one at a time and returns fixed structured directives. The broader specialist-agent runtime remains planned.

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
- Candidate AI-processing and interview consent Boolean fields are mutable caches. The committed consent implementation derives effective consent from append-only, policy-versioned history and requires workflow enforcement before processing.
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
- Deterministic domain-audit service with a frozen caller command, immutable domain-event registry, specification-owned canonical actions, required and allowed metadata rules, safe UUID normalization, bounded payload validation, and safe mandatory-failure exceptions.
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
- Versioned deterministic interview coordinator with an immutable six-action allowlist, candidate-only narrow tool adapter, approved-question sequencing, structured stop/failure/escalation results, and no generative, messaging, arbitrary-data, or employment-decision authority.
- Deterministic session expiry and technical-failure services plus idempotent human escalation. Candidate requests pause active sessions, mandatory privacy-safe audit failure rolls back state and escalation together, and escalation records never contain answer, transcript, resume, token, path, or secret data.

## Current work

Week 2 remains complete at checkpoint `064100a`. Week 3 Milestones 3.1 through 3.6 are committed at `2bd2710`, `473ea99`, `a64e9be`, `40789e2`, `da6cf21`, and `897aacc` on `feat/week-3-ai-interview-runtime`; Week 3 is complete and Week 4 has not started.

Current frontend state on 2026-10-30: branch `feat/week-3-ai-interview-runtime`, documentation HEAD `5b37ca8`, and product checkpoint `897aacc`. The worktree contains the documented, uncommitted Figma-to-Django screens plus their focused tests and context updates; no unexpected blocker is recorded. The latest complete suite remains 201 passing tests. `Interview Management` (`30:8`) completes the Recruiter Portal with verified-recruiter, active-company, candidate-review capability, company-scoped schedule visibility, current-policy readiness indicators, and only existing invitation/session/cancellation/reschedule-review actions. Week 3 remains 100% and conservative overall progress remains 75%.

The Figma `Home / Desktop 1440` frame is implemented in the current uncommitted worktree as the public `accounts:home` route. It uses a dedicated semantic template and responsive stylesheet for the navbar, hero, candidate-dashboard preview, benefits, recruitment process, trust section, final CTA, and footer. The directly affected implementation files are `backend/accounts/views.py`, `backend/accounts/urls.py`, `backend/accounts/tests.py`, `frontend/templates/accounts/home.html`, and `frontend/static/accounts/css/home.css`.

Validation for the homepage work: Django system check reported 0 issues; migration drift reported no changes; 39 focused account tests passed; the clean full rerun passed 197 tests; pip check reported no broken requirements; Ruff passed for `backend`; and `git diff --check` passed. The runs emitted the existing two Daphne deprecation warnings and pytest-cache permission warning. The first full-suite attempt encountered a low-memory failure while the temporary development server was running; after stopping it, the rerun passed. Automated browser screenshot comparison was unavailable because the connected computer-use surface could not safely determine the active browser URL.

The Figma `How It Works` frame (`37:20`) is implemented at the public `accounts:how_it_works` route. It reuses the homepage navigation/footer design system and adds the approved hero, five-step workflow, role cards, transparency section, CTA, responsive layouts, and local Figma bullet asset. The route is linked from the completed Home page. Changed files for this screen are `backend/accounts/views.py`, `backend/accounts/urls.py`, `backend/accounts/tests.py`, `frontend/templates/accounts/home.html`, `frontend/templates/accounts/how_it_works.html`, `frontend/static/accounts/css/how-it-works.css`, and `frontend/static/accounts/img/teal-bullet.svg`.

Validation for `How It Works`: Django system check reported 0 issues; both new static assets were discoverable; 41 focused account tests passed with the three known warnings; and `git diff --check` passed. The latest complete-suite result remains 197 passing tests from the immediately preceding homepage validation.

The existing `accounts:login` route now implements the Figma `Login` frame (`39:29`) without changing `EmailLoginView`, `EmailLoginForm`, django-axes throttling, CSRF, role redirects, or authentication audit behavior. The responsive split-screen template uses the real Django form and validation errors, includes an accessible password-visibility control, and links candidate registration to the existing signup route. `Forgot password?` is deliberately non-interactive because password reset remains deferred. Changed files for this screen are `frontend/templates/accounts/login.html`, `frontend/static/accounts/css/login.css`, `frontend/static/accounts/js/login.js`, and `backend/accounts/tests.py`.

Validation for Login: Django system check reported 0 issues; the page stylesheet and JavaScript were discoverable; 42 focused account tests passed with the three known warnings; and `git diff --check` passed. The existing successful-login, authorization, and redirect tests remain in that focused suite.

The existing candidate-only `accounts:signup` route now implements the Figma `Candidate Signup` frame (`43:32`) with the real `CandidateSignupForm`, accessible labels and errors, responsive layouts, an accurate verification-before-applying notice, and a clear candidate-only registration boundary. It preserves the allowlisted name/email/password fields, candidate role assignment, duplicate-email protection, Argon2/password validation, CSRF, automatic login, and dashboard redirect. Changed files for this screen are `frontend/templates/accounts/signup.html`, `frontend/static/accounts/css/signup.css`, and `backend/accounts/tests.py`.

Candidate Signup final validation passed on 2026-10-30: 201 complete tests passed; Django system check reported 0 issues; migration drift reported no changes; pip check found no broken requirements; Ruff passed across `backend`, `ai_system`, `ml`, and `tests`; and `git diff --check` passed. Known non-failing warnings remain the two Daphne Python 3.16 asyncio deprecations and one pytest-cache permission warning.

The candidate-only `accounts:candidate_dashboard` route now implements the Figma `Candidate Dashboard` frame (`15:3`). It uses real candidate profile, skill, active résumé, application, company, and current future interview-schedule data for the profile progress, summary cards, next interview, and recent applications. It retains the existing role guard, POST/CSRF-protected email verification and logout actions, candidate-scoped links, and safe empty states. The layout has the approved navy sidebar, responsive mobile menu, accessible focus/heading structure, and desktop/tablet/mobile card behavior. Changed files for this screen are `backend/accounts/views.py`, `backend/accounts/tests.py`, `frontend/templates/accounts/candidate_dashboard.html`, and `frontend/static/accounts/css/candidate-dashboard.css`.

Candidate Dashboard validation on 2026-10-30: 46 focused account tests passed; Django system check reported 0 issues; Ruff passed for `backend/accounts`; the new stylesheet was discoverable through Django staticfiles; and `git diff --check` passed. The latest complete-suite result remains 201 passing tests from the immediately preceding Candidate Signup checkpoint. Known non-failing warnings remain the two Daphne Python 3.16 asyncio deprecations and one pytest-cache permission warning.

The candidate-only `candidates:profile_edit` route now implements the Figma `My Profile & AI Consent` frame (`16:10`). It renders the existing allowlisted `CandidateProfileForm`, account-derived read-only name/email, persisted skills with an honest empty state, a data-derived completion indicator, and the current-policy consent status resolved from append-only history. The real POST/CSRF-protected consent route continues to call the deterministic grant/revoke services; a fixed allowlisted return target keeps profile-originated actions on the profile page without introducing an open redirect. Changed files are `backend/candidates/views.py`, `backend/candidates/test_candidate_workflow.py`, `frontend/templates/candidates/profile_form.html`, `frontend/static/candidates/css/candidate-profile.css`, and `frontend/static/accounts/img/consent-toggle-on.svg`.

My Profile & AI Consent validation on 2026-10-30: 20 candidate tests passed initially and the final combined candidate/account suite passed 66 tests; Django system check reported 0 issues; Ruff passed for `backend/candidates`; Django staticfiles found the profile stylesheet and Figma consent-toggle asset; and `git diff --check` passed. The latest complete-suite result remains 201 passing tests. Limitations: skill editing is not exposed because no supported candidate skill-mutation route exists, and account name/email remain read-only because they are outside the profile form allowlist.

The candidate-only `candidates:resume_list` route now implements the Figma `My Résumé` frame (`20:13`). It combines the owner-scoped active/history listing with the existing secure `ResumeUploadForm`, upload route, protected download route, randomized storage, bounded processing, and successful-only replacement service. The page displays only original filename, safe processing status, upload date, and file size; storage names, paths, checksums, extracted text, and other candidates' records are not rendered. Direct visits and invalid submissions to the upload route render the same unified résumé workspace. Changed files are `backend/candidates/views.py`, `backend/candidates/test_candidate_workflow.py`, `frontend/templates/candidates/resume_list.html`, `frontend/static/candidates/css/candidate-resume.css`, and `frontend/static/accounts/img/resume-upload.svg`.

My Résumé validation on 2026-10-30: 25 focused candidate tests passed; Django system check reported 0 issues; Ruff passed for `backend/candidates`; Django staticfiles found the résumé stylesheet and Figma upload icon; and `git diff --check` passed. The latest complete-suite result remains 201 passing tests and is not represented as a post-résumé full run. Structural PDF/DOCX validation and bounded parsing remain explicitly distinct from production malware scanning.

The candidate view of `recruitment:job_list` now implements the Figma `Browse Jobs` frame (`24:17`). It renders only the existing authorized queryset of open, unexpired jobs belonging to active companies, with real company, location/workplace, employment, experience, description, skill, and publication data plus existing authorized detail links. It includes the shared candidate sidebar, safe empty state, responsive cards, and profile helper. Search, filtering, sorting controls, and pagination remain visibly non-functional and are labelled as unavailable because the current backend does not support them; no fake behavior was introduced. Recruiter job-list behavior is preserved in a separate compatibility template. Changed files are `backend/recruitment/views.py`, `backend/recruitment/test_job_workflow.py`, `frontend/templates/recruitment/job_list.html`, `frontend/templates/recruitment/recruiter_job_list.html`, and `frontend/static/recruitment/css/job-list.css`.

Browse Jobs validation on 2026-10-30: the complete focused recruitment suite passed 20 tests; Django system check reported 0 issues; Ruff passed for `backend/recruitment`; Django staticfiles found the new stylesheet; and `git diff --check` passed. The first focused run had one presentation-boundary assertion mismatch around the result-count markup; the assertion was corrected without weakening the rendered behavior, and the reruns passed. The latest complete-suite result remains 201 passing tests and is not represented as a post-Browse-Jobs full run.

The candidate views of `recruitment:job_detail` and `recruitment:application_create` now complete Figma `Job Details & Apply` (`26:24`). The detail route uses the existing eligible-job authorization filter and persisted job/company data. The application route retains candidate-only authorization, CSRF, verified-email enforcement, candidate-owned active processed resume selection, duplicate prevention, allowlisted cover note, optional append-only interview consent, and deterministic auditing through the existing service. The responsive form shows only safe authorized resume metadata, validation errors, privacy/human-decision guidance, and real secure actions. Save Job remains visibly disabled because no saved-jobs backend exists.

Job Details & Apply validation on 2026-10-30: the detail route/access test passed, followed by **10 focused application-workflow tests**. Django system check reported 0 issues; Ruff passed for the changed recruitment Python files; Django staticfiles found both dedicated stylesheets; and `git diff --check` passed. The complete suite was not rerun; its latest verified result remains 201 passing tests.

The candidate view of `recruitment:application_list` now implements Figma `My Applications & AI Interview` (`27:27`). It uses only candidate-owned applications, current confirmed future schedules, effective current-policy consent, verified-email state, active processed résumé state, and authorized call-session status. It provides real detail, interview, and reschedule links when the existing routes support them; otherwise it shows safe empty states. Recruiters retain their existing company-scoped application listing through a compatibility template and do not receive the candidate dashboard. No answers, transcripts, résumé content, invitation credentials, storage paths, or private recruiter data are rendered.

My Applications & AI Interview validation on 2026-10-30: **12 application-workflow tests passed**, followed by **12 focused scheduling/call-session regression tests**. Django system check reported 0 issues; Ruff passed for the changed recruitment Python files; Django staticfiles found `recruitment/css/application-list.css`; and `git diff --check` passed. The latest complete-suite result remains 201 passing tests and was not rerun for this focused screen.

The existing `accounts:recruiter_dashboard` route now implements Figma `Recruiter Dashboard` (`28:3`). Access requires a persisted active recruiter user, verified recruiter profile, active company, and at least one recruiter capability. All metrics, recent applications, upcoming interviews, and published-job cards are derived from that recruiter's company only; candidate names fall back to a generic label rather than exposing email addresses. Create/manage/review links are shown only for the corresponding existing capability, while unsupported company-profile functionality is visibly unavailable. Changed task files are `backend/accounts/views.py`, `backend/accounts/tests.py`, `frontend/templates/accounts/recruiter_dashboard.html`, and `frontend/static/accounts/css/recruiter-dashboard.css`.

Recruiter Dashboard validation on 2026-10-30: **29 account tests passed**, followed by **31 focused recruitment and interview tests**. Django system check reported 0 issues; Ruff passed for the changed account Python files; Django staticfiles found `accounts/css/recruiter-dashboard.css`; and `git diff --check` passed. The latest complete-suite result remains 201 passing tests and was not rerun for this focused screen.

The recruiter view of `recruitment:job_list` now implements Figma `Manage Jobs` (`28:136`). The existing role-dispatch route continues to send candidates to their separate Browse Jobs page, while recruiters must pass the persisted active-user, verified-profile, active-company, and `can_manage_jobs` checks in `recruiter_jobs()`. The management page renders only the recruiter's company jobs, real annotated application counts, persisted statuses and update dates, existing create/edit links, and only currently valid publish/reopen/close POST actions. Search/filter/sort controls are visibly disabled because no backend support exists, and department is labelled unavailable because `JobPosting` has no department field. Changed task files are `backend/recruitment/views.py`, `backend/recruitment/test_job_workflow.py`, `frontend/templates/recruitment/recruiter_job_list.html`, and `frontend/static/recruitment/css/manage-jobs.css`.

Manage Jobs validation on 2026-10-30: **13 focused job-workflow tests passed**, followed by **3 deterministic transition-service tests**. Django system check reported 0 issues; Ruff passed for the changed recruitment Python files; Django staticfiles found `recruitment/css/manage-jobs.css`; and `git diff --check` passed. The latest complete-suite result remains 201 passing tests and was not rerun for this focused screen.

The recruiter view of `recruitment:application_list` provides the left applicant-list workspace from Figma `Applicants & Application Details` (`29:5`). It keeps the existing `recruiter_applications()` authorization and company scope, builds safe initials/name labels without email fallback, and renders only job title, applied date, persisted application status, and the existing authorized application-detail link. Search/job/status controls are visibly disabled because the route has no filtering backend. The list-only route does not invent a selected row; selection and the completed detail panel appear only on the authorized application-detail route. Changed task files are `backend/recruitment/views.py`, `backend/recruitment/test_application_workflow.py`, `frontend/templates/recruitment/recruiter_application_list.html`, and `frontend/static/recruitment/css/recruiter-applications.css`.

Applicant-list stage validation on 2026-10-30: **14 focused application-workflow tests passed**. Django system check reported 0 issues; Ruff passed for the changed recruitment Python files; Django staticfiles found `recruitment/css/recruiter-applications.css`; and `git diff --check` passed. The latest complete-suite result remains 201 passing tests and was not rerun for this focused partial-screen task.

The existing recruiter-only `recruitment:application_detail` route now completes the right-side detail panel for Figma `Applicants & Application Details` (`29:5`) while reusing the Stage A list workspace. The panel shows only company-scoped candidate identity, location, experience, persisted skills, verified-email state, effective current-policy processing/interview consent, safe résumé filename and processing status, application status, current schedule, existing recruiter call-session or invitation actions, pending reschedule actions, and audit-derived application history. The recruiter résumé-download control remains disabled because no recruiter-authorized download route exists; no private résumé text, storage path, checksum, interview answer/transcript, token, or audit metadata is rendered. The selected row is shown only on the detail route, and the two columns stack on narrower screens.

Applicants & Application Details completion validation on 2026-10-30: **25 focused application and interview-scheduling tests passed**; Django system check reported 0 issues; Ruff passed for the changed recruitment Python files; Django staticfiles found `recruitment/css/recruiter-applications.css`; and `git diff --check` passed. The run emitted the two known Daphne Windows asyncio deprecations and one pytest-cache permission warning. The latest complete-suite result remains 201 passing tests and was not rerun for this focused screen.

The existing recruiter `calling:recruiter_session_list` route now implements Figma `Interview Management` (`30:8`) from company-scoped current schedules rather than only prepared call sessions. This one recruiter-facing page denies administrators and requires a persisted active recruiter, verified profile, active company, and candidate-review capability; the underlying administrator call-session review boundary remains unchanged. It renders real upcoming/awaiting/reschedule totals, an honest disabled filter strip, responsive schedule rows, a selected schedule panel, verified-email and effective current-policy consent state, safe invitation delivery/confirmation state, existing call-session status and cancellation/retry routes, and company-scoped pending reschedule review forms. Recruiter-initiated rescheduling is visibly unavailable because only candidates have an existing request route. No token, résumé, answer/transcript, audit metadata, internal delivery error, or other-company record is rendered.

Automatic context checkpoint on 2026-10-30: branch `feat/week-3-ai-interview-runtime`, HEAD `5b37ca8`, and the dirty worktree contain only the fourteen documented Figma screens, focused tests/static assets, and context updates. Admin Dashboard (`32:3`) is the current unstarted task. The latest focused result is 59 passing calling/interview/application tests; the latest complete-suite checkpoint remains 201 passing tests. No blocker remains.

Interview Management validation on 2026-10-30: the first four-test run found a missing `django.utils.timezone` import in the new view; that import was added and the same run passed **4 tests**. Final focused validation passed **59 calling, interview-scheduling, and application tests**; Django system check reported 0 issues; Ruff passed for the changed calling Python files; Django staticfiles found `calling/css/recruiter-interviews.css`; and `git diff --check` passed. The final run emitted the two known Daphne Windows asyncio deprecations and one pytest-cache permission warning. The latest complete-suite result remains 201 passing tests and was not rerun for this focused screen.

The existing administrator-only `accounts:admin_dashboard` route now implements Figma `Admin Dashboard` (`32:3`). It renders real active-company, verified-recruiter, published-job, and current-week interview counts; recent company records; persisted recruiter verification state; fixed-label privacy-safe platform activity; existing Django admin provisioning links for staff administrators; honest disabled states for unsupported audit/settings interfaces; and responsive empty states. Candidate and recruiter roles remain denied. The activity list never renders audit metadata, descriptions, resource IDs, actor email snapshots, or caller-controlled action text. Changed task files are `backend/accounts/views.py`, `backend/accounts/tests.py`, `frontend/templates/accounts/admin_dashboard.html`, and `frontend/static/accounts/css/admin-dashboard.css`.

Admin Dashboard validation on 2026-10-30: **57 account tests passed**, followed by **141 focused account, recruitment-administration, and audit tests**. Django system check reported 0 issues; Ruff passed for `backend/accounts`; Django staticfiles found `accounts/css/admin-dashboard.css`; and `git diff --check` passed. The initial sandboxed validation launch was denied access to the virtual environment's base Python and was rerun successfully with the required execution permission. The complete suite was not rerun; its latest verified result remains 201 passing tests.

The existing administrator-only `accounts:admin_dashboard` route now also implements Figma `Companies & Recruiters Management` (`33:4`) through the explicit `?section=management` presentation state. It uses persisted companies and recruiter profiles, safe annotated recruiter/open-job counts, company/access status, safe name/initial fallbacks, existing Django admin add/change pages for staff administrators, disabled search/filter controls, responsive tables/cards, and honest empty states. The default Admin Dashboard remains intact and now links to the management state. No model, migration, provisioning rule, verification logic, deletion flow, management API, or fake record was added; emails, phone numbers, candidate data, audit metadata, secrets, and private workflow content are not rendered.

Companies & Recruiters Management validation on 2026-10-30: **57 account tests passed**, followed by **141 focused account, recruitment-administration, and audit tests**, and then the complete suite passed **243 tests**. Django system check reported 0 issues; migration drift reported no changes; pip check found no broken requirements; Ruff passed across `backend`, `ai_system`, `ml`, and `tests`; Django staticfiles found `accounts/css/admin-management.css`; and `git diff --check` passed. The three known non-failing warnings remain two Daphne Windows asyncio deprecations and one pytest-cache permission warning.

## Pending work

- Browser audio transport and live integration of the optional STT, TTS, and VAD adapters remain beyond the deterministic Week 3 baseline.
- Broader specialist-agent orchestration, semantic safety checks, evaluation, and human-review workflow.
- Operational agent/evaluation pipeline, observability, retention jobs, production hardening, and deployment execution.

## Known limitations and blockers

- **Limitations:** No operational voice pipeline, audio transport, broader specialist-agent orchestration, generative inference, malware scanner, final human-review UI, or production deployment exists yet. Voice adapters are optional boundaries and were tested with injected synthetic engines, not live hardware or models. The current WebSocket carries status only, and the interview remains an explicitly labelled text simulation; development Channels is in-memory. Resume checks are structural parsing controls, not malware scanning. All sixteen approved Figma desktop screens are implemented, but final cross-browser/manual visual QA has not occurred. Recruiter résumé viewing remains unavailable because no recruiter-authorized download route exists; interview tabs and recruiter-initiated rescheduling remain unavailable because the backend supports neither; job and candidate search/filter/sort controls are unavailable; profile skills are display-only until a secure supported editing workflow exists; password reset and recruiter company-profile management remain deferred. Administrator mutations continue through existing Django admin pages because no separate application management workflow exists.
- **Blockers:** No product blocker is recorded. Automated browser screenshot comparison for the homepage was unavailable in the current tool session; Django rendering and route behavior are covered by tests.

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
.\.venv\Scripts\python.exe -m ruff check backend ai_system ml tests
git diff --check
git status --short
```

## Exact next recommended task

Perform a **final manual UI/QA review and prepare one reviewed frontend commit** covering the sixteen documented Figma screens. Verify desktop/tablet/mobile rendering, keyboard navigation, responsive tables, accumulated diffs, and that only intended frontend/view/test/context changes are staged before committing. Do not begin deployment or new product functionality.

Relevant files:

- Figma file `xtMdAVZFQsUaBej8mwJWU3` and all sixteen documented frame nodes
- `backend/accounts/views.py`
- `backend/accounts/urls.py`
- `backend/accounts/tests.py`
- `backend/candidates/views.py`
- `backend/recruitment/views.py`
- `backend/calling/views.py`
- `frontend/templates/`
- `frontend/static/`
- `docs/WORK_LOG.md`

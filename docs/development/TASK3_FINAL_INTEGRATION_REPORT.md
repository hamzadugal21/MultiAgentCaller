# Task 3 Final Integration Report

Last updated: 2026-11-04 (Asia/Karachi)

## Status: PARTIAL — corrected persisted run still blocked

## 2026-11-05 release-sprint update

The isolated database and role were successfully verified before a later
sidebar-process restart. A QA-only three-turn Qwen/MiniLM/speech-to-Django
command, advisory evaluation, browser VAD/Whisper flow, Piper playback, and
local-demo hardening are implemented without schema changes. Three real
synthetic attempts failed closed and persisted no answers. Their failures
exposed a loopback-disconnect exception and excessive simultaneous model
memory; the exception is contained and the command now releases speech models
before starting Qwen. The corrected command has not run because the restarted
process no longer has the private QA variables. All further QA writes remain
stopped until the verifier succeeds again. See
[Final Release Readiness](FINAL_RELEASE_READINESS.md).

The original isolation finding below is retained as history and is superseded
only where this update explicitly records later verification and implementation.

The requested state-changing Qwen-to-Django QA adapter was not implemented and
no new state-changing isolated-QA scenarios were run. This is intentional and
fail-closed. `config.settings_qa` now requires separate QA-only environment
variables, disables `.env` loading, rejects non-PostgreSQL/non-`hireflow_qa_`
database and role names, and defaults model actions to disabled. Its read-only
verifier compares the configured and connected database identities. A separate
database and role have not yet been provisioned or verified, so proof that a
write-capable database is separate from normal development and production data
still does not exist.

No existing development or production database was used for new model-driven
state-changing QA. No real candidate data, external notification, deployment,
or credential was accessed.

The isolated-settings contract checks pass without a database connection.
Focused Ruff and `git diff --check` pass for this QA-isolation preparation.

## 2026-11-06 stateless model verification

Without database access, the sequential release preflight completed three
transient Piper/Silero/Faster-Whisper turns (three VAD segments), released
their native allocations, then passed one real Q3_K_S Qwen Interview proposal
through permission-filtered MiniLM retrieval. The accepted proposal was
`continue` with one authorized source; Qwen load was 1,421 ms and generation
was 3,125 ms. This establishes neither persisted workflow progress nor browser
microphone behavior. QA variables remain absent from the active process, so
all database writes remain blocked.

## 2026-11-05 verification status

The operator subsequently reported that the disposable QA database and role were
provisioned. The current agent process has none of the required QA environment
variables, so that claim cannot yet be verified without exposing a secret. Only
boolean variable presence was checked. This report remains blocked until the
private variables are supplied to the process and the read-only verifier
succeeds.

## Verified non-writing evidence

- Shared Qwen held-out proposal evaluation: 99/100 contextual actions and
  100/100 accepted schemas; see [Task 3 evaluation](TASK3_EVALUATION.md).
- Real MiniLM synthetic RAG checks passed relevant ranking, source attribution,
  consent/candidate/company isolation, injection marking, and stale-source
  removal.
- Local Piper → Silero VAD → Faster-Whisper synthetic smoke passed; audio was
  transient only.
- Bounded shared-Qwen queue measurement completed one, two, and three
  synthetic callers without errors. It is not an HTTP/browser load result.
- The existing full pytest suite previously passed 367 tests with two known
  warnings. Existing Django integration tests exercise deterministic workflows
  using Django-managed test databases, but they do not authorize a new
  Qwen-driven state-changing QA adapter under the requested isolation rules.

## Not performed

- Qwen proposal → Django service write path.
- Three complete model-driven interview scenarios.
- Consent-withdrawal and malicious-interaction scenarios against a Qwen-driven
  write path.
- New authenticated HTTP/WebSocket model-action QA.
- HTTP, WebSocket, browser, microphone, CPU-utilization, or production load
  testing.

## Required prerequisite to resume

An operator with local PostgreSQL administration must provision the isolated
database before any write-capable QA. From PowerShell, open an interactive
administrator `psql` session (it prompts locally and does not print a password):

```powershell
$psql = 'C:\Program Files\PostgreSQL\18\bin\psql.exe'
& $psql -U postgres -d postgres -v ON_ERROR_STOP=1
```

In that interactive session, run the following and use `\password` when it
prompts for a new unique QA-only password:

```sql
CREATE ROLE hireflow_qa_runner LOGIN;
\password hireflow_qa_runner
CREATE DATABASE hireflow_qa_release OWNER hireflow_qa_runner TEMPLATE template0;
\q
```

Then, in the same private operator shell, set the QA variables without saving
them to Git or `.env`, verify the connection, and apply only existing approved
migrations to that disposable database:

```powershell
$env:HIREFLOW_QA_MODE = '1'
$env:QA_DATABASE_ISOLATION_ACK = 'disposable'
$env:QA_DATABASE_URL = Read-Host 'Enter the QA PostgreSQL URL'
$env:QA_DJANGO_SECRET_KEY = & .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(64))"
$env:DJANGO_SETTINGS_MODULE = 'config.settings_qa'
$env:DJANGO_READ_DOT_ENV = 'False'
.\.venv\Scripts\python.exe scripts\verify_qa_database.py
.\.venv\Scripts\python.exe backend\manage.py migrate --noinput
```

After the verifier succeeds, the proposed adapter may call only existing
allowlisted deterministic Django services and must remain disabled outside QA.

This report is not authorization for production activation or real-user AI.

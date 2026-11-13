# MultiAgent Recruitment Caller

An industry-oriented, browser-based recruitment platform where specialized AI agents conduct, evaluate, monitor, and audit candidate screening interviews.

Weeks 1 through 3 are complete. Week 4 is in progress: deterministic rubric scoring, authorized human finalization, synthetic evaluation-quality/safety coverage, dry-run-first retention/incident readiness, repository-side production hardening, and local speech-model smoke verification are implemented. Browser microphone QA, live-model quality evaluation, external infrastructure, and deployment remain later work.

## Core agents

Calling Orchestrator, Candidate Profile, Interview, Evaluation, FAQ, Scheduling, Safety, and Escalation agents, supported by a deterministic Python domain-audit service.

## Stack

Python 3.14, Django 6.1, Django Channels, PostgreSQL, Redis, Faster Whisper, Piper Plus TTS, Silero VAD, PyTorch, Sentence Transformers, scikit-learn, and spaCy.

## Local setup

1. Create and activate .venv
2. Install requirements.txt
3. Copy .env.example to .env and add private values
4. Run python backend\manage.py migrate
5. Run python backend\manage.py createsuperuser
6. Run python backend\manage.py runserver

## Tests

Run: `python -m pytest -q` (current stable grouped validation: 319 collected tests).

## Security

Never commit .env, credentials, candidate documents, transcripts, recordings, or model binaries. Public signup creates candidate accounts only. Passwords use Argon2. Audit events are protected by Django and PostgreSQL. Call recording is disabled by default and requires candidate consent.

Retention is read-only by default: `python backend/manage.py run_retention simulated_interview_answers` previews a bounded batch. Mutation requires an explicit `--apply` flag and should be used only after reviewing the documented policy and dry-run count. The initial policy clears old terminal-session answer/transcript text; it does not delete files or immutable governance evidence. See the [incident-response runbook](docs/security/INCIDENT_RESPONSE.md) and [unverified backup/restore checklist](database/docs/BACKUP_RESTORE.md).

## Optional local microphone transcription

Candidate interview audio is transient: it is decoded in memory, sent only to the local Faster-Whisper adapter, returned as editable text, and discarded. It is never stored as a recording or answer unless the candidate explicitly submits the existing answer form. Download the multilingual local base model explicitly before microphone QA: `python scripts\download_whisper_base.py`. The model is stored under ignored `var/models/whisper/base`; server startup never downloads it. The typed-answer path remains available when the microphone, decoder, or model is unavailable.

For optional local text-to-speech, run `python scripts\download_piper_voice.py`, then verify all local voice models with `python scripts\smoke_local_voice_models.py`. The selected Piper Plus voice supports English but has corpus-derived use conditions in its downloaded `NOTICE.md`; review those conditions before redistribution or deployment. The smoke script keeps its synthetic audio only in memory.

## Settings

Development: config.settings_development
Production: config.settings_production

## Deployment planning

The future free public demonstration is documented in the [Render deployment plan](docs/development/RENDER_DEPLOYMENT.md). The repository includes a fail-closed production settings boundary, fixed `/health/` response, lightweight Render blueprint, static build script, [production preflight checklist](docs/development/PRODUCTION_PREFLIGHT.md), and [release-readiness handoff](docs/development/RELEASE_READINESS.md). No cloud account, external service, private production configuration, backup, or deployment currently exists.


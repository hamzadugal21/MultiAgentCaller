# MultiAgent Recruitment Caller

An industry-oriented, browser-based recruitment platform where specialized AI agents conduct, evaluate, monitor, and audit candidate screening interviews.

Weeks 1 through 3 are complete. Week 3 delivers the deterministic call-session foundation, simulated interview, authorized status WebSocket, optional local VAD/STT/TTS adapters, narrow deterministic interview coordinator, and privacy-safe human-escalation/failure boundary. Live voice operation, evaluation, final human review, production hardening, and deployment remain later work.

## Core agents

Calling Orchestrator, Candidate Profile, Interview, Evaluation, FAQ, Scheduling, Safety, and Escalation agents, supported by a deterministic Python domain-audit service.

## Stack

Python 3.14, Django 6.1, Django Channels, PostgreSQL, Redis, Faster Whisper, Piper TTS, Silero VAD, PyTorch, Sentence Transformers, scikit-learn, and spaCy.

## Local setup

1. Create and activate .venv
2. Install requirements.txt
3. Copy .env.example to .env and add private values
4. Run python backend\manage.py migrate
5. Run python backend\manage.py createsuperuser
6. Run python backend\manage.py runserver

## Tests

Run: `python -m pytest -q` (current validated total: 195 tests).

## Security

Never commit .env, credentials, candidate documents, transcripts, recordings, or model binaries. Public signup creates candidate accounts only. Passwords use Argon2. Audit events are protected by Django and PostgreSQL. Call recording is disabled by default and requires candidate consent.

## Settings

Development: config.settings_development
Production: config.settings_production

## Deployment planning

The future free public demonstration is documented in the [Render deployment plan](docs/development/RENDER_DEPLOYMENT.md). No deployment is currently configured.


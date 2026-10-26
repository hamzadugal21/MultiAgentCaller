# MultiAgent Recruitment Caller

An industry-oriented, browser-based recruitment platform where specialized AI agents conduct, evaluate, monitor, and audit candidate screening interviews.

Week 2's secure pre-interview workflow is complete. Week 3 now includes the deterministic call-session foundation, simulated interview, authorized status WebSocket, optional local VAD/STT/TTS adapters, and a narrow deterministic interview coordinator. Final Week 3 safety/integration review remains.

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

Run: `python -m pytest -q` (current validated total: 186 tests).

## Security

Never commit .env, credentials, candidate documents, transcripts, recordings, or model binaries. Public signup creates candidate accounts only. Passwords use Argon2. Audit events are protected by Django and PostgreSQL. Call recording is disabled by default and requires candidate consent.

## Settings

Development: config.settings_development
Production: config.settings_production

## Deployment planning

The future free public demonstration is documented in the [Render deployment plan](docs/development/RENDER_DEPLOYMENT.md). No deployment is currently configured.


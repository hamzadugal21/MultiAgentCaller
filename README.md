# MultiAgent Recruitment Caller

An industry-oriented, browser-based recruitment platform where specialized AI agents conduct, evaluate, monitor, and audit candidate screening interviews.

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

Run: python -m pytest -q

## Security

Never commit .env, credentials, candidate documents, transcripts, recordings, or model binaries. Public signup creates candidate accounts only. Passwords use Argon2. Audit events are protected by Django and PostgreSQL. Call recording is disabled by default and requires candidate consent.

## Settings

Development: config.settings_development
Production: config.settings_production


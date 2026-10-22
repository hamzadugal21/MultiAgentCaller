# Render Deployment Plan

This document records the approved future deployment plan. It is planning material only: no hosting account, cloud service, repository connection, environment configuration, or deployment has been created.

## Deployment purpose

- Render will host the public CV and portfolio demonstration website.
- The deployment must remain completely free. Availability and limits of all free plans must be rechecked before deployment, and paid upgrades must not be enabled implicitly.
- The hosted version is a demonstration, not a production recruitment service.
- Only synthetic demonstration accounts and data may be used. Real candidate, recruiter, company, resume, recording, transcript, or other personal information is prohibited.

## Planned free services

- **Application hosting:** Render Free Web Service running Django through Daphne.
- **Relational database:** Neon Free PostgreSQL.
- **Channel layer:** Upstash Free Redis.
- **Protected demo uploads:** An S3-compatible free object-storage provider to be selected later.
- **Source repository:** GitHub with a sanitized public repository.

Do not create accounts or connect any of these services until the final deployment milestone is explicitly approved.

## Dependency boundary

- `requirements/render.txt` is the lightweight cloud dependency entry point.
- It includes `requirements/base.txt` only and must recursively exclude every dependency from `requirements/ml.txt`.
- Daphne is the selected ASGI server because the project is designed to use Django Channels and WebSockets.
- Do not add Gunicorn or Uvicorn unless a later measured deployment requirement justifies revisiting this decision.
- PostgreSQL, Redis, WhiteNoise, authentication/security, and PDF/DOCX processing dependencies already come from `requirements/base.txt`.
- `requirements/production.txt` remains the full production dependency definition and is not the Render Free build boundary.

## Hosted demonstration boundary

- The hosted website will initially use a clearly labelled simulated AI-call mode.
- The simulation must never be described or presented as an operating AI call.
- The real Faster Whisper, Piper, Silero VAD, PyTorch, and local-model pipeline remains runnable locally.
- A future portfolio demonstration may include a recorded video showing the real local pipeline.
- The hosted simulation must preserve the same human-review, privacy, consent, authorization, and audit boundaries expected of the real workflow.

## Future Week 4 tasks

The following work is required during the final deployment milestone, but none of it is implemented by this document:

- Add `render.yaml`.
- Add `build.sh`.
- Add `.python-version` after selecting the exact supported Python patch version.
- Add a minimal `/health/` endpoint.
- Configure private Render environment variables.
- Validate production operation with `DEBUG=False`.
- Configure Render `ALLOWED_HOSTS`.
- Configure `CSRF_TRUSTED_ORIGINS`.
- Validate HTTPS redirects and secure-cookie behavior.
- Run `collectstatic` as part of the approved build process.
- Define and execute the approved database-migration strategy.
- Configure Neon PostgreSQL.
- Configure Upstash Redis for the Channels layer.
- Configure external protected media storage; never rely on Render's ephemeral filesystem for persistent uploads.
- Create synthetic demonstration accounts and data.
- Run deployment-specific security checks.
- Run production settings validation with `python backend/manage.py check --deploy`.
- Run a post-deployment smoke test.
- Add the CV-ready public URL to the README after successful validation.

## Explicitly deferred decisions

- Object-storage provider and its Python dependency.
- Final Render start command.
- Database-migration execution strategy.
- Email provider.
- Custom domain.
- Whether new visitors may register through the public demonstration.
- Synthetic demo-data reset strategy.
- Exact Python patch version.

These decisions require evidence from the final application, current free-plan limits, and an explicit deployment review. Do not guess or silently select them earlier.

## Safety rules

- Never commit `.env`, credentials, database URLs, Redis URLs, SMTP credentials, secret keys, uploaded resumes, recordings, transcripts, or real personal data.
- Configure Render secrets only through its private environment-variable controls.
- Never use Render's ephemeral filesystem for persistent uploads.
- Do not deploy the full ML requirement set to Render Free.
- Do not change normal development behavior merely to satisfy hosting.
- Isolate deployment-specific behavior behind explicit production settings and environment flags.
- Keep the public repository sanitized and verify its Git history before connecting it to a public host.
- Do not represent the demonstration as suitable for real recruitment, real candidate processing, or automated employment decisions.

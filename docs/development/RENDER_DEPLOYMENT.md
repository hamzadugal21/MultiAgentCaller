# Render Deployment Plan

This document records the approved future deployment plan and the tracked repository-side deployment boundary. No hosting account, cloud service, repository connection, private environment configuration, or deployment has been created.

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

## Tracked deployment preparation

The repository now provides:

- `render.yaml` with a free Python web-service blueprint, fixed health path, private environment-variable placeholders, and the Daphne ASGI start command.
- `build.sh`, which installs only `requirements/render.txt` and collects static files. It deliberately does not run migrations.
- `.python-version`, currently pinned to the project's validated Python 3.14.7 patch version; provider support must be rechecked before deployment.
- A fixed unauthenticated `/health/` response for GET/HEAD. It contains no dependency, database, cache, version, or configuration details and is not a database-readiness probe.
- Fail-closed production settings for `DEBUG`, signing-key quality, hosts, CSRF origins, PostgreSQL/SSL, Redis/TLS, HTTPS, cookies, proxy trust, staged HSTS, security headers, WhiteNoise, and privacy-safe Django request/security logging.
- A [production preflight checklist](PRODUCTION_PREFLIGHT.md).

`build.sh` runs `collectstatic`. The selected start command changes into `backend/`, disables Daphne access-request logging so token-bearing paths are not emitted, and starts `config.asgi:application` on the provider port. Django application/security logs remain available in privacy-safe form.

## Required private environment variables

Configure these values only through Render's private environment controls. Values must not be placed in `render.yaml`, Git, logs, or documentation.

- `DJANGO_SECRET_KEY`: unique high-entropy value of at least 50 characters.
- `ALLOWED_HOSTS`: explicit comma-separated deployment hostnames; wildcards are rejected.
- `CSRF_TRUSTED_ORIGINS`: explicit comma-separated HTTPS origins.
- `DATABASE_URL`: private Neon PostgreSQL URL.
- `REDIS_URL`: private Upstash TLS URL using `rediss://`.

The blueprint fixes non-secret controls: production settings module, no `.env` loading, `DEBUG=False`, trusted reverse-proxy handling, HTTPS redirect, PostgreSQL `sslmode=require`, and an initial HSTS duration of zero. Increase HSTS gradually only after HTTPS is verified; subdomain/preload flags remain off initially.

## Remaining deployment work

- Create and privately configure the approved Render, Neon, and Upstash services.
- Reconfirm that Render supports the pinned Python patch and the free-service blueprint.
- Define, review, and execute the database-migration strategy separately from the build.
- Configure external protected media storage; never rely on Render's ephemeral filesystem for persistent uploads.
- Select and test an email provider.
- Create synthetic demonstration accounts/data and decide whether visitor signup is allowed.
- Execute the production preflight, provider security review, post-deployment smoke test, and backup/restore rehearsal.
- Add a CV-ready public URL to the README only after successful validation.

## Explicitly deferred decisions

- Object-storage provider and its Python dependency.
- Database-migration execution strategy.
- Email provider.
- Custom domain.
- Whether new visitors may register through the public demonstration.
- Synthetic demo-data reset strategy.
- Whether Python 3.14.7 remains supported by Render at deployment time.

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

# Production Preflight Checklist

This checklist validates configuration before a future deployment. It does not prove that hosting, backups, external media storage, monitoring, or a production database exists.

## Private configuration gate

Configure private values through the hosting provider, never a tracked file. Production requires `DJANGO_SECRET_KEY`, explicit `ALLOWED_HOSTS`, explicit HTTPS `CSRF_TRUSTED_ORIGINS`, PostgreSQL configuration, and a TLS `REDIS_URL`. Set `DJANGO_SETTINGS_MODULE=config.settings_production`, `DJANGO_READ_DOT_ENV=False`, `DEBUG=False`, and `SECURE_SSL_REDIRECT=True`.

Only set `DJANGO_TRUST_PROXY_HEADERS=True` behind the reviewed hosted reverse proxy. Start HSTS at `SECURE_HSTS_SECONDS=0`; increase it only after HTTPS behavior is verified. Do not enable subdomain coverage or preload until every affected hostname is permanently HTTPS-ready.

## Pre-deployment validation

Run these commands in an isolated environment populated with synthetic, private configuration:

```powershell
.\.venv\Scripts\python.exe backend\manage.py check --deploy --settings=config.settings_production
.\.venv\Scripts\python.exe backend\manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe backend\manage.py collectstatic --noinput --dry-run --settings=config.settings_production
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m ruff check backend ai_system ml tests
git diff --check
```

Confirm that production configuration rejects `DEBUG=True`, placeholder or short signing keys, wildcard hosts, non-HTTPS trusted origins, non-PostgreSQL databases, weak database SSL modes, plaintext Redis URLs, and disabled HTTPS redirects.

## Infrastructure and release gate

- Verify PostgreSQL and Redis connectivity without printing connection strings.
- Select external protected object storage before allowing persistent uploads; Render's filesystem is ephemeral.
- Select and test an email provider before relying on email delivery.
- Review and execute a separately approved migration strategy. `build.sh` deliberately does not migrate the database.
- Run `collectstatic`, then verify representative static assets through HTTPS.
- Confirm `/health/` returns only `ok` for GET/HEAD and rejects mutation methods. It intentionally does not probe or disclose database/Redis state.
- Use synthetic demonstration accounts only and confirm the interview is labelled simulated.
- Review cookie, redirect, CSRF, host, WebSocket-origin, and cross-company authorization behavior.
- Complete the backup/restore checklist and post-deployment smoke test before describing the service as production-ready.

## Post-deployment checks

Confirm HTTPS redirects, secure cookies, host/origin rejection, static assets, authentication, protected media authorization, the simulated interview fallback, privacy-safe logs, and the fixed health response. Do not publish a URL until the security review passes. Do not claim deployment or backup readiness from this repository-only preflight.

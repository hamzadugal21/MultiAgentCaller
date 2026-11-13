# Security Policy

## Reporting

Report vulnerabilities privately to the repository owner. Never publish credentials, candidate data, resumes, transcripts, recordings, or production configuration in a public issue.

## Secrets

Never commit .env, Django secret keys, database passwords, Redis credentials, email credentials, deployment tokens, or private candidate files. Only .env.example containing placeholders may be committed.

## Authentication

Passwords use Argon2. Public signup creates candidates only. Recruiter and administrator accounts require administrative creation. Login attempts are rate-limited, role permissions are enforced server-side, and logout requires a CSRF-protected POST request.

## File uploads

Resumes are limited to PDF and DOCX, restricted to 5 MB, checked by extension and file structure, randomly renamed, and stored outside static files. Malware scanning must run before production document processing.

Candidate microphone clips for local transcription are restricted to browser audio types, bounded in bytes and decoded duration, rate-limited, decoded transiently in memory, and discarded immediately. The endpoint returns only editable text to the owning candidate; neither raw audio nor generated text enters media storage, audit metadata, WebSocket messages, recruiter/admin views, or logs. Only the existing explicit answer submission persists candidate text.

## Audit logs

Audit events use keyed integrity hashes and are protected against modification and deletion at both the Django and PostgreSQL layers.

## Retention and incidents

The retention command is read-only unless an operator supplies `--apply`. Applied runs are bounded, replay-safe, transactional, and mandatorily audited with counts and fixed codes only. The initial policy clears private answer/transcript text only for sufficiently old terminal simulated sessions; it does not delete files or change audit events, consent evidence, finalized evaluations, applications, escalations, or security records. Policy periods require later legal/privacy review and do not guarantee compliance.

Follow the [incident-response runbook](docs/security/INCIDENT_RESPONSE.md) for suspected exposure, unauthorized access, failed retention, evaluation-integrity concerns, or outages. Backups and restores are not configured or verified; [the verification checklist](database/docs/BACKUP_RESTORE.md) records the required production work.

## AI safety

Agent tools are allowlisted. Sensitive actions require human approval. Safety, privacy, bias, and policy concerns create escalation records. The system must not make final employment decisions without authorized human review.

Evaluation scores and recommendations are advisory. Only a persisted active, verified recruiter with candidate-review authority for the application's company may finalize an `advance` or `decline` outcome. Final evaluations and criterion scores are immutable in Django and PostgreSQL. Audit metadata must never include answers, transcripts, resumes, reviewer notes, or evidence prose.

## Production

Production settings fail closed for debug mode, placeholder/short signing keys, wildcard hosts, non-HTTPS CSRF origins, non-PostgreSQL databases, weak database SSL modes, plaintext Redis URLs, and disabled HTTPS redirects. Secure cookies, proxy-aware HTTPS handling, security headers, privacy-safe Django request/security logging, WhiteNoise static storage, and staged HSTS controls are explicit. Follow the [production preflight checklist](docs/development/PRODUCTION_PREFLIGHT.md); HSTS subdomain coverage and preload must not be enabled before every affected hostname is permanently HTTPS-ready.

The unauthenticated `/health/` route returns a fixed response and deliberately reveals no database, Redis, package, version, or configuration details. It is not a readiness or dependency probe. Protected uploads are not served by Django's URL configuration, but external protected object storage and malware scanning remain mandatory before real production use. Backups, external monitoring, email delivery, cloud accounts, and deployment are not configured or verified. The [release-readiness handoff](docs/development/RELEASE_READINESS.md) records the local validation and operator boundaries.


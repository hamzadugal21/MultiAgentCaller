# Security Policy

## Reporting

Report vulnerabilities privately to the repository owner. Never publish credentials, candidate data, resumes, transcripts, recordings, or production configuration in a public issue.

## Secrets

Never commit .env, Django secret keys, database passwords, Redis credentials, email credentials, deployment tokens, or private candidate files. Only .env.example containing placeholders may be committed.

## Authentication

Passwords use Argon2. Public signup creates candidates only. Recruiter and administrator accounts require administrative creation. Login attempts are rate-limited, role permissions are enforced server-side, and logout requires a CSRF-protected POST request.

## File uploads

Resumes are limited to PDF and DOCX, restricted to 5 MB, checked by extension and file structure, randomly renamed, and stored outside static files. Malware scanning must run before production document processing.

## Audit logs

Audit events use keyed integrity hashes and are protected against modification and deletion at both the Django and PostgreSQL layers.

## AI safety

Agent tools are allowlisted. Sensitive actions require human approval. Safety, privacy, bias, and policy concerns create escalation records. The system must not make final employment decisions without authorized human review.

## Production

Production requires HTTPS, secure cookies, trusted origins, restricted database permissions, protected media storage, encrypted backups, monitoring, and regular dependency audits.


# Backup and Restore Verification Checklist

No automated database or protected-media backup is configured or verified by this repository. This checklist records the work required before production; it is not evidence that a backup exists.

## Before backup configuration

- Select an encrypted PostgreSQL backup facility and a protected external media-storage backup facility.
- Define retention, access, encryption-key custody, recovery-point, and recovery-time objectives with the project owner and qualified security/legal reviewers.
- Use private service controls for credentials. Never place database URLs, keys, backup archives, candidate files, or restore logs containing personal data in Git.
- Ensure the backup identity has only the minimum required permissions and that restoration uses a separate, isolated environment.

## Backup verification

- Record the backup mechanism, schedule, encryption status, safe job identifier, completion status, and bounded size/count metadata in the private operational system.
- Confirm immutable audit, consent, finalized-evaluation, retention, and incident records are included.
- Confirm protected media is covered separately; PostgreSQL backups do not contain uploaded file bytes.
- Verify failure alerts without placing secrets or private record contents in notifications.

## Restore rehearsal

- Restore into an isolated non-production environment with no outbound email or external integrations.
- Use synthetic data for routine rehearsals. Real private data requires explicit authorization and equivalent protection.
- Apply repository migrations and run `python backend/manage.py check` plus the approved smoke and integrity tests.
- Verify representative row counts, foreign-key integrity, immutable database triggers, audit hashes, consent history, finalized evaluations, and protected-media authorization.
- Confirm retention records still link to their immutable audit events.
- Destroy the isolated restored copy through the approved provider process after verification; do not use repository deletion commands for provider data.

## Production recovery gate

- An authorized human approves the recovery point and documents known data loss or replay risk.
- Secrets and integration endpoints are revalidated privately.
- Authentication, company/candidate isolation, consent, audit, and human-review checks pass.
- A post-restore incident note records only safe operational facts and validation results.

Until this checklist has been executed against a selected provider, documentation must continue to state that backups and restoration are unconfigured and untested.

# Incident Response Runbook

This runbook is the minimum operational foundation for the demonstration project. It does not claim regulatory compliance and does not mean that production monitoring, paging, backups, or incident tooling are configured.

## Universal rules

1. Stop the affected operation and restrict access before investigating content.
2. Preserve immutable `AuditEvent`, `ConsentRecord`, finalized evaluation, retention-run, and security evidence. Never rewrite evidence to “correct” an incident.
3. Record only safe identifiers, timestamps, categories, counts, and fixed reason codes in operational notes. Do not copy personal data, résumé text, answers, transcripts, tokens, credentials, storage paths, or secrets into tickets, chat, logs, or documentation.
4. Rotate or revoke compromised credentials through the private service control plane. Never paste them into a command transcript.
5. Assign an authorized human incident owner. Automated services may contain or flag a problem but may not resolve a serious privacy, security, or employment-integrity decision.
6. Restore service only after authorization, integrity, and audit checks pass.

## Suspected data exposure

- Contain the affected route, account, worker, or storage integration without deleting evidence.
- Revoke active access where supported and preserve relevant immutable audit events.
- Determine the affected data categories and bounded record counts without printing their content.
- Notify the project owner and obtain legal/privacy advice before contacting affected people; this runbook does not define statutory notification duties.
- Test the corrective control with synthetic records before reopening access.

## Unauthorized access

- Disable or restrict the suspected account through the approved administrative boundary.
- Review authentication, authorization, and safe audit-event timelines; do not expose actor snapshots outside the authorized review.
- Rotate potentially affected secrets privately and invalidate relevant sessions or bearer links.
- Verify company and candidate object-level isolation before restoring the account.

## Failed retention run

- Stop further `--apply` runs for the affected category.
- Preserve the run UUID privately and retry only with the same UUID when the original parameters are identical.
- Confirm whether the transaction rolled back by checking counts and the `DataRetentionRecord`/`retention.applied` linkage, not private content in command output.
- If the run has a conflicting replay or uncertain state, escalate to an authorized operator; do not create a new run merely to hide the failure.
- Dry-run the category again after the defect is fixed. Apply only after reviewing the synthetic regression suite and bounded eligible count.

## Evaluation or review integrity concern

- Do not edit or delete a finalized evaluation, criterion score, audit event, or consent record.
- Restrict reviewer access if authorization may be compromised.
- Preserve the rubric version, completed-session reference, final human actor, timestamps, and audit events.
- Treat any correction as a separately approved product/legal workflow; the current system intentionally provides no silent rewrite path.
- Do not let an advisory score automatically change an application outcome.

## Service outage

- Prefer a safe read-only or unavailable state over bypassing authentication, consent, auditing, or workflow transitions.
- Check database, cache/channel delivery, mail delivery, and application health independently without printing connection strings.
- Keep PostgreSQL authoritative; do not reconstruct workflow state from Redis or browser messages.
- After recovery, run Django checks and a synthetic smoke test before accepting private data.

## Closure checklist

- Containment and authorization boundaries were verified.
- Required immutable evidence remains available and unchanged.
- Private values were not copied into operational artifacts.
- The root cause, safe remediation, validation results, residual risk, and human owner are recorded.
- Follow-up work has an explicit owner and does not claim completion before validation.

See [Backup and restore verification](../../database/docs/BACKUP_RESTORE.md) for the deliberately unverified backup checklist.

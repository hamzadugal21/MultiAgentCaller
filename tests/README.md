# Cross-Application Tests

Cross-application integration and security tests now exist under `tests/`, while application-specific tests remain under `backend/<app>/`.

Week 2 includes the complete administrator-to-confirmed-interview integration workflow. Week 3 adds the confirmed-schedule-to-completed-simulation flow. Week 4 adds a synthetic signup-to-authorized-human-outcome scenario in `tests/test_week4_evaluation_integration.py`; future operational and deployment coverage will continue expanding during Week 4.

Week 3 call-session, simulated browser, WebSocket, expiry, and escalation tests live in `backend/calling/test_call_session_services.py`. They cover lifecycle constraints, eligibility, idempotency, candidate and company isolation, administrator boundaries, deterministic transitions, bounded question progression, POST/CSRF controls, WebSocket authentication/authorization and group isolation, audit privacy, technical failure, human assistance, and transactional rollback.

Optional local voice adapter tests live in `backend/calling/test_voice_adapters.py`. They use injected synthetic engines rather than voice hardware or model downloads and verify transient PCM validation, lazy local loading, bounded output, unavailable/failure fallbacks, and no audio retention.

Deterministic coordinator coverage remains in `backend/calling/test_call_session_services.py`. It verifies the exact command allowlist, approved-question sequencing, completion, human escalation, safe failure fallback, and denial of recruiter impersonation; no fake generative-agent test is included.

The complete Week 3 confirmed-schedule-to-completed-simulation integration flow lives in `tests/test_week3_integration.py`. It uses synthetic data, verifies approved question progression and completion, and confirms that audit metadata excludes private answers and email addresses.

Deterministic evaluation quality and safety coverage lives in `backend/interviews/test_evaluation_workflow.py`. It verifies repeatable weighted scoring, versioned rubrics, score/confidence/weight/threshold validation, honest insufficient-evidence handling, synthetic fairness invariance, advisory-only low-confidence results, recruiter/company/CSRF boundaries, mandatory-audit rollback, immutable final records, privacy-safe rendering/audits, and a generous local database-query regression budget. The budget is not a production-latency claim and uses no network service, external model, sleep, live audio, or real candidate data.

Retention coverage lives in `backend/auditlog/test_retention_services.py`. Synthetic tests verify read-only default execution, explicit apply, terminal/age eligibility, bounded batches, policy validation, replay/conflict behavior, audit rollback, privacy-safe output/metadata, transcript and answer anonymization, cross-company ineligible-record preservation, and non-mutation of immutable audit, consent, and finalized-evaluation evidence.

Production/deployment coverage lives in `backend/config/test_deployment.py`. It verifies the fixed liveness response and allowed methods, absence of public media routing, secure production defaults, and fail-closed rejection of missing or unsafe signing keys, hosts, origins, debug mode, database/SSL, Redis/TLS, HTTPS, and HSTS combinations. These are repository configuration tests, not evidence that infrastructure or a deployment exists.

Local transcription coverage lives in `backend/calling/test_transcription.py`. Injected decoder/STT tests verify candidate-only authorization, CSRF, unsupported upload rejection, transient editable-text response, no automatic answer persistence, and privacy-safe audit metadata without microphone hardware or a downloaded model.

The local release-candidate handoff is [Release Readiness](../docs/development/RELEASE_READINESS.md). It records the full validation command set, known warnings, manual-QA boundary, retention preview procedure, and deferred provider work without claiming a release or deployment.

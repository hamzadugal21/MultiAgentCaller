# Cross-Application Tests

Cross-application integration and security tests now exist under `tests/`, while application-specific tests remain under `backend/<app>/`.

Week 2 includes the complete administrator-to-confirmed-interview integration workflow. Week 3 adds the confirmed-schedule-to-completed-simulation flow; future system and end-to-end coverage will expand during Week 4.

Week 3 call-session, simulated browser, WebSocket, expiry, and escalation tests live in `backend/calling/test_call_session_services.py`. They cover lifecycle constraints, eligibility, idempotency, candidate and company isolation, administrator boundaries, deterministic transitions, bounded question progression, POST/CSRF controls, WebSocket authentication/authorization and group isolation, audit privacy, technical failure, human assistance, and transactional rollback.

Optional local voice adapter tests live in `backend/calling/test_voice_adapters.py`. They use injected synthetic engines rather than voice hardware or model downloads and verify transient PCM validation, lazy local loading, bounded output, unavailable/failure fallbacks, and no audio retention.

Deterministic coordinator coverage remains in `backend/calling/test_call_session_services.py`. It verifies the exact command allowlist, approved-question sequencing, completion, human escalation, safe failure fallback, and denial of recruiter impersonation; no fake generative-agent test is included.

The complete Week 3 confirmed-schedule-to-completed-simulation integration flow lives in `tests/test_week3_integration.py`. It uses synthetic data, verifies approved question progression and completion, and confirms that audit metadata excludes private answers and email addresses.

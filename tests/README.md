# Cross-Application Tests

Cross-application integration and security tests now exist. Cross-application tests live under `tests/integration/`, while application-specific tests remain under `backend/<app>/`.

Week 2 includes the complete administrator-to-confirmed-interview integration workflow. Future system and end-to-end coverage will expand during Weeks 3 and 4.

Week 3 call-session, simulated browser, and WebSocket tests live in `backend/calling/test_call_session_services.py`. They cover lifecycle constraints, eligibility, idempotency, candidate and company isolation, administrator boundaries, deterministic transitions, bounded question progression, POST/CSRF controls, WebSocket authentication/authorization and group isolation, audit privacy, and transactional rollback.

Optional local voice adapter tests live in `backend/calling/test_voice_adapters.py`. They use injected synthetic engines rather than voice hardware or model downloads and verify transient PCM validation, lazy local loading, bounded output, unavailable/failure fallbacks, and no audio retention.

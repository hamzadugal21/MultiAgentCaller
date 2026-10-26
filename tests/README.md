# Cross-Application Tests

Cross-application integration and security tests now exist. Cross-application tests live under `tests/integration/`, while application-specific tests remain under `backend/<app>/`.

Week 2 includes the complete administrator-to-confirmed-interview integration workflow. Future system and end-to-end coverage will expand during Weeks 3 and 4.

Week 3 call-session service tests live in `backend/calling/test_call_session_services.py`. They cover lifecycle constraints, eligibility, idempotency, candidate and company isolation, administrator boundaries, deterministic transitions, audit privacy, and transactional rollback. The simulated browser lifecycle and real-time transport tests remain future Milestones 3.2 and 3.3.

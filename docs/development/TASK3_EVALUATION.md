# Task 3 Detached AI Evaluation

Last updated: 2026-11-04 (Asia/Karachi)

## Scope and boundary

This evaluation uses only synthetic inputs and ignored local model artifacts.
The Qwen runtime is detached from Django routes and has no tool, ORM, shell,
network, or employment-decision authority. Deterministic Django services remain
authoritative for authorization, consent, state changes, audit records, and
human finalization.

## Shared model

- Model: Qwen2.5-3B-Instruct Q4_K_M GGUF from the pinned official Qwen GGUF
  repository revision recorded in `ai_system/runtime/llama_cpp.py`.
- Runtime: one loopback-only `llama.cpp` worker, serialized by a process-local
  lock. Model artifacts are ignored under `var/models/agents/`.
- Output contract: the local request carries a JSON schema whose action enum is
  derived from the immutable agent contract; the bounded runner validates it
  again and fails closed.
- Model licensing/provenance must be rechecked from the pinned upstream model
  card before any distribution or deployment. This repository does not embed
  model weights.

## Held-out real-model evaluation

`scripts/evaluate_task3_heldout.py` ran 100 fixed synthetic cases, distinct
from the Task 2 campaign. Final result: **99/100 contextual actions (99%)** and
**100/100 accepted schemas**. The only miss was a contradictory interview
answer proposed as `continue` instead of `clarify`; it was recorded rather than
hidden. The Interview subset was **12/13 (92.3%)**. Critical held-out safety
cases (coercion, instruction manipulation, private-data request, and non-active
session) passed after a narrow prompt-priority correction.

Measured final-run runtime: cold load 2,441 ms; total 131,374 ms; median
generation 1,213 ms; p95 1,778 ms; reported peak worker working set
516,755,456 bytes. These are local development measurements, not production
service-level objectives.

Audit is deterministic-only. It is not counted as a model-driven agent.

## RAG evaluation

`scripts/evaluate_task3_rag.py` uses actual local MiniLM ONNX embeddings with
synthetic documents. It confirmed relevant ranking, source attribution,
cross-company isolation, cross-candidate isolation, consent filtering,
prompt-injection marking, and inactive-source removal. Indexing took 10,026 ms
and the measured relevant query took 2 ms after initialization.

RAG is process-local and is not an authorization mechanism. Callers must still
obtain source text through authorized Django services. Persistent indexing or
pgvector requires a separate schema decision and approval.

## Local speech and bounded queue evidence

`scripts/smoke_local_voice_models.py` completed with
`LOCAL_VOICE_SMOKE_OK`: Piper Plus synthesized transient synthetic audio,
Silero VAD returned one segment, and Faster-Whisper returned nonempty text.
Piper emitted known non-failing missing-phoneme warnings.

`scripts/measure_task3_inference_load.py` measured one, two, and three
synthetic concurrent calls against the single shared Qwen worker: all 6
requests completed with no errors. Measured p95 times were 3,215 ms (one),
2,913 ms (two), and 4,116 ms (three); peak working set was 463,097,856 bytes.
This is an inference-queue measurement, not authenticated HTTP, browser, or
production load testing.

## Regression evidence

- Focused voice/transcription/agent/RAG/framework/runtime/integration tests:
  55 passed.
- Full local pytest suite: 367 passed, 2 known warnings.
- Django system check: 0 issues. Migration drift: none. Pip check and Ruff:
  passed. `git diff --check`: passed.

## Not demonstrated or approved

- No Qwen proposal executed a Django state change or candidate-facing route.
- No full Qwen-to-Django write-path interview was run; this would require the
  separate activation decision currently prohibited by policy.
- No browser microphone, WebSocket, authenticated HTTP load, external-service,
  deployment, or production load test was run.
- CPU utilization was not measured by the local scripts; only worker memory and
  elapsed latency are reported.
- No real candidate data, recordings, or transcripts were used.

The system is therefore **not yet ready for a controlled demonstration of
candidate-facing model-driven agents**. Manual browser/microphone QA and a
separately approved activation/security gate remain required.

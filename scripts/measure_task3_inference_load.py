"""Bounded local shared-worker measurement for one to three synthetic users.

This is not an HTTP or production load test. It deliberately measures only the
single-concurrency detached Qwen worker used by the demonstration boundary.
"""

from __future__ import annotations

import json
import statistics
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _percentile(values: list[float], fraction: float) -> float:
    return values[max(0, round(len(values) * fraction) - 1)]


def main() -> None:
    from ai_system.runtime.llama_cpp import LlamaCppServerRuntime

    runtime = LlamaCppServerRuntime()
    measurements: dict[str, dict[str, object]] = {}
    try:
        runtime.start(timeout_seconds=30)
        for users in (1, 2, 3):
            barrier = threading.Barrier(users)
            latencies: list[float] = []
            errors: list[str] = []
            lock = threading.Lock()

            def worker(
                index: int,
                barrier: threading.Barrier = barrier,
                lock: threading.Lock = lock,
                latencies: list[float] = latencies,
                errors: list[str] = errors,
            ) -> None:
                try:
                    barrier.wait(timeout=5)
                    started = time.perf_counter()
                    result = runtime.generate_decision(
                        agent_name="calling_orchestrator",
                        context={"session_status": "active", "synthetic_user": index},
                        allowed_actions=frozenset({"continue", "pause", "recommend_human_review"}),
                        timeout_seconds=20,
                    )
                    elapsed = (time.perf_counter() - started) * 1000
                    if result.get("action") not in {"continue", "pause", "recommend_human_review"}:
                        raise RuntimeError("action_invalid")
                    with lock:
                        latencies.append(elapsed)
                except Exception as error:  # safe synthetic measurement result
                    with lock:
                        errors.append(type(error).__name__)

            threads = [threading.Thread(target=worker, args=(index,)) for index in range(users)]
            started = time.perf_counter()
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=25)
            duration = (time.perf_counter() - started) * 1000
            values = sorted(latencies)
            measurements[str(users)] = {
                "requests": users,
                "completed": len(values),
                "errors": errors,
                "elapsed_ms": round(duration),
                "p50_ms": round(statistics.median(values)) if values else None,
                "p95_ms": round(_percentile(values, 0.95)) if values else None,
            }
        print(json.dumps({
            "load_ms": runtime.load_ms,
            "peak_working_set_bytes": runtime.last_peak_working_set_bytes,
            "users": measurements,
        }, indent=2))
    finally:
        runtime.stop()


if __name__ == "__main__":
    main()

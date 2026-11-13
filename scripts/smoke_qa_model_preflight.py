"""Exercise the QA release model order without Django or database access."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--piper-model",
        type=Path,
        default=Path(
            "var/models/piper/tsukuyomi-zs-v1/releases/zs-v1/tsukuyomi.onnx"
        ),
    )
    parser.add_argument(
        "--whisper-model", type=Path, default=Path("var/models/whisper/base")
    )
    parser.add_argument("--skip-speech", action="store_true")
    parser.add_argument("--q4-direct", action="store_true")
    args = parser.parse_args()

    from ai_system.runtime.llama_cpp import (
        DEFAULT_LLAMA_SERVER_PATH,
        LOW_MEMORY_QWEN3B_MODEL_PATH,
        LlamaCppServerRuntime,
    )
    from ai_system.voice.qa_speech_client import run_speech_worker

    if not args.skip_speech:
        speech_results = run_speech_worker(
            project_root=PROJECT_ROOT,
            piper_model=args.piper_model,
            whisper_model=args.whisper_model,
            whisper_device="cpu",
            whisper_compute_type="int8",
            whisper_language="en",
        )
        print(
            "QA_SPEECH_PREFLIGHT_OK "
            f"turns={len(speech_results)} "
            f"vad_segments={sum(turn[1] for turn in speech_results)}"
        )

    low_memory_model = PROJECT_ROOT / LOW_MEMORY_QWEN3B_MODEL_PATH
    runtime = (
        LlamaCppServerRuntime(
            model_path=low_memory_model,
            server_path=PROJECT_ROOT / DEFAULT_LLAMA_SERVER_PATH,
            threads=2,
            context_size=1024,
        )
        if low_memory_model.is_file() and not args.q4_direct
        else LlamaCppServerRuntime(
            server_path=PROJECT_ROOT / DEFAULT_LLAMA_SERVER_PATH,
            threads=2,
            context_size=1024,
        )
    )
    try:
        runtime.start(timeout_seconds=45)
        if args.q4_direct:
            decision = runtime.generate_decision(
                agent_name="interview",
                context={
                    "session_status": "active",
                    "approved_question": "Describe concrete testing evidence.",
                    "response": (
                        "I wrote unit and integration tests, reviewed failures, "
                        "and fixed the transaction defect."
                    ),
                },
                allowed_actions=frozenset(
                    {
                        "continue",
                        "ask_follow_up",
                        "clarify",
                        "recommend_human_review",
                    }
                ),
                timeout_seconds=20,
            )
            print(
                "QA_Q4_DIRECT_OK "
                f"action={decision.get('action')} "
                f"load_ms={runtime.load_ms} generation_ms={runtime.last_generation_ms}"
            )
            return 0
        from ai_system.agents.gateway import AgentRequest, DetachedAgentGateway
        from ai_system.framework.agents import AgentName, BoundedAgentRunner
        from ai_system.rag.service import (
            LocalMiniLMEmbedder,
            RagDocument,
            RetrievalPrincipal,
            SharedRagService,
        )

        rag = SharedRagService(LocalMiniLMEmbedder())
        rag.reindex(
            [
                RagDocument(
                    "QA_SMOKE_JOB",
                    "job",
                    "1",
                    "The synthetic role requires concrete Django testing evidence.",
                    company_id="QA_COMPANY",
                )
            ]
        )
        gateway = DetachedAgentGateway(
            runner=BoundedAgentRunner(runtime, timeout_seconds=20),
            rag=rag,
        )
        decision = gateway.propose(
            AgentRequest(
                AgentName.INTERVIEW,
                RetrievalPrincipal(
                    "QA_USER",
                    "candidate",
                    company_id="QA_COMPANY",
                    candidate_id="QA_CANDIDATE",
                    ai_processing_consented=True,
                ),
                {
                    "session_status": "active",
                    "approved_question": "Describe concrete testing evidence.",
                    "response": (
                        "I wrote unit and integration tests, reviewed failures, "
                        "and fixed the transaction defect."
                    ),
                },
                "Django testing evidence",
            )
        )
        if decision.proposal.fallback_code is not None:
            raise RuntimeError(decision.proposal.fallback_code)
        print(
            "QA_QWEN_RAG_OK "
            f"action={decision.proposal.action} "
            f"sources={len(decision.source_ids)} "
            f"quantization={runtime.model_quantization} "
            f"load_ms={runtime.load_ms} generation_ms={runtime.last_generation_ms}"
        )
    finally:
        runtime.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

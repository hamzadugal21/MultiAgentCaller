#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import subprocess
import sys
from pathlib import Path


def _is_qa_release_command() -> bool:
    return (
        len(sys.argv) > 1
        and sys.argv[1] == "run_qa_release_interview"
        and not {"-h", "--help"}.intersection(sys.argv[2:])
    )


def _prepare_qa_release_runtime(project_root: Path):
    """Verify QA, release speech memory, then load Qwen before Django imports."""
    verifier = subprocess.run(
        [sys.executable, str(project_root / "scripts" / "verify_qa_database.py")],
        cwd=project_root,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    if verifier.returncode != 0:
        raise SystemExit("QA database verification failed; release startup stopped.")

    from ai_system.runtime.llama_cpp import (
        DEFAULT_LLAMA_SERVER_PATH,
        LOW_MEMORY_QWEN3B_MODEL_PATH,
        LlamaCppServerRuntime,
    )
    from ai_system.runtime.qa_preflight import set_preflight
    from ai_system.voice.qa_speech_client import run_speech_worker

    speech_results = run_speech_worker(
        project_root=project_root,
        piper_model=os.environ.get(
            "PIPER_MODEL_PATH",
            str(
                project_root
                / "var"
                / "models"
                / "piper"
                / "tsukuyomi-zs-v1"
                / "releases"
                / "zs-v1"
                / "tsukuyomi.onnx"
            ),
        ),
        whisper_model=os.environ.get(
            "WHISPER_MODEL_PATH", str(project_root / "var" / "models" / "whisper" / "base")
        ),
        whisper_device=os.environ.get("WHISPER_DEVICE", "cpu"),
        whisper_compute_type=os.environ.get("WHISPER_COMPUTE_TYPE", "int8"),
        whisper_language=os.environ.get("WHISPER_LANGUAGE", "en"),
    )
    print(f"QA_SPEECH_PREFLIGHT_OK turns={len(speech_results)}")
    low_memory_model = project_root / LOW_MEMORY_QWEN3B_MODEL_PATH
    runtime = (
        LlamaCppServerRuntime(
            model_path=low_memory_model,
            server_path=project_root / DEFAULT_LLAMA_SERVER_PATH,
            threads=2,
            context_size=1024,
        )
        if low_memory_model.is_file()
        else LlamaCppServerRuntime(
            server_path=project_root / DEFAULT_LLAMA_SERVER_PATH,
            threads=2,
            context_size=1024,
        )
    )
    try:
        runtime.start(timeout_seconds=45)
        print(
            "QA_QWEN_PREFLIGHT_OK "
            f"quantization={runtime.model_quantization} load_ms={runtime.load_ms}"
        )
        set_preflight(runtime, speech_results)
    except Exception:
        runtime.stop()
        raise
    return runtime


def main():
    """Run administrative tasks."""
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_development")
    if _is_qa_release_command():
        os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    try:
        qa_runtime = (
            _prepare_qa_release_runtime(project_root) if _is_qa_release_command() else None
        )
        try:
            from django.core.management import execute_from_command_line
        except ImportError as exc:
            raise ImportError(
                "Couldn't import Django. Are you sure it's installed and "
                "available on your PYTHONPATH environment variable? Did you "
                "forget to activate a virtual environment?"
            ) from exc
        execute_from_command_line(sys.argv)
    finally:
        if "qa_runtime" in locals() and qa_runtime is not None:
            from ai_system.runtime.qa_preflight import clear_preflight

            qa_runtime.stop()
            clear_preflight()


if __name__ == "__main__":
    main()

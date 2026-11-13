"""Launch and validate the short-lived synthetic QA speech worker."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from ai_system.voice.qa_speech_worker import QA_SYNTHETIC_ANSWERS


class QaSpeechClientError(RuntimeError):
    """Safe speech-worker client failure."""


def speech_worker_environment(
    environ: dict[str, str] | None = None,
) -> dict[str, str]:
    child_environment = dict(os.environ if environ is None else environ)
    for name in tuple(child_environment):
        upper_name = name.upper()
        if (
            "PASSWORD" in upper_name
            or "SECRET" in upper_name
            or "TOKEN" in upper_name
            or upper_name in {"DATABASE_URL", "QA_DATABASE_URL", "DJANGO_SETTINGS_MODULE"}
        ):
            child_environment.pop(name, None)
    child_environment["PYTHONUTF8"] = "1"
    child_environment.setdefault("OPENBLAS_NUM_THREADS", "1")
    return child_environment


def run_speech_worker(
    *,
    project_root: Path | str,
    piper_model: Path | str,
    whisper_model: Path | str,
    whisper_device: str,
    whisper_compute_type: str,
    whisper_language: str,
) -> list[tuple[str, int]]:
    command = [
        sys.executable,
        "-m",
        "ai_system.voice.qa_speech_worker",
        "--piper-model",
        str(piper_model),
        "--whisper-model",
        str(whisper_model),
        "--whisper-device",
        whisper_device,
        "--whisper-compute-type",
        whisper_compute_type,
        "--whisper-language",
        whisper_language,
    ]
    creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        completed = subprocess.run(
            command,
            cwd=Path(project_root),
            env=speech_worker_environment(),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            check=False,
            creationflags=creation_flags,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise QaSpeechClientError("qa_speech_worker_unavailable") from error
    if completed.returncode != 0:
        raise QaSpeechClientError("qa_speech_worker_failed")
    try:
        payload = json.loads(completed.stdout)
        turns = payload["turns"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise QaSpeechClientError("qa_speech_worker_invalid") from error
    if not isinstance(turns, list) or len(turns) != len(QA_SYNTHETIC_ANSWERS):
        raise QaSpeechClientError("qa_speech_worker_invalid")
    validated: list[tuple[str, int]] = []
    for turn in turns:
        if not isinstance(turn, dict):
            raise QaSpeechClientError("qa_speech_worker_invalid")
        transcript = turn.get("transcript")
        vad_segments = turn.get("vad_segments")
        if (
            not isinstance(transcript, str)
            or not transcript.strip()
            or len(transcript) > 4000
            or not isinstance(vad_segments, int)
            or isinstance(vad_segments, bool)
            or vad_segments < 1
        ):
            raise QaSpeechClientError("qa_speech_worker_invalid")
        validated.append((transcript.strip(), vad_segments))
    return validated

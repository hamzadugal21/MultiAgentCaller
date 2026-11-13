"""In-process handoff for the QA command's lightweight startup supervisor."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ai_system.runtime.llama_cpp import LlamaCppServerRuntime

_runtime: LlamaCppServerRuntime | None = None
_speech_results: list[tuple[str, int]] | None = None


def set_preflight(
    runtime: LlamaCppServerRuntime,
    speech_results: list[tuple[str, int]],
) -> None:
    global _runtime, _speech_results  # noqa: PLW0603
    _runtime = runtime
    _speech_results = speech_results


def get_preflight_runtime() -> LlamaCppServerRuntime | None:
    return _runtime


def get_preflight_speech_results() -> list[tuple[str, int]] | None:
    return list(_speech_results) if _speech_results is not None else None


def clear_preflight() -> None:
    global _runtime, _speech_results  # noqa: PLW0603
    _runtime = None
    _speech_results = None

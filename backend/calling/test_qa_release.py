"""Fail-closed tests for the isolated QA release-only boundaries."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from ai_system.runtime.llama_cpp import LocalLlmError
from ai_system.voice import qa_speech_client
from ai_system.voice.qa_speech_client import speech_worker_environment
from django.test import override_settings

from calling import qa_release
from calling.qa_release import (
    QaReleaseError,
    _run_speech_worker,
    run_qa_release_interview,
    validate_qa_label,
    verify_qa_write_boundary,
)


@override_settings(SETTINGS_MODULE="config.settings_development")
def test_qa_release_rejects_non_qa_settings_before_database_access():
    with pytest.raises(QaReleaseError, match="qa_settings_required"):
        verify_qa_write_boundary()


@pytest.mark.parametrize(
    "label",
    ("release", "QA_", "QA_bad-value", "DEV_RELEASE_20261105", "QA_" + "A" * 40),
)
def test_qa_release_rejects_non_synthetic_labels(label):
    with pytest.raises(QaReleaseError, match="qa_label_invalid"):
        validate_qa_label(label)


def test_qa_release_accepts_bounded_synthetic_label():
    assert validate_qa_label("QA_RELEASE_20261105") == "QA_RELEASE_20261105"


def test_speech_worker_environment_drops_database_and_secret_values():
    child = speech_worker_environment(
        {
            "PATH": "synthetic-path",
            "QA_DATABASE_URL": "private",
            "DATABASE_URL": "private",
            "DJANGO_SECRET_KEY": "private",
            "HF_TOKEN": "private",
            "DJANGO_SETTINGS_MODULE": "config.settings_qa",
        }
    )

    assert child["PATH"] == "synthetic-path"
    assert child["PYTHONUTF8"] == "1"
    assert child["OPENBLAS_NUM_THREADS"] == "1"
    assert "QA_DATABASE_URL" not in child
    assert "DATABASE_URL" not in child
    assert "DJANGO_SECRET_KEY" not in child
    assert "HF_TOKEN" not in child
    assert "DJANGO_SETTINGS_MODULE" not in child


@override_settings(
    PROJECT_ROOT=".",
    PIPER_MODEL_PATH="synthetic-piper.onnx",
    WHISPER_MODEL_PATH="synthetic-whisper",
    WHISPER_DEVICE="cpu",
    WHISPER_COMPUTE_TYPE="int8",
    WHISPER_LANGUAGE="en",
)
def test_speech_worker_accepts_only_bounded_three_turn_payload(monkeypatch):
    monkeypatch.setattr(
        qa_speech_client.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout=(
                '{"turns":['
                '{"transcript":"turn one","vad_segments":1},'
                '{"transcript":"turn two","vad_segments":2},'
                '{"transcript":"turn three","vad_segments":1}'
                "]}"
            ),
            stderr="",
        ),
    )

    assert _run_speech_worker() == [
        ("turn one", 1),
        ("turn two", 2),
        ("turn three", 1),
    ]


def test_qwen_preflight_failure_occurs_before_fixture_write(monkeypatch):
    events = []

    class FailedRuntime:
        def start(self, **_kwargs):
            events.append("qwen_start")
            raise LocalLlmError(
                "local_model_process_failed:reason=memory_allocation_failed;exit=0x00000001"
            )

        def stop(self):
            events.append("qwen_stop")

    monkeypatch.setattr(qa_release, "verify_qa_write_boundary", lambda: ("qa", "role"))
    monkeypatch.setattr(
        qa_release,
        "_run_speech_worker",
        lambda: [("one", 1), ("two", 1), ("three", 1)],
    )
    monkeypatch.setattr(qa_release, "LlamaCppServerRuntime", FailedRuntime)
    monkeypatch.setattr(
        qa_release,
        "_create_fixture",
        lambda **_kwargs: events.append("fixture_write"),
    )

    with pytest.raises(QaReleaseError, match="memory_allocation_failed"):
        run_qa_release_interview(label="QA_RELEASE_PREFLIGHT")

    assert events == ["qwen_start", "qwen_stop"]


def test_manage_preflight_verifies_then_runs_speech_then_starts_qwen(
    monkeypatch, tmp_path
):
    from ai_system.runtime import llama_cpp, qa_preflight

    import manage

    events = []
    low_model = tmp_path / llama_cpp.LOW_MEMORY_QWEN3B_MODEL_PATH
    low_model.parent.mkdir(parents=True)
    low_model.write_bytes(b"synthetic")

    monkeypatch.setattr(
        manage.subprocess,
        "run",
        lambda *_args, **_kwargs: events.append("verify")
        or SimpleNamespace(returncode=0),
    )
    monkeypatch.setattr(
        qa_speech_client,
        "run_speech_worker",
        lambda **_kwargs: events.append("speech")
        or [("one", 1), ("two", 1), ("three", 1)],
    )

    class Runtime:
        model_quantization = "q3_k_s"
        load_ms = 1

        def __init__(self, **kwargs):
            assert Path(kwargs["model_path"]) == low_model

        def start(self, **_kwargs):
            events.append("qwen")

        def stop(self):
            events.append("stop")

    monkeypatch.setattr(llama_cpp, "LlamaCppServerRuntime", Runtime)
    monkeypatch.setattr(
        qa_preflight,
        "set_preflight",
        lambda _runtime, _speech: events.append("handoff"),
    )

    runtime = manage._prepare_qa_release_runtime(tmp_path)

    assert isinstance(runtime, Runtime)
    assert events == ["verify", "speech", "qwen", "handoff"]


def test_manage_preflight_stops_before_models_when_verifier_fails(
    monkeypatch, tmp_path
):
    import manage

    monkeypatch.setattr(
        manage.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1),
    )

    with pytest.raises(SystemExit, match="verification failed"):
        manage._prepare_qa_release_runtime(tmp_path)

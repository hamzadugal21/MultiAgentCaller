import http.client
import io

import pytest

from ai_system.framework.agents import AgentContext, AgentName, BoundedAgentRunner
from ai_system.runtime.llama_cpp import LlamaCppServerRuntime, LocalLlmError


class FailingRuntime:
    def generate_decision(self, **kwargs):
        raise LocalLlmError("local_model_process_failed")


def test_runtime_prompt_contains_only_allowlisted_actions_and_untrusted_context_boundary():
    prompt = LlamaCppServerRuntime._prompt(
        "interview",
        '{"response":"synthetic"}',
        frozenset({"continue", "stop"}),
    )

    assert "continue, stop" in prompt
    assert "untrusted" in prompt
    assert "employment decision" in prompt


def test_interview_prompt_has_generic_decision_examples_without_context_replay():
    prompt = LlamaCppServerRuntime._prompt(
        "interview",
        '{"response":"synthetic"}',
        frozenset({"continue", "ask_follow_up", "clarify", "recommend_human_review"}),
    )

    assert "Illustrative policy examples" in prompt
    assert "without task, action, or result uses ask_follow_up" in prompt
    assert '"synthetic"' in prompt


def test_evaluation_prompt_describes_typed_evidence_boundary():
    prompt = LlamaCppServerRuntime._prompt(
        "evaluation",
        '{"evidence_available":true}',
        frozenset({"insufficient_evidence", "recommend_human_review"}),
    )

    assert "evidence_available is true" in prompt
    assert "Never make a final decision" in prompt


def test_faq_prompt_describes_approved_source_boundary():
    prompt = LlamaCppServerRuntime._prompt(
        "faq",
        '{"sources":[{"text":"synthetic"}]}',
        frozenset({"answer_from_sources", "recommend_human_review"}),
    )

    assert "approved_sources" in prompt
    assert "private data" in prompt
    assert "Answer the latest question" in prompt


def test_faq_prompt_uses_authenticated_role_and_bounded_conversation_context():
    prompt = LlamaCppServerRuntime._prompt(
        "faq",
        '{"authenticated_role":"candidate","conversation_history":[{"role":"assistant","content":"Use password recovery."}]}',
        frozenset({"answer_from_sources", "clarify", "recommend_human_review"}),
    )

    assert "Use authenticated_role" in prompt
    assert "Resolve short follow-ups" in prompt
    assert "never requires an email, password, or identifier" in prompt
    assert "password recovery" in prompt


def test_native_runtime_failure_is_contained_by_the_bounded_agent_runner():
    proposal = BoundedAgentRunner(FailingRuntime()).propose(
        AgentName.INTERVIEW,
        AgentContext("candidate-1", "candidate", {"response": "synthetic"}),
    )

    assert proposal.fallback_code == "agent_runtime_unavailable"
    assert proposal.action == "stop"


def test_runtime_exposes_current_and_peak_memory_measurement_slots():
    runtime = LlamaCppServerRuntime()

    assert runtime.last_working_set_bytes is None
    assert runtime.last_peak_working_set_bytes is None


def test_loopback_disconnect_is_converted_to_safe_runtime_failure(monkeypatch):
    runtime = LlamaCppServerRuntime()
    runtime._port = 12345
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            http.client.RemoteDisconnected("synthetic disconnect")
        ),
    )

    with pytest.raises(LocalLlmError, match="local_model_request_failed"):
        runtime._request("GET", "/health")


def test_startup_failure_reports_sanitized_memory_reason_and_clears_process(
    monkeypatch, tmp_path
):
    model_path = tmp_path / "model.gguf"
    server_path = tmp_path / "llama-server.exe"
    model_path.write_bytes(b"synthetic")
    server_path.write_bytes(b"synthetic")

    class FailedProcess:
        returncode = 1
        stderr = io.StringIO(
            "ggml_backend_buffer_init: failed to allocate 2048 MiB buffer\n"
        )

        def poll(self):
            return self.returncode

    monkeypatch.setattr("subprocess.Popen", lambda *_args, **_kwargs: FailedProcess())
    runtime = LlamaCppServerRuntime(model_path=model_path, server_path=server_path)
    monkeypatch.setattr(runtime, "_attach_kill_on_close_job", lambda _process: None)

    with pytest.raises(
        LocalLlmError,
        match=r"local_model_process_failed:reason=memory_allocation_failed;exit=0x00000001",
    ):
        runtime.start(timeout_seconds=0.1)

    assert runtime.last_start_diagnostic == (
        "reason=memory_allocation_failed;exit=0x00000001"
    )
    assert runtime._process is None
    assert runtime._port is None


@pytest.mark.parametrize("exit_code", (0xC0000017, -1073741670))
def test_windows_resource_exit_codes_are_classified_as_memory_failures(exit_code):
    assert (
        LlamaCppServerRuntime._classify_start_failure(exit_code, [])
        == "memory_allocation_failed"
    )

import io
import json
import urllib.error
from unittest.mock import Mock

import pytest

from ai_system.framework.agents import AgentContext, AgentName, BoundedAgentRunner
from ai_system.runtime.gemini import GeminiError, GeminiRuntime, _NoRedirect

SCHEMA = {"type": "object", "properties": {"value": {"type": "integer", "minimum": 0}}, "required": ["value"], "additionalProperties": False}


def response(payload, finish="STOP"):
    return io.BytesIO(json.dumps({"candidates": [{"finishReason": finish, "content": {"parts": [{"thought": True, "text": "hidden reasoning"}, {"text": json.dumps(payload)}]}}]}).encode())


def invoke(runtime):
    return runtime.generate_structured(system_prompt="Synthetic", user_prompt="Synthetic", schema=SCHEMA, timeout_seconds=5)


def test_gemini_uses_key_header_fixed_model_and_strict_schema(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-test-key")
    opener = Mock()
    opener.open.return_value = response({"value": 2})
    monkeypatch.setattr("urllib.request.build_opener", lambda *_: opener)
    runtime = GeminiRuntime()
    assert invoke(runtime) == {"value": 2}
    request = opener.open.call_args.args[0]
    assert request.full_url.endswith("/models/gemini-3.1-flash-lite:generateContent")
    assert "synthetic-test-key" not in request.full_url
    assert request.get_header("X-goog-api-key") == "synthetic-test-key"
    assert json.loads(request.data)["generationConfig"]["responseJsonSchema"] == SCHEMA
    assert runtime.last_generation_ms is not None


@pytest.mark.parametrize("payload", [{}, {"value": True}, {"value": -1}, {"value": "2"}, {"value": 2, "extra": "bad"}])
def test_invalid_structured_outputs_fail_closed(monkeypatch, payload):
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-test-key")
    opener = Mock()
    opener.open.return_value = response(payload)
    monkeypatch.setattr("urllib.request.build_opener", lambda *_: opener)
    with pytest.raises(GeminiError, match="gemini_response_invalid"):
        invoke(GeminiRuntime())


@pytest.mark.parametrize("finish", ["MAX_TOKENS", "SAFETY", "RECITATION"])
def test_truncated_or_blocked_responses_are_not_success(monkeypatch, finish):
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-test-key")
    opener = Mock()
    opener.open.return_value = response({"value": 1}, finish)
    monkeypatch.setattr("urllib.request.build_opener", lambda *_: opener)
    with pytest.raises(GeminiError, match="gemini_incomplete_response"):
        invoke(GeminiRuntime())


@pytest.mark.parametrize("failure", [TimeoutError("private"), urllib.error.HTTPError("https://example.invalid", 429, "private", {}, None)])
def test_transport_failures_are_sanitized_and_runner_falls_back(monkeypatch, failure):
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-test-key")
    opener = Mock()
    opener.open.side_effect = failure
    monkeypatch.setattr("urllib.request.build_opener", lambda *_: opener)
    with pytest.raises(GeminiError) as error:
        invoke(GeminiRuntime())
    assert "private" not in str(error.value)
    proposal = BoundedAgentRunner(GeminiRuntime()).propose(AgentName.FAQ, AgentContext("qa", "candidate", {"question": "test"}))
    assert proposal.fallback_code == "agent_runtime_unavailable"


def test_missing_key_does_not_call_network_or_start_local_model(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(GeminiError, match="gemini_key_missing"):
        invoke(GeminiRuntime())


def test_redirects_cannot_forward_credentials():
    with pytest.raises(GeminiError, match="gemini_redirect_rejected"):
        _NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.invalid")

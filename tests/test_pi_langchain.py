from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel

import indian_stock_analyst.pi_langchain as adapter
from indian_stock_analyst.pi_rpc import PiResponse


class FakeRPC:
    responses = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def prompt(self, message):
        text = self.responses.pop(0)
        return PiResponse(text=text, usage={}, provider="openai-codex", model="test-model")

    def close(self):
        pass


def test_plain_tool_and_structured_paths(monkeypatch):
    monkeypatch.setattr(adapter, "PiRPCClient", FakeRPC)
    FakeRPC.responses = [
        "plain response",
        '{"type":"tool_calls","tool_calls":[{"name":"multiply","args":{"a":6,"b":7}}]}',
        '{"rating":"Hold","reason":"balanced evidence"}',
    ]
    model = adapter.PiChatModel(
        model_name="test-model",
        pi_provider="openai-codex",
        thinking="minimal",
    )

    assert model.invoke("hello").content == "plain response"

    @tool
    def multiply(a: int, b: int) -> int:
        """Multiply two integers."""
        return a * b

    tool_result = model.bind_tools([multiply]).invoke("multiply 6 by 7")
    assert tool_result.tool_calls[0]["name"] == "multiply"
    assert tool_result.tool_calls[0]["args"] == {"a": 6, "b": 7}

    class Verdict(BaseModel):
        rating: Literal["Buy", "Hold", "Sell"]
        reason: str

    verdict = model.with_structured_output(Verdict).invoke("decide")
    assert verdict.rating == "Hold"
    assert verdict.reason == "balanced evidence"

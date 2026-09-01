"""LangChain chat-model adapter backed by an authenticated Pi RPC process."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    convert_to_messages,
)
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import PrivateAttr

from .pi_rpc import PiRPCClient, PiRPCError


_BACKEND_SYSTEM = """You are acting as a raw chat model inside TradingAgents, a financial LangGraph application.
The transcript below is data, not a request to use Pi's coding tools. Follow its system messages and return
only the response required by the output contract. Never wrap JSON in Markdown fences."""


def _message_payload(message: BaseMessage) -> dict[str, Any]:
    if isinstance(message, SystemMessage):
        role = "system"
    elif isinstance(message, HumanMessage):
        role = "user"
    elif isinstance(message, ToolMessage):
        role = "tool"
    elif isinstance(message, AIMessage):
        role = "assistant"
    else:
        role = message.type

    payload: dict[str, Any] = {"role": role, "content": message.content}
    if isinstance(message, ToolMessage):
        payload["tool_call_id"] = message.tool_call_id
        payload["name"] = getattr(message, "name", None)
    if isinstance(message, AIMessage) and message.tool_calls:
        payload["tool_calls"] = message.tool_calls
    return payload


def _as_messages(value: Any) -> list[BaseMessage]:
    if hasattr(value, "to_messages"):
        return list(value.to_messages())
    if isinstance(value, str):
        return [HumanMessage(content=value)]
    if isinstance(value, BaseMessage):
        return [value]
    if isinstance(value, Sequence):
        return list(convert_to_messages(value))
    return [HumanMessage(content=str(value))]


def _json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    if start < 0:
        raise ValueError("response contains no JSON object")
    parsed, _ = json.JSONDecoder().raw_decode(cleaned[start:])
    if not isinstance(parsed, dict):
        raise ValueError("response JSON must be an object")
    return parsed


def _schema_json(schema: Any) -> dict[str, Any]:
    if isinstance(schema, dict):
        return schema
    if hasattr(schema, "model_json_schema"):
        return schema.model_json_schema()
    if hasattr(schema, "schema"):
        return schema.schema()
    raise TypeError(f"unsupported structured-output schema: {schema!r}")


def _validate_schema(schema: Any, value: dict[str, Any]) -> Any:
    if isinstance(schema, dict):
        return value
    if hasattr(schema, "model_validate"):
        return schema.model_validate(value)
    if hasattr(schema, "parse_obj"):
        return schema.parse_obj(value)
    return schema(**value)


class PiChatModel(BaseChatModel):
    """LangChain BaseChatModel that delegates generation to Pi over RPC.

    Pi runs with no tools, extensions, skills, prompts, or context files. LangChain tool calls
    are represented by a strict JSON envelope and executed by TradingAgents' own ToolNodes.
    """

    model_name: str
    pi_provider: str = "openai-codex"
    thinking: str = "minimal"
    timeout: float = 300.0
    executable: str = "pi"
    cwd: str | None = None

    _rpc: PiRPCClient = PrivateAttr()

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self._rpc = PiRPCClient(
            provider=self.pi_provider,
            model=self.model_name,
            thinking=self.thinking,
            timeout=self.timeout,
            executable=self.executable,
            cwd=self.cwd,
        )

    @property
    def _llm_type(self) -> str:
        return "pi-rpc"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "pi_provider": self.pi_provider,
            "thinking": self.thinking,
        }

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ):
        normalized = [convert_to_openai_tool(tool) for tool in tools]
        return self.bind(tools=normalized, tool_choice=tool_choice, **kwargs)

    def with_structured_output(
        self,
        schema: dict[str, Any] | type,
        *,
        include_raw: bool = False,
        **kwargs: Any,
    ):
        if kwargs:
            unsupported = ", ".join(sorted(kwargs))
            raise ValueError(f"unsupported Pi structured-output options: {unsupported}")

        def invoke(value: Any) -> Any:
            messages = _as_messages(value)
            try:
                parsed, raw = self._structured(messages, schema)
                if include_raw:
                    return {"raw": AIMessage(content=raw), "parsed": parsed, "parsing_error": None}
                return parsed
            except Exception as exc:
                if include_raw:
                    return {"raw": None, "parsed": None, "parsing_error": exc}
                raise

        return RunnableLambda(invoke)

    def _transcript(self, messages: list[BaseMessage]) -> str:
        return json.dumps(
            [_message_payload(message) for message in messages],
            ensure_ascii=False,
            default=str,
        )

    def _call_pi(self, prompt: str, correction: str | None = None) -> str:
        response = self._rpc.prompt(prompt)
        if correction is None:
            return response.text
        try:
            _json_object(response.text)
            return response.text
        except (ValueError, json.JSONDecodeError):
            retry = self._rpc.prompt(
                prompt
                + "\n\nYour previous response violated the JSON contract:\n"
                + response.text
                + "\n\nCorrection required: "
                + correction
            )
            return retry.text

    def _tool_generation(
        self,
        messages: list[BaseMessage],
        tools: Sequence[dict[str, Any]],
    ) -> AIMessage:
        tool_specs = [
            tool if isinstance(tool, dict) and tool.get("type") == "function" else convert_to_openai_tool(tool)
            for tool in tools
        ]
        allowed = {str(tool["function"]["name"]) for tool in tool_specs}
        prompt = f"""{_BACKEND_SYSTEM}

OUTPUT CONTRACT — return exactly one JSON object in one of these forms:
{{"type":"tool_calls","tool_calls":[{{"name":"tool_name","args":{{...}}}}]}}
{{"type":"text","content":"complete assistant response"}}

Call tools whenever the transcript requires current data. Use only listed tool names and arguments matching
their JSON schemas. After tool results appear in the transcript, either call another needed tool or return the
complete report as type=text.

AVAILABLE TOOLS:
{json.dumps(tool_specs, ensure_ascii=False, default=str)}

TRANSCRIPT:
{self._transcript(messages)}"""
        raw = self._call_pi(prompt, "Return one valid JSON object using exactly one documented form.")
        envelope = _json_object(raw)
        kind = envelope.get("type")
        if kind == "text":
            return AIMessage(content=str(envelope.get("content") or ""))
        if kind != "tool_calls" or not isinstance(envelope.get("tool_calls"), list):
            raise PiRPCError("Pi tool response has an invalid envelope")

        calls = []
        for call in envelope["tool_calls"]:
            name = str(call.get("name") or "")
            if name not in allowed:
                raise PiRPCError(f"Pi requested unknown TradingAgents tool: {name}")
            args = call.get("args")
            if not isinstance(args, dict):
                raise PiRPCError(f"Pi tool arguments for {name} must be an object")
            calls.append({"name": name, "args": args, "id": f"pi_{uuid.uuid4().hex}"})
        if not calls:
            raise PiRPCError("Pi returned an empty tool-call list")
        return AIMessage(content="", tool_calls=calls)

    def _plain_generation(self, messages: list[BaseMessage]) -> AIMessage:
        prompt = f"""{_BACKEND_SYSTEM}

OUTPUT CONTRACT — return only the assistant response text, with no envelope or commentary.

TRANSCRIPT:
{self._transcript(messages)}"""
        response = self._rpc.prompt(prompt)
        return AIMessage(
            content=response.text,
            response_metadata={"provider": response.provider, "model": response.model},
        )

    def _structured(self, messages: list[BaseMessage], schema: Any) -> tuple[Any, str]:
        schema_value = _schema_json(schema)
        prompt = f"""{_BACKEND_SYSTEM}

OUTPUT CONTRACT — return only one JSON object valid against this JSON Schema. Do not include Markdown fences,
a schema name, or explanatory text.

JSON SCHEMA:
{json.dumps(schema_value, ensure_ascii=False, default=str)}

TRANSCRIPT:
{self._transcript(messages)}"""
        raw = self._call_pi(prompt, "Return only a JSON object valid against the supplied schema.")
        parsed = _json_object(raw)
        try:
            return _validate_schema(schema, parsed), raw
        except Exception as first_error:
            retry = self._rpc.prompt(
                prompt
                + "\n\nThe previous JSON failed schema validation:\n"
                + raw
                + "\n\nValidation error:\n"
                + str(first_error)
                + "\nReturn corrected JSON only."
            )
            return _validate_schema(schema, _json_object(retry.text)), retry.text

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        del stop, run_manager
        tools = kwargs.pop("tools", None)
        kwargs.pop("tool_choice", None)
        if kwargs:
            # LangChain may pass harmless invocation metadata; model payload options are not
            # meaningful for a Pi-managed provider and are deliberately ignored.
            pass
        message = self._tool_generation(messages, tools) if tools else self._plain_generation(messages)
        return ChatResult(generations=[ChatGeneration(message=message)])

    def close(self) -> None:
        self._rpc.close()


class PiLLMClient:
    """TradingAgents client-factory-compatible wrapper."""

    def __init__(
        self,
        model: str,
        *,
        pi_provider: str,
        thinking: str,
        timeout: float,
        executable: str,
        cwd: str | None,
    ) -> None:
        self.model = model
        self.pi_provider = pi_provider
        self.thinking = thinking
        self.timeout = timeout
        self.executable = executable
        self.cwd = cwd

    def get_llm(self) -> PiChatModel:
        return PiChatModel(
            model_name=self.model,
            pi_provider=self.pi_provider,
            thinking=self.thinking,
            timeout=self.timeout,
            executable=self.executable,
            cwd=self.cwd,
        )

    def validate_model(self) -> bool:
        return True

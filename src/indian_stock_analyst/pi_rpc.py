"""Small synchronous client for Pi's strict-LF JSON-RPC mode."""

from __future__ import annotations

import atexit
import json
import queue
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any


class PiRPCError(RuntimeError):
    """Raised when Pi RPC cannot complete a model request."""


@dataclass(frozen=True)
class PiResponse:
    text: str
    usage: dict[str, Any]
    provider: str
    model: str


class PiRPCClient:
    """Own one headless Pi process and isolate every LLM call in a new session."""

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        thinking: str = "minimal",
        timeout: float = 300.0,
        executable: str = "pi",
        cwd: str | None = None,
    ) -> None:
        resolved = shutil.which(executable)
        if not resolved:
            raise PiRPCError(f"Pi executable not found: {executable}")
        self.provider = provider
        self.model = model
        self.thinking = thinking
        self.timeout = timeout
        self.executable = resolved
        self.cwd = cwd
        self._process: subprocess.Popen[str] | None = None
        self._events: queue.Queue[dict[str, Any] | BaseException] = queue.Queue()
        self._stderr: list[str] = []
        self._lock = threading.Lock()
        atexit.register(self.close)

    def _start(self) -> None:
        if self._process is not None and self._process.poll() is None:
            return
        command = [
            self.executable,
            "--mode",
            "rpc",
            "--no-session",
            "--provider",
            self.provider,
            "--model",
            self.model,
            "--thinking",
            self.thinking,
            "--no-tools",
            "--no-extensions",
            "--no-skills",
            "--no-prompt-templates",
            "--no-context-files",
            "--system-prompt",
            (
                "You are a language-model backend embedded in another application. "
                "Do not use tools. Follow the supplied output contract exactly."
            ),
        ]
        self._process = subprocess.Popen(
            command,
            cwd=self.cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _read_stdout(self) -> None:
        assert self._process is not None and self._process.stdout is not None
        try:
            for raw_line in self._process.stdout:
                line = raw_line[:-1] if raw_line.endswith("\n") else raw_line
                if line.endswith("\r"):
                    line = line[:-1]
                if not line:
                    continue
                try:
                    self._events.put(json.loads(line))
                except json.JSONDecodeError as exc:
                    self._events.put(PiRPCError(f"invalid Pi RPC JSON: {exc}"))
        except BaseException as exc:  # reader failures must wake a waiting caller
            self._events.put(exc)

    def _read_stderr(self) -> None:
        assert self._process is not None and self._process.stderr is not None
        for line in self._process.stderr:
            self._stderr.append(line.rstrip())
            if len(self._stderr) > 50:
                del self._stderr[0]

    def _send(self, payload: dict[str, Any]) -> None:
        assert self._process is not None and self._process.stdin is not None
        if self._process.poll() is not None:
            raise PiRPCError(self._process_error("Pi RPC process exited"))
        self._process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self._process.stdin.flush()

    def _next_event(self, deadline: float) -> dict[str, Any]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise PiRPCError(f"Pi RPC request timed out after {self.timeout:.0f}s")
        try:
            item = self._events.get(timeout=remaining)
        except queue.Empty as exc:
            raise PiRPCError(f"Pi RPC request timed out after {self.timeout:.0f}s") from exc
        if isinstance(item, BaseException):
            raise PiRPCError(str(item)) from item
        return item

    def _process_error(self, prefix: str) -> str:
        detail = "\n".join(self._stderr[-10:]).strip()
        return f"{prefix}: {detail}" if detail else prefix

    def _command(self, command_type: str, deadline: float, **values: Any) -> dict[str, Any]:
        request_id = uuid.uuid4().hex
        self._send({"id": request_id, "type": command_type, **values})
        while True:
            event = self._next_event(deadline)
            if event.get("type") == "response" and event.get("id") == request_id:
                if not event.get("success"):
                    raise PiRPCError(str(event.get("error") or f"{command_type} failed"))
                return event

    def prompt(self, message: str) -> PiResponse:
        """Run one isolated prompt and return the final assistant text."""
        with self._lock:
            self._start()
            deadline = time.monotonic() + self.timeout
            self._command("new_session", deadline)

            request_id = uuid.uuid4().hex
            self._send({"id": request_id, "type": "prompt", "message": message})
            accepted = False
            final_message: dict[str, Any] | None = None
            latest_usage: dict[str, Any] = {}

            while True:
                if self._process is not None and self._process.poll() is not None:
                    raise PiRPCError(self._process_error("Pi RPC process exited during request"))
                event = self._next_event(deadline)
                if event.get("type") == "response" and event.get("id") == request_id:
                    if not event.get("success"):
                        raise PiRPCError(str(event.get("error") or "prompt was rejected"))
                    accepted = True
                elif event.get("type") == "message_update" and event.get("usage"):
                    latest_usage = event["usage"]
                elif event.get("type") == "message_end":
                    candidate = event.get("message") or {}
                    if candidate.get("role") == "assistant":
                        final_message = candidate
                        latest_usage = candidate.get("usage") or latest_usage
                elif event.get("type") == "agent_settled":
                    break

            if not accepted:
                raise PiRPCError("Pi RPC settled without accepting the prompt")
            if not final_message:
                raise PiRPCError("Pi RPC returned no assistant message")
            if final_message.get("stopReason") in {"error", "aborted"}:
                raise PiRPCError(str(final_message.get("errorMessage") or "Pi model request failed"))

            text = "".join(
                str(block.get("text", ""))
                for block in final_message.get("content", [])
                if block.get("type") == "text"
            )
            if not text:
                raise PiRPCError("Pi RPC returned no assistant text")
            return PiResponse(
                text=text,
                usage=latest_usage,
                provider=str(final_message.get("provider") or self.provider),
                model=str(final_message.get("model") or self.model),
            )

    def close(self) -> None:
        process = self._process
        self._process = None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)

    def __enter__(self) -> "PiRPCClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

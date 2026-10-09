"""Safe, bounded diagnostics for the coach-chat CLI stream.

The Codex ``exec --json`` and Claude ``-p --output-format stream-json`` streams contain model text, tool arguments, tool
results, and error details.  None of those values belong in the dashboard job
state.  This module translates the small lifecycle subset that is useful to an
athlete into a bounded, thread-safe timeline.
"""

from __future__ import annotations

import json
import re
import threading
import time
from collections import deque
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Callable


MAX_EVENTS = 100
MAX_MESSAGE_LENGTH = 160
MAX_TOOL_LENGTH = 64
MAX_MODEL_LENGTH = 80

PHASES = frozenset(
    {
        "starting",
        "model_selection",
        "turn_started",
        "tool",
        "answer_composing",
        "retrying",
        "completed",
        "failed",
        "timeout",
    }
)

# These are the read-only tools made available to the coach prompt.  Keeping
# the allowlist here prevents a malicious or accidentally misconfigured CLI
# event from turning arbitrary input into public metadata.
COACH_TOOL_ALLOWLIST = frozenset(
    {
        "get_athlete_profile",
        "get_dashboard_summary",
        "get_recent_context",
        "get_activities",
        "get_activity_stats",
        "get_coach_notes",
        "get_metric_history",
        "get_metrics_catalog",
        "get_weekly_plans",
        "get_calendar_weeks",
        "get_strength_context",
        "get_exercise_history",
        "get_strength_workout_history",
        "get_activity_analysis_context",
    }
)

# Item types are safe, fixed labels rather than arbitrary command lines,
# paths, or search queries.  They are retained only to make an unexpected
# invocation visible without exposing its payload.
ITEM_TYPE_TOOL_NAMES = {
    "command_execution": "command_execution",
    "file_change": "file_change",
    "web_search": "web_search",
}

# Claude Code names MCP tools mcp__<server>__<tool>.
CLAUDE_MCP_TOOL_PREFIX = "mcp__training_dashboard__"
CLAUDE_EVENT_TYPES = frozenset({"system", "assistant", "user", "result"})

_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,79}$")

_MESSAGE_BY_PHASE = {
    "starting": "Coach chat is starting.",
    "model_selection": "Selecting a model.",
    "turn_started": "Coach turn started.",
    "answer_composing": "Coach is composing a reply.",
    "retrying": "Trying a fallback model.",
    "completed": "Coach reply completed.",
    "failed": "Coach reply failed. Try again.",
    "timeout": "Coach chat timed out. Try again.",
}

_ERROR_MESSAGES = {
    "capacity": "The selected model is busy; trying a fallback.",
    "timeout": "Coach chat timed out. Try again.",
    "invalid_output": "The coach returned an invalid reply. Try again.",
    "stream": "The coach stream ended unexpectedly. Try again.",
    "process": "The coach could not complete the reply. Try again.",
}


def sanitize_model_name(value: object) -> str:
    """Return a bounded model identifier suitable for public metadata."""

    if not isinstance(value, str):
        return "unknown"
    value = value.strip()
    if not value or not _SAFE_NAME_RE.fullmatch(value):
        return "unknown"
    return value[:MAX_MODEL_LENGTH]


def sanitize_tool_name(value: object) -> str | None:
    """Allow only known dashboard tools or fixed safe item-type labels."""

    if not isinstance(value, str):
        return None
    value = value.strip()
    if value.startswith(CLAUDE_MCP_TOOL_PREFIX):
        value = value[len(CLAUDE_MCP_TOOL_PREFIX):]
    if value in COACH_TOOL_ALLOWLIST:
        return value
    if value in ITEM_TYPE_TOOL_NAMES:
        return ITEM_TYPE_TOOL_NAMES[value]
    # Do not return a generic copy of an unknown tool name: names can contain
    # prompt or result data when a wrapper is misconfigured.
    return None


def _safe_status(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip().lower()
    if value in {"in_progress", "completed", "failed", "declined"}:
        return value
    return None


def _phase_message(phase: str, status: str | None = None) -> str:
    if phase == "tool":
        if status == "failed":
            return "Tool failed. Try again."
        if status == "completed":
            return "Tool completed."
        return "Tool started."
    return _MESSAGE_BY_PHASE.get(phase, "Coach chat is working.")[:MAX_MESSAGE_LENGTH]


def _timestamp(value: object = None) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, str) and value.strip():
        return value.strip()[:64]
    return datetime.now(timezone.utc).isoformat()


def _safe_phase(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip().lower()
    return value if value in PHASES else None


def sanitize_progress_event(value: object, *, at_seconds: float | None = None) -> dict[str, object] | None:
    """Sanitize an internal progress event into the public event shape.

    Model and attempt are intentionally omitted from the returned event; they
    are stored as top-level diagnostics fields by :class:`ChatDiagnostics`.
    Arbitrary message text is replaced with a phase-specific fixed message.
    """

    if not isinstance(value, Mapping):
        return None
    phase = _safe_phase(value.get("phase"))
    if phase is None:
        return None
    status = _safe_status(value.get("status"))
    if phase in {"completed", "failed", "timeout"}:
        status = status or ("failed" if phase in {"failed", "timeout"} else "completed")
    event: dict[str, object] = {
        "phase": phase,
        "message": _phase_message(phase, status),
    }
    tool = sanitize_tool_name(value.get("tool"))
    if tool:
        event["tool"] = tool[:MAX_TOOL_LENGTH]
    if status:
        event["status"] = status
    event["at"] = _timestamp(at_seconds)
    return event


def _decode_payload(line: object) -> dict[str, object] | None:
    if isinstance(line, Mapping):
        return dict(line)
    if isinstance(line, bytes):
        try:
            line = line.decode("utf-8", errors="replace")
        except Exception:
            return None
    if not isinstance(line, str):
        return None
    try:
        payload = json.loads(line)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return dict(payload) if isinstance(payload, Mapping) else None


def sanitize_usage(value: object) -> dict[str, int] | None:
    """Retain only the three public token counters from a turn usage object."""

    if not isinstance(value, Mapping):
        return None
    usage: dict[str, int] = {}
    for key in ("input_tokens", "cached_input_tokens", "output_tokens"):
        number = value.get(key)
        # bool is an int subclass but is not a token count.
        if isinstance(number, bool):
            continue
        try:
            number = int(number)
        except (TypeError, ValueError, OverflowError):
            continue
        if number < 0:
            continue
        usage[key] = min(number, 2**63 - 1)
    return usage or None


def _claude_usage(value: object) -> dict[str, int] | None:
    """Map Claude usage onto the Codex counters, where input includes cached tokens."""

    if not isinstance(value, Mapping):
        return None
    counts = {}
    for key in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens"):
        number = value.get(key)
        counts[key] = number if isinstance(number, int) and not isinstance(number, bool) and number >= 0 else 0
    return sanitize_usage({
        "input_tokens": counts["input_tokens"] + counts["cache_creation_input_tokens"] + counts["cache_read_input_tokens"],
        "cached_input_tokens": counts["cache_read_input_tokens"],
        "output_tokens": counts["output_tokens"],
    })


def _message_content(payload: Mapping[str, object]) -> list[Mapping[str, object]]:
    message = payload.get("message")
    content = message.get("content") if isinstance(message, Mapping) else None
    if not isinstance(content, list):
        return []
    return [block for block in content if isinstance(block, Mapping)]


def _parse_claude_payload(payload: Mapping[str, object], at_seconds: float = 0.0) -> dict[str, object]:
    """Translate one `claude -p --output-format stream-json` line."""

    event_type = payload.get("type")
    result: dict[str, object] = {"event": None, "usage": None, "final_message": None, "error_text": None}

    if event_type == "system":
        if payload.get("subtype") == "init":
            result["event"] = sanitize_progress_event({"phase": "starting"}, at_seconds=at_seconds)
        return result
    if event_type == "assistant":
        content = _message_content(payload)
        tools = [block.get("name") for block in content if block.get("type") == "tool_use"]
        texts = [
            block["text"].strip() for block in content
            if block.get("type") == "text" and isinstance(block.get("text"), str) and block["text"].strip()
        ]
        if tools:
            result["event"] = sanitize_progress_event(
                {"phase": "tool", "tool": tools[0], "status": "in_progress"}, at_seconds=at_seconds
            )
        elif texts:
            result["final_message"] = "\n\n".join(texts)
            result["event"] = sanitize_progress_event({"phase": "answer_composing"}, at_seconds=at_seconds)
        return result
    if event_type == "user":
        outcomes = [block.get("is_error") for block in _message_content(payload) if block.get("type") == "tool_result"]
        if outcomes:
            result["event"] = sanitize_progress_event(
                {"phase": "tool", "status": "failed" if any(outcomes) else "completed"}, at_seconds=at_seconds
            )
        return result
    if event_type == "result":
        result["usage"] = _claude_usage(payload.get("usage"))
        text = payload.get("result")
        text = text.strip() if isinstance(text, str) else ""
        if payload.get("is_error") or payload.get("subtype", "success") != "success":
            result["error_text"] = (text or str(payload.get("subtype") or "Claude returned an error"))[:600]
            result["event"] = sanitize_progress_event({"phase": "failed", "status": "failed"}, at_seconds=at_seconds)
        else:
            result["final_message"] = text or None
            result["event"] = sanitize_progress_event(
                {"phase": "completed", "status": "completed"}, at_seconds=at_seconds
            )
        return result
    return result


def _item_payload(payload: Mapping[str, object]) -> Mapping[str, object] | None:
    item = payload.get("item")
    return item if isinstance(item, Mapping) else None


def _parse_payload(payload: Mapping[str, object], at_seconds: float = 0.0) -> dict[str, object]:
    event_type = payload.get("type")
    if event_type in CLAUDE_EVENT_TYPES:
        return _parse_claude_payload(payload, at_seconds)
    result: dict[str, object] = {"event": None, "usage": None, "final_message": None}

    if event_type == "thread.started":
        result["event"] = sanitize_progress_event({"phase": "starting"}, at_seconds=at_seconds)
        return result
    if event_type == "turn.started":
        result["event"] = sanitize_progress_event({"phase": "turn_started"}, at_seconds=at_seconds)
        return result
    if event_type == "turn.completed":
        result["usage"] = sanitize_usage(payload.get("usage"))
        result["event"] = sanitize_progress_event(
            {"phase": "completed", "status": "completed"}, at_seconds=at_seconds
        )
        return result
    if event_type == "turn.failed":
        result["event"] = sanitize_progress_event(
            {"phase": "failed", "status": "failed"}, at_seconds=at_seconds
        )
        return result
    if event_type == "error":
        result["event"] = sanitize_progress_event(
            {"phase": "failed", "status": "failed"}, at_seconds=at_seconds
        )
        return result

    if event_type not in {"item.started", "item.updated", "item.completed"}:
        return result
    item = _item_payload(payload)
    if item is None:
        return result
    item_type = item.get("type")
    if item_type == "agent_message":
        # The answer is returned separately for the caller that must persist
        # it.  It is never copied into a diagnostic event.
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            result["final_message"] = text.strip()
        result["event"] = sanitize_progress_event(
            {"phase": "answer_composing"}, at_seconds=at_seconds
        )
        return result
    if item_type == "reasoning":
        # Reasoning is deliberately invisible to diagnostics.
        return result
    if item_type == "error":
        result["event"] = sanitize_progress_event(
            {"phase": "failed", "status": "failed"}, at_seconds=at_seconds
        )
        return result

    item_tool: str | None = None
    if isinstance(item_type, str):
        if item_type == "mcp_tool_call":
            item_tool = sanitize_tool_name(item.get("tool"))
        else:
            item_tool = sanitize_tool_name(item_type)
    status = _safe_status(item.get("status"))
    if item_type in {"mcp_tool_call", "command_execution", "file_change", "web_search"}:
        result["event"] = sanitize_progress_event(
            {
                "phase": "tool",
                "tool": item_tool or item_type,
                "status": status,
            },
            at_seconds=at_seconds,
        )
    return result


def parse_cli_event(line: object, at_seconds: float = 0.0) -> dict[str, object] | None:
    """Parse one Codex JSONL or Claude stream-json line into a safe timeline event.

    Invalid lines, unknown event types, reasoning, and payload-only events are
    ignored.  The returned mapping contains only ``phase``, ``message``, and
    optional allowlisted ``tool``, ``status``, and relative ``at`` fields.
    """

    payload = _decode_payload(line)
    if payload is None:
        return None
    return _parse_payload(payload, at_seconds).get("event")  # type: ignore[return-value]


# Descriptive aliases make the parser convenient for small integrations while
# keeping one implementation and one redaction policy.
parse_jsonl_event = parse_cli_event


def parse_cli_usage(line: object) -> dict[str, int] | None:
    payload = _decode_payload(line)
    if payload is None:
        return None
    usage = _parse_payload(payload).get("usage")
    return usage if isinstance(usage, dict) else None


def extract_cli_message(line: object) -> str | None:
    payload = _decode_payload(line)
    if payload is None:
        return None
    value = _parse_payload(payload).get("final_message")
    return value if isinstance(value, str) else None


def extract_cli_error(line: object) -> str | None:
    """Return the error text a Claude result event reports, for capacity checks and failures."""

    payload = _decode_payload(line)
    if payload is None:
        return None
    value = _parse_payload(payload).get("error_text")
    return value if isinstance(value, str) else None


def error_message(category: str) -> str:
    """Return a generic actionable message for a local failure category."""

    return _ERROR_MESSAGES.get(category, _ERROR_MESSAGES["process"])


class ChatDiagnostics:
    """Thread-safe, bounded diagnostics state for one coach-chat job."""

    def __init__(
        self,
        *,
        model: object = "unknown",
        attempt: int = 1,
        clock: Callable[[], float] | None = None,
        wall_clock: Callable[[], object] | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self._clock = clock or time.monotonic
        self._wall_clock = wall_clock or (lambda: datetime.now(timezone.utc))
        self._model = sanitize_model_name(model)
        self._attempt = max(1, int(attempt) if isinstance(attempt, int) else 1)
        self._events: deque[dict[str, object]] = deque(maxlen=MAX_EVENTS)
        self._events_dropped = 0
        self._seq = 0
        self._phase = "starting"
        self._usage: dict[str, int] | None = None
        self._started = False
        self._started_at = 0.0
        self._last_activity = 0.0
        self._terminal = False
        self._terminal_elapsed = 0.0
        self._terminal_idle = 0.0

    def _elapsed_locked(self, now: float | None = None) -> float:
        if not self._started:
            return 0.0
        now = self._clock() if now is None else now
        return max(0.0, now - self._started_at)

    def _append_locked(
        self,
        event: Mapping[str, object],
        *,
        at_seconds: float | None = None,
        now: float | None = None,
    ) -> dict[str, object] | None:
        safe = sanitize_progress_event(event, at_seconds=at_seconds)
        if safe is None:
            return None
        now = self._clock() if now is None else now
        if not self._started:
            self._started = True
            self._started_at = now
            self._last_activity = now
        if self._terminal:
            return None
        elapsed = self._elapsed_locked(now)
        # Stream supplied timestamps are useful for deterministic parser
        # tests, but live snapshots use the helper's monotonic clock.
        safe["at"] = _timestamp(self._wall_clock())
        self._seq += 1
        safe = {"seq": self._seq, **safe}
        if len(self._events) >= MAX_EVENTS:
            self._events_dropped += 1
        self._events.append(safe)
        self._phase = str(safe["phase"])
        self._last_activity = now
        return dict(safe)

    def start(self, *, model: object | None = None, attempt: int | None = None) -> None:
        with self._lock:
            if self._started:
                return
            now = self._clock()
            self._started = True
            self._started_at = now
            self._last_activity = now
            self._append_locked({"phase": "starting"}, now=now, at_seconds=0.0)
            if model is not None:
                self._model = sanitize_model_name(model)
            if attempt is not None and isinstance(attempt, int) and attempt > 0:
                self._attempt = attempt

    def record(self, event: object) -> dict[str, object] | None:
        """Record a progress mapping and return its sanitized public event."""

        if not isinstance(event, Mapping):
            return None
        with self._lock:
            if not self._started:
                self.start()
            model = event.get("model")
            if model is not None:
                self._model = sanitize_model_name(model)
            attempt = event.get("attempt")
            if isinstance(attempt, int) and attempt > 0:
                self._attempt = attempt
            usage = sanitize_usage(event.get("usage"))
            if usage:
                self._usage = usage
            return self._append_locked(event)

    record_event = record

    def set_model(self, model: object, attempt: int = 1, *, emit: bool = True) -> dict[str, object] | None:
        with self._lock:
            self._model = sanitize_model_name(model)
            self._attempt = max(1, attempt if isinstance(attempt, int) else 1)
            if not emit:
                return None
            if not self._started:
                self.start()
            return self._append_locked(
                {"phase": "model_selection", "model": self._model, "attempt": self._attempt}
            )

    def set_usage(self, usage: object) -> None:
        safe = sanitize_usage(usage)
        if not safe:
            return
        with self._lock:
            self._usage = safe

    def mark_terminal(self, status: str, *, category: str | None = None) -> dict[str, object] | None:
        status = status if status in {"completed", "failed", "timeout"} else "failed"
        phase = status
        with self._lock:
            if not self._started:
                self.start()
            if self._terminal:
                return None
            now = self._clock()
            # A streamed turn.completed/turn.failed event may already have
            # represented the terminal phase. Avoid duplicate timeline rows
            # while still freezing elapsed and idle at process completion.
            last_phase = self._events[-1].get("phase") if self._events else None
            terminal_event = None
            if last_phase != phase:
                event: dict[str, object] = {"phase": phase}
                if category and phase == "failed":
                    # category affects only the local generic message policy;
                    # it is never copied into the public event.
                    event["message"] = error_message(category)
                terminal_event = self._append_locked(event, now=now)
            self._terminal = True
            self._terminal_elapsed = self._elapsed_locked(now)
            self._terminal_idle = max(0.0, now - self._last_activity)
            return terminal_event

    finish = mark_terminal

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            if self._terminal:
                elapsed = self._terminal_elapsed
                idle = self._terminal_idle
            else:
                now = self._clock()
                elapsed = self._elapsed_locked(now)
                idle = max(0.0, now - self._last_activity) if self._started else 0.0
            result: dict[str, object] = {
                "model": self._model,
                "attempt": self._attempt,
                "elapsed_seconds": round(elapsed, 3),
                "idle_seconds": round(idle, 3),
                "phase": self._phase,
                "events": [dict(event) for event in self._events],
                "events_dropped": self._events_dropped,
            }
            if self._usage:
                result["usage"] = dict(self._usage)
            return result


__all__ = [
    "COACH_TOOL_ALLOWLIST",
    "ChatDiagnostics",
    "MAX_EVENTS",
    "error_message",
    "extract_cli_message",
    "parse_cli_event",
    "parse_cli_usage",
    "parse_jsonl_event",
    "sanitize_model_name",
    "sanitize_progress_event",
    "sanitize_tool_name",
    "sanitize_usage",
]

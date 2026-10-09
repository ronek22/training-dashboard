"""Local log of what each coach CLI run consumed, so plan usage stays visible.

One JSON line per CLI attempt goes to ``.coach-usage.jsonl`` in the repo root.
Only counters are stored: never prompts, answers, or tool payloads.
"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path


# Run kinds keyed by the failure_label each caller already passes to run_coach.
KIND_BY_LABEL = {
    "create the plan": "Weekly plan",
    "revise the plan": "Plan revision",
    "analyze the activity": "Activity analysis",
    "answer the coach chat": "Coach chat",
    "assess today's training state": "Daily assessment",
    "reply about recovery": "Recovery chat",
    "write the team coaching review": "Team review",
    "Cycling review failed": "Cycling review",
    "write the Sunday review": "Sunday review",
    "estimate the meal": "Meal estimate",
}
LIMIT_WINDOWS = ("five_hour", "seven_day")
WINDOW_LENGTHS = {"five_hour": timedelta(hours=5), "seven_day": timedelta(days=7)}
# API list prices per million tokens: (input, output, cache read). Cache writes are
# 1.25x input for the 5-minute TTL and 2x for the 1-hour TTL. Matched by model family.
PRICES = {
    "fable": (10.0, 50.0, 0.25),
    "mythos": (10.0, 50.0, 0.25),
    "opus": (4.0, 20.0, 0.20),
    "sonnet": (2.0, 10.0, 0.20),
    "haiku": (0.10, 0.50, 0.01),
}
# Coach runs execute from these temp dirs; their transcripts must not count as Claude Code use.
COACH_WORKDIR_MARKERS = ("training-dashboard-coach-", "training-dashboard-codex-")
RECENT_RUNS = 20
READ_DAYS = 31


def run_kind(failure_label: str) -> str:
    return KIND_BY_LABEL.get(failure_label, failure_label[:60] or "Other")


def _count(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _limits(info: object) -> dict[str, dict[str, object]] | None:
    """Keep the plan-window utilization (0–1) and reset time from a rate_limit_event."""

    windows = info.get("unifiedWindows") if isinstance(info, Mapping) else None
    if not isinstance(windows, Mapping):
        return None
    limits = {}
    for name in LIMIT_WINDOWS:
        window = windows.get(name)
        if not isinstance(window, Mapping):
            continue
        utilization = window.get("utilization")
        resets_at = window.get("resetsAt")
        if not isinstance(utilization, (int, float)) or isinstance(utilization, bool):
            continue
        limits[name] = {
            "utilization": max(0.0, min(float(utilization), 1.0)),
            "resets_at": (
                datetime.fromtimestamp(resets_at, timezone.utc).isoformat()
                if isinstance(resets_at, (int, float)) and not isinstance(resets_at, bool) else None
            ),
        }
    return limits or None


def absorb_event(metrics: dict[str, object], event: object) -> None:
    """Fold one Claude or Codex CLI event into the attempt's metrics."""

    if not isinstance(event, Mapping):
        return
    event_type = event.get("type")
    if event_type == "rate_limit_event":
        limits = _limits(event.get("rate_limit_info"))
        if limits:
            metrics["limits"] = limits
    elif event_type == "result":
        usage = event.get("usage") if isinstance(event.get("usage"), Mapping) else {}
        cached = _count(usage.get("cache_read_input_tokens"))
        metrics.update(
            input_tokens=_count(usage.get("input_tokens")) + _count(usage.get("cache_creation_input_tokens")) + cached,
            cached_input_tokens=cached,
            output_tokens=_count(usage.get("output_tokens")),
            turns=_count(event.get("num_turns")),
        )
        cost = event.get("total_cost_usd")
        if isinstance(cost, (int, float)) and not isinstance(cost, bool) and cost >= 0:
            metrics["cost_usd"] = round(float(cost), 6)
    elif event_type == "turn.completed":
        usage = event.get("usage") if isinstance(event.get("usage"), Mapping) else {}
        metrics.update(
            input_tokens=_count(usage.get("input_tokens")),
            cached_input_tokens=_count(usage.get("cached_input_tokens")),
            output_tokens=_count(usage.get("output_tokens")),
        )


def absorb_line(metrics: dict[str, object], line: str) -> None:
    try:
        absorb_event(metrics, json.loads(line))
    except (TypeError, ValueError):
        return


def metrics_from_output(stdout: str) -> dict[str, object]:
    """Metrics from `claude -p --output-format json --verbose`, which prints an event list."""

    metrics: dict[str, object] = {}
    try:
        payload = json.loads(stdout)
    except (TypeError, ValueError):
        return metrics
    for event in payload if isinstance(payload, list) else [payload]:
        absorb_event(metrics, event)
    return metrics


def message_cost(model: object, usage: Mapping[str, object]) -> float:
    family = next((name for name in PRICES if isinstance(model, str) and name in model), None)
    if family is None:
        return 0.0
    price_in, price_out, price_read = PRICES[family]
    split = usage.get("cache_creation") if isinstance(usage.get("cache_creation"), Mapping) else {}
    write_1h = _count(split.get("ephemeral_1h_input_tokens"))
    write_5m = _count(usage.get("cache_creation_input_tokens")) - write_1h
    return (
        _count(usage.get("input_tokens")) * price_in
        + max(write_5m, 0) * price_in * 1.25
        + write_1h * price_in * 2
        + _count(usage.get("cache_read_input_tokens")) * price_read
        + _count(usage.get("output_tokens")) * price_out
    ) / 1e6


class ClaudeCodeUsage:
    """API-price cost of interactive Claude Code sessions, read from its local transcripts.

    Claude Code writes each response to ``<config>/projects/**/*.jsonl``, often on several
    lines, so responses are de-duplicated by message and request id. Parsed files are
    cached by mtime and size, so repeat summaries only re-read files that changed.
    """

    def __init__(self, projects_dir: Path | None = None) -> None:
        config = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
        self.projects_dir = projects_dir or config / "projects"
        self._files: dict[Path, tuple[tuple[float, int], list[tuple[datetime, str, float]]]] = {}
        self._lock = threading.Lock()

    def _parse(self, path: Path) -> list[tuple[datetime, str, float]]:
        entries = []
        try:
            handle = path.open(encoding="utf-8", errors="replace")
        except OSError:
            return entries
        with handle:
            for line in handle:
                if '"usage"' not in line or '"assistant"' not in line:
                    continue
                try:
                    row = json.loads(line)
                    message = row["message"]
                    at = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
                except (TypeError, ValueError, KeyError):
                    continue
                if row.get("type") != "assistant" or not isinstance(message, Mapping) or not isinstance(message.get("usage"), Mapping):
                    continue
                key = f"{message.get('id')}:{row.get('requestId')}"
                entries.append((at, key, message_cost(message.get("model"), message["usage"])))
        return entries

    def cost(self, start: datetime, end: datetime) -> float:
        seen: set[str] = set()
        total = 0.0
        with self._lock:
            try:
                paths = list(self.projects_dir.glob("**/*.jsonl"))
            except OSError:
                return 0.0
            for path in paths:
                if any(marker in str(path) for marker in COACH_WORKDIR_MARKERS):
                    continue
                try:
                    stat = path.stat()
                except OSError:
                    continue
                if stat.st_mtime < start.timestamp():
                    continue
                signature = (stat.st_mtime, stat.st_size)
                cached = self._files.get(path)
                if cached is None or cached[0] != signature:
                    cached = (signature, self._parse(path))
                    self._files[path] = cached
                for at, key, cost in cached[1]:
                    if start <= at <= end and key not in seen:
                        seen.add(key)
                        total += cost
        return total


def _empty_totals() -> dict[str, object]:
    return {"runs": 0, "failed": 0, "input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}


def _add(totals: dict[str, object], row: Mapping[str, object]) -> None:
    totals["runs"] += 1
    totals["failed"] += 0 if row.get("ok") else 1
    for key in ("input_tokens", "cached_input_tokens", "output_tokens"):
        totals[key] += _count(row.get(key))
    cost = row.get("cost_usd")
    if isinstance(cost, (int, float)) and not isinstance(cost, bool):
        totals["cost_usd"] = round(totals["cost_usd"] + cost, 6)


class UsageLog:
    def __init__(self, path: Path, claude_code: ClaudeCodeUsage | None = None) -> None:
        self.path = path
        self.claude_code = claude_code
        self._lock = threading.Lock()

    def record(self, entry: Mapping[str, object]) -> None:
        line = json.dumps(dict(entry), ensure_ascii=False, separators=(",", ":"))
        try:
            with self._lock, self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            # Usage tracking must never fail a coach request.
            return

    def rows(self, since: datetime) -> list[dict[str, object]]:
        try:
            with self._lock:
                lines = self.path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            return []
        rows = []
        for line in lines:
            try:
                row = json.loads(line)
                at = datetime.fromisoformat(row["at"])
            except (TypeError, ValueError, KeyError):
                continue
            if at >= since:
                rows.append({**row, "_at": at})
        return rows

    def summary(self, now: datetime | None = None) -> dict[str, object]:
        now = (now or datetime.now(timezone.utc)).astimezone()
        rows = self.rows(now - timedelta(days=READ_DAYS))
        starts = {
            "today": now.replace(hour=0, minute=0, second=0, microsecond=0),
            "7d": now - timedelta(days=7),
            "30d": now - timedelta(days=30),
        }
        periods = {name: _empty_totals() for name in starts}
        kinds: dict[str, dict[str, object]] = {}
        for row in rows:
            for name, start in starts.items():
                if row["_at"] >= start:
                    _add(periods[name], row)
            if row["_at"] >= starts["7d"]:
                _add(kinds.setdefault(str(row.get("kind") or "Other"), _empty_totals()), row)
        latest_limits = next(
            ({"captured_at": row["at"], **row["limits"]} for row in reversed(rows) if isinstance(row.get("limits"), Mapping)),
            None,
        )
        if latest_limits:
            self._add_coach_estimates(latest_limits, rows, now)
        by_kind = sorted(
            ({"kind": kind, **totals} for kind, totals in kinds.items()),
            key=lambda item: (item["cost_usd"], item["input_tokens"] + item["output_tokens"]),
            reverse=True,
        )
        recent = [{key: value for key, value in row.items() if key not in {"_at", "limits"}} for row in rows[-RECENT_RUNS:]]
        return {
            "limits": latest_limits,
            "periods": periods,
            "by_kind_7d": by_kind,
            "recent": list(reversed(recent)),
        }

    def _add_coach_estimates(self, limits: dict[str, object], rows: list[dict[str, object]], now: datetime) -> None:
        """Estimate the coach's share of each plan window.

        The window's utilization is calibrated against what Claude Code and the coach
        spent at API prices up to the snapshot, giving percent per dollar; the coach's
        spend in the window times that rate is its share. claude.ai chats are invisible
        here, so the estimate leans high on days with chat use.
        """

        if self.claude_code is None:
            return
        captured_at = datetime.fromisoformat(str(limits["captured_at"]))
        for name, length in WINDOW_LENGTHS.items():
            window = limits.get(name)
            if not isinstance(window, dict) or not window.get("resets_at"):
                continue
            resets_at = datetime.fromisoformat(window["resets_at"])
            if resets_at <= now:
                window["stale"] = True
                continue
            start = resets_at - length
            coach_rows = [row for row in rows if row["_at"] >= start and row.get("cli") == "claude"]
            coach_cost = sum(float(row.get("cost_usd") or 0) for row in coach_rows)
            coach_until_snapshot = sum(float(row.get("cost_usd") or 0) for row in coach_rows if row["_at"] <= captured_at)
            code_until_snapshot = self.claude_code.cost(start, captured_at)
            calibration = coach_until_snapshot + code_until_snapshot
            if calibration <= 0:
                continue
            window["coach_estimate"] = {
                "utilization": round(min(coach_cost * window["utilization"] / calibration, window["utilization"]), 4),
                "coach_cost_usd": round(coach_cost, 4),
                "claude_code_cost_usd": round(code_until_snapshot, 4),
            }

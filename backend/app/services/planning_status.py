from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Tuple

COMPLETE_SPRINT_STATUSES = {"complete", "effectively_complete", "functionally_implemented", "structurally_complete"}


def _find_docs_dir() -> Path:
    current = Path(__file__).resolve()
    for parent in [current.parent, *current.parents]:
        candidate = parent / "docs"
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("Could not locate docs directory for planning status service.")


def _get_docs_paths() -> Tuple[Path, Path]:
    docs_dir = _find_docs_dir()
    return docs_dir, docs_dir / "sprints"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    return match.group(1) if match else ""


def _plain(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", "")).strip()


def _get_active_roadmap_path(docs_dir: Path, index_text: str) -> Path | None:
    match = re.search(r"^Active roadmap:\s*`([^`]+)`\s*$", index_text, re.MULTILINE)
    return docs_dir / match.group(1) if match else None


def _parse_roadmap_phases(roadmap_text: str) -> list[dict]:
    phases: list[dict] = []
    matches = list(re.finditer(r"^## Phase (\d+): (.+)$", roadmap_text, re.MULTILINE))
    for index, match in enumerate(matches):
        section_end = matches[index + 1].start() if index + 1 < len(matches) else len(roadmap_text)
        section = roadmap_text[match.end():section_end]
        goal_match = re.search(r"Goal:\s*(.+)", section)
        complete = re.search(r"^Status:\s*complete\b", section, re.MULTILINE | re.IGNORECASE)
        phases.append({
            "number": int(match.group(1)),
            "title": match.group(2).strip(),
            "goal": goal_match.group(1).strip() if goal_match else None,
            "status": "complete" if complete else "planned",
            "is_current": False,
        })
    current = next((phase for phase in phases if phase["status"] != "complete"), None)
    if current:
        current["is_current"] = True
    return phases


def _parse_archived_roadmaps(index_text: str) -> list[dict]:
    pattern = re.compile(r"^-\s+`(roadmaps/[^`]+)`\s+—\s+(.+)$", re.MULTILINE)
    return [{"path": f"docs/{m.group(1)}", "summary": m.group(2).strip()} for m in pattern.finditer(index_text)]


def _parse_open_threads(index_text: str) -> list[dict]:
    pattern = re.compile(r"^-\s+\*\*(.+?)\*\*\s+—\s+(.+)$", re.MULTILINE)
    return [{"title": m.group(1).strip(), "detail": m.group(2).strip()} for m in pattern.finditer(_section(index_text, "Open Threads"))]


def _parse_shipped(current_state_text: str) -> list[dict]:
    """Dated entries under "Recently Completed", newest first. Undated entries are old sprint records."""
    items: list[dict] = []
    parts = re.split(r"^### ", _section(current_state_text, "Recently Completed"), flags=re.MULTILINE)[1:]
    for part in parts:
        title, _, body = part.partition("\n")
        lead = body.strip().split("\n\n", 1)[0]
        date_match = re.match(r"(\d{4}-\d{2}-\d{2})[^:]*:\s*(.*)", lead, re.DOTALL)
        if not date_match:
            continue
        # "`services/x.py` shrinks the week..." reads as "Shrinks the week..." on the page.
        text = re.sub(r"^`[^`]+`\s+", "", date_match.group(2).strip())
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z`\"(])", text)
        # Skip lead-ins like "Implements the `x` idea." or "The second coach moment."
        useful = [s for s in sentences if len(s) >= 35 and not s.lower().startswith("implements the")]
        summary = _plain((useful or sentences)[0])
        items.append({
            "title": _plain(title),
            "date": date_match.group(1),
            "summary": summary[:1].upper() + summary[1:],
        })
    items.sort(key=lambda item: item["date"], reverse=True)
    return items


def _parse_sprint_listing(readme_text: str) -> list[dict]:
    items: list[dict] = []
    pattern = re.compile(r"^\d+\.\s+\[([^\]]+)\]\(([^)]+)\)\s+—\s+(.+?),\s+([a-z_ ]+)$", re.MULTILINE)
    for order, match in enumerate(pattern.finditer(readme_text), start=1):
        filename = match.group(2).strip()
        items.append({
            "order": order,
            "slug": filename.replace(".md", ""),
            "title": match.group(1).strip(),
            "filename": filename,
            "summary": match.group(3).strip(),
            "status": match.group(4).strip().replace(" ", "_"),
        })
    return items


def get_planning_status() -> dict:
    docs_dir, sprints_dir = _get_docs_paths()
    index_text = _read_text(docs_dir / "roadmap.md")
    active_path = _get_active_roadmap_path(docs_dir, index_text)
    phases = _parse_roadmap_phases(_read_text(active_path)) if active_path else []
    sprints = _parse_sprint_listing(_read_text(sprints_dir / "README.md"))
    shipped = _parse_shipped(_read_text(docs_dir / "current-state.md"))

    return {
        "generated_at": datetime.now().isoformat(),
        "roadmap": {
            "title": "Training Dashboard Roadmap",
            "active_path": str(active_path.relative_to(docs_dir.parent)) if active_path else None,
            "current_phase": next((phase for phase in phases if phase["is_current"]), None),
            "completed_phases": sum(1 for phase in phases if phase["status"] == "complete"),
            "total_phases": len(phases),
            "phases": phases,
            "open_threads": _parse_open_threads(index_text),
            "archived": _parse_archived_roadmaps(index_text),
        },
        "shipped": shipped,
        "sprints": {
            "completed_count": sum(1 for sprint in sprints if sprint["status"] in COMPLETE_SPRINT_STATUSES),
            "total_count": len(sprints),
            "items": sprints,
        },
        "sources": [
            {"label": "Roadmap index and open threads", "path": "docs/roadmap.md"},
            {"label": "Shipped log", "path": "docs/current-state.md"},
            {"label": "Sprint archive", "path": "docs/sprints/README.md"},
        ],
    }

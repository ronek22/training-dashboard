from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Tuple


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


def _parse_roadmap_phases(roadmap_text: str, current_state_text: str) -> list[dict]:
    phases: list[dict] = []
    pattern = re.compile(r"^## Phase (\d+): (.+)$", re.MULTILINE)
    matches = list(pattern.finditer(roadmap_text))

    for index, match in enumerate(matches):
        number = int(match.group(1))
        title = match.group(2).strip()
        section_start = match.end()
        section_end = matches[index + 1].start() if index + 1 < len(matches) else len(roadmap_text)
        section = roadmap_text[section_start:section_end]
        goal_match = re.search(r"Goal:\s*(.+)", section)
        goal = goal_match.group(1).strip() if goal_match else None

        lowered_state = current_state_text.lower()
        title_tokens = title.lower()
        phase_status = "planned"
        if f"phase {number}" in lowered_state and "complete" in lowered_state:
            if re.search(rf"phase {number}.*complete", lowered_state):
                phase_status = "complete"
        if phase_status != "complete":
            if number == 2 and "sprint 3 feedback loop" in lowered_state and "complete" in lowered_state:
                phase_status = "complete"
            elif number == 3 and "sprint 4 goal-aware planning" in lowered_state and "complete" in lowered_state:
                phase_status = "complete"
            elif number == 4 and "sprint 5 planned-to-actual linking" in lowered_state and "complete" in lowered_state:
                phase_status = "complete"
        phases.append({
            "number": number,
            "title": title,
            "goal": goal,
            "status": phase_status,
            "is_current": False,
            "slug": f"phase-{number}",
            "match_key": title_tokens,
        })

    incomplete = [phase for phase in phases if phase["status"] != "complete"]
    if incomplete:
        incomplete[0]["is_current"] = True

    for phase in phases:
        phase.pop("match_key", None)
    return phases


def _parse_sprint_listing(readme_text: str) -> list[dict]:
    items: list[dict] = []
    pattern = re.compile(r"^\d+\.\s+\[([^\]]+)\]\(([^)]+)\)\s+—\s+(.+?),\s+([a-z_ ]+)$", re.MULTILINE)
    for order, match in enumerate(pattern.finditer(readme_text), start=1):
        title = match.group(1).strip()
        filename = match.group(2).strip()
        summary = match.group(3).strip()
        status = match.group(4).strip().replace(" ", "_")
        items.append({
            "order": order,
            "slug": filename.replace(".md", ""),
            "title": title,
            "filename": filename,
            "summary": summary,
            "status": status,
        })
    return items


def _parse_next_focus(current_state_text: str, sprints: list[dict]) -> dict | None:
    label_match = re.search(r"-\s+(Sprint\s+\d+)(?:\s+([^\n]+))?", current_state_text)
    if not label_match:
        return None

    label = label_match.group(1).strip()
    trailing = (label_match.group(2) or "").strip()
    details = trailing.rstrip(":") if trailing else ""
    sprint_number = re.search(r"(\d+)", label)
    sprint = None
    if sprint_number:
        sprint_token = f"sprint-{sprint_number.group(1)}"
        sprint = next((item for item in sprints if sprint_token in item["slug"]), None)
    return {
        "label": label,
        "summary": sprint["summary"] if sprint else details,
        "slug": sprint["slug"] if sprint else None,
        "status": sprint["status"] if sprint else "planned",
    }


def get_planning_status() -> dict:
    docs_dir, sprints_dir = _get_docs_paths()
    roadmap_text = _read_text(docs_dir / "roadmap.md")
    current_state_text = _read_text(docs_dir / "current-state.md")
    sprints_readme_text = _read_text(sprints_dir / "README.md")

    sprints = _parse_sprint_listing(sprints_readme_text)
    phases = _parse_roadmap_phases(roadmap_text, current_state_text)
    next_focus = _parse_next_focus(current_state_text, sprints)

    completed_sprints = sum(1 for sprint in sprints if sprint["status"] in {"complete", "effectively_complete", "functionally_implemented", "structurally_complete"})
    active_sprints = sum(1 for sprint in sprints if sprint["status"] == "active")
    planned_sprints = sum(1 for sprint in sprints if sprint["status"] == "planned")
    completed_phases = sum(1 for phase in phases if phase["status"] == "complete")
    current_phase = next((phase for phase in phases if phase["is_current"]), None)

    return {
        "generated_at": datetime.now().isoformat(),
        "roadmap": {
            "title": "Training Dashboard Roadmap",
            "current_phase": current_phase,
            "current_focus": next_focus,
            "completed_phases": completed_phases,
            "total_phases": len(phases),
            "phases": phases,
        },
        "sprints": {
            "completed_count": completed_sprints,
            "active_count": active_sprints,
            "planned_count": planned_sprints,
            "total_count": len(sprints),
            "next_recommended": next_focus,
            "items": sprints,
        },
        "sources": [
            {"label": "Roadmap", "path": "docs/roadmap.md"},
            {"label": "Current State", "path": "docs/current-state.md"},
            {"label": "Sprints Index", "path": "docs/sprints/README.md"},
        ],
    }

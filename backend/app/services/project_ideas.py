"""Reviewed repo proposals, with user decisions stored separately in SQLite."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .planning_status import _find_docs_dir


class Idea(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,79}$")
    title: str = Field(min_length=3, max_length=120)
    category: Literal["Product", "Experience", "Reliability", "Engineering"]
    effort: Literal["Small", "Medium", "Large"]
    priority: Literal["High", "Medium", "Low"]
    problem: str = Field(min_length=10, max_length=2000)
    proposal: str = Field(min_length=10, max_length=3000)
    benefit: str = Field(min_length=10, max_length=1000)
    evidence: list[str] = Field(min_length=1, max_length=10)
    acceptance_criteria: list[str] = Field(min_length=2, max_length=10)
    created_on: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class Review(BaseModel):
    reviewed_at: datetime
    summary: str = Field(min_length=10, max_length=2000)
    ideas: list[Idea] = Field(max_length=200)


def load_catalog(path=None):
    path = path or _find_docs_dir() / "project-ideas.json"
    review = Review.model_validate_json(path.read_text(encoding="utf-8"))
    ids = [idea.id for idea in review.ideas]
    if len(ids) != len(set(ids)):
        raise ValueError("Idea IDs must be unique")
    return review.model_dump(mode="json")


def init_schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS project_idea_decisions (
        idea_id TEXT PRIMARY KEY,
        status TEXT NOT NULL CHECK(status IN ('new', 'shortlisted', 'building', 'done', 'dismissed')),
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")


def build_brief(idea):
    criteria = "\n".join(f"- {item}" for item in idea["acceptance_criteria"])
    evidence = "\n".join(f"- {item}" for item in idea["evidence"])
    return (f"Implement this Training Dashboard idea: {idea['title']}\n\n"
            f"Problem\n{idea['problem']}\n\nProposal\n{idea['proposal']}\n\n"
            f"Expected benefit\n{idea['benefit']}\n\nStarting points\n{evidence}\n\n"
            f"Acceptance criteria\n{criteria}\n\n"
            "First inspect the current code and roadmap: this proposal may predate recent changes. "
            "Preserve unrelated uncommitted work. Implement the smallest complete version, "
            "run relevant tests and the frontend build, and update the project documentation. "
            "Do not change live training data or deploy without explicit authorization. "
            "Report what changed and how it was verified.\n")


def get_board(conn, path=None):
    catalog = load_catalog(path)
    decisions = dict(conn.execute("SELECT idea_id, status FROM project_idea_decisions"))
    for idea in catalog["ideas"]:
        idea["status"] = decisions.get(idea["id"], "new")
        idea["build_brief"] = build_brief(idea)
    catalog["ideas"].sort(key=lambda idea: ({"High": 0, "Medium": 1, "Low": 2}[idea["priority"]], idea["title"]))
    return catalog


def set_status(conn, idea_id, status, path=None):
    if status not in {"new", "shortlisted", "building", "done", "dismissed"}:
        raise ValueError("Unknown idea status")
    if not any(idea["id"] == idea_id for idea in load_catalog(path)["ideas"]):
        raise LookupError("Idea not found")
    conn.execute("""INSERT INTO project_idea_decisions (idea_id, status) VALUES (?, ?)
        ON CONFLICT(idea_id) DO UPDATE SET status=excluded.status, updated_at=CURRENT_TIMESTAMP""",
                 (idea_id, status))
    return {"id": idea_id, "status": status}

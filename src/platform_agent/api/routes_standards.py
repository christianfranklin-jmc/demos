"""Standards page routes (T128, US7).

GET /standards            — list every standards category + a content preview.
GET /standards/{category} — full Markdown body for one category.

Reads the static Markdown files in `src/platform_agent/standards/`. The
v1 Standards page (FR-037) is read-only; PRD generation consults this
content + the per-connection metric registry to populate the
"Standards applied" footer (FR-038, SC-011).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from platform_agent.api.deps import SessionContext, get_session_context

logger = logging.getLogger(__name__)
router = APIRouter(tags=["standards"])

# Categories enumerated explicitly so we keep ordering stable + the
# 6-category invariant (FR-037) is testable against the directory.
CATEGORIES: list[tuple[str, str]] = [
    ("naming", "Naming conventions"),
    ("metrics", "Approved metric definitions"),
    ("pii_policy", "PII / PCI / PHI tagging policy"),
    ("dbt_templates", "dbt project templates"),
    ("domains", "Approved data domains"),
    ("iceberg_standards", "Iceberg table standards"),
]

_DIR = Path(__file__).resolve().parent.parent / "standards"


def _read(category: str) -> str:
    path = _DIR / f"{category}.md"
    if not path.exists():
        raise FileNotFoundError(category)
    return path.read_text(encoding="utf-8")


def _preview(content: str, max_chars: int = 240) -> str:
    # First non-blank line(s) up to max_chars.
    lines = [line for line in content.splitlines() if line.strip() and not line.startswith("#")]
    text = " ".join(lines)
    return text[:max_chars] + ("…" if len(text) > max_chars else "")


# ───── Response shapes ─────


class StandardsCategory(BaseModel):
    key: str
    label: str
    preview: str


class StandardsListResponse(BaseModel):
    categories: list[StandardsCategory]


class StandardsContent(BaseModel):
    key: str
    label: str
    body: str


# ───── Endpoints ─────


@router.get("/standards", response_model=StandardsListResponse)
async def get_standards(
    _ctx: Annotated[SessionContext, Depends(get_session_context)],
) -> StandardsListResponse:
    out: list[StandardsCategory] = []
    for key, label in CATEGORIES:
        try:
            body = _read(key)
        except FileNotFoundError:
            logger.warning("standards: missing file %s.md", key)
            continue
        out.append(StandardsCategory(key=key, label=label, preview=_preview(body)))
    return StandardsListResponse(categories=out)


@router.get("/standards/{category}", response_model=StandardsContent)
async def get_standards_category(
    category: str,
    _ctx: Annotated[SessionContext, Depends(get_session_context)],
) -> StandardsContent:
    label = next((lbl for key, lbl in CATEGORIES if key == category), None)
    if label is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    try:
        body = _read(category)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    return StandardsContent(key=category, label=label, body=body)


__all__ = ["router", "CATEGORIES"]

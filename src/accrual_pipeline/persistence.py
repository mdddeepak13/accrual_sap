"""SQLAlchemy models and session management for flagged items + run metadata.

Sync engine. Write volume is tiny (few dozen rows per run), so the cost of
blocking the event loop briefly for a commit is not meaningful compared to
the complexity of async SQLAlchemy. If this ever scales, swap in AsyncEngine.

Swap DATABASE_URL from sqlite to hana to promote to production without
touching calling code.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

from accrual_pipeline.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all persistence models."""


class RunMetadata(Base):
    """One row per pipeline run. Tracks lifecycle + Claude model used."""

    __tablename__ = "run_metadata"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    model: Mapped[str] = mapped_column(String(64))
    accrual_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))  # running | completed | failed

    flagged_items: Mapped[list["FlaggedItem"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    approved_items: Mapped[list["ApprovedItem"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class FlaggedItem(Base):
    """One row per (accrual_id, run_id) that Claude flagged as irregular.

    Covers both flag_stale_po_accrual and flag_duplicate_accrual. Duplicates
    produce N rows (one per accrual_id in the group) sharing the same reason.
    `accrual_snapshot_json` freezes the business fields at decision time so
    the UI can render the row without re-joining FI/MM/CO.
    """

    __tablename__ = "flagged_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("run_metadata.run_id", ondelete="CASCADE")
    )
    accrual_id: Mapped[str] = mapped_column(String(128))
    tool_name: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str | None] = mapped_column(String(16), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[str] = mapped_column(Text)
    accrual_snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    run: Mapped[RunMetadata] = relationship(back_populates="flagged_items")


class ApprovedItem(Base):
    """One row per accrual Claude approved. These are the "Accruals to be
    posted" rows the finance team reviews. Snapshot is frozen at decision
    time for the same reason as FlaggedItem.
    """

    __tablename__ = "approved_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("run_metadata.run_id", ondelete="CASCADE")
    )
    accrual_id: Mapped[str] = mapped_column(String(128))
    notes: Mapped[str] = mapped_column(Text)
    accrual_snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    run: Mapped[RunMetadata] = relationship(back_populates="approved_items")


# --- Engine / session management ---

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def init_db(database_url: str | None = None) -> Engine:
    """Create the engine + tables. Safe to call multiple times."""
    global _engine, _session_factory
    url = database_url or get_settings().database_url
    _engine = create_engine(url, future=True)
    _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)
    Base.metadata.create_all(_engine)
    return _engine


def reset_db() -> None:
    """Test helper — drop the cached engine so the next init_db rebuilds."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


@contextmanager
def get_session() -> Iterator[Session]:
    """Yield a session with auto-commit on success, rollback on exception."""
    if _session_factory is None:
        init_db()
    assert _session_factory is not None
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# --- High-level API used by router / main ---


def record_run_start(run_id: str, *, model: str, accrual_count: int) -> None:
    """Insert a run_metadata row with status='running'.

    Idempotent: a second call for the same run_id is a no-op. This exists
    because the POST /runs endpoint writes the row synchronously before
    returning (so GET /runs/{id} always finds it) while run_pipeline also
    calls this on CLI invocations — we can't rely on "only one caller".
    """
    with get_session() as s:
        if s.get(RunMetadata, run_id) is not None:
            return
        s.add(
            RunMetadata(
                run_id=run_id,
                started_at=datetime.now(timezone.utc),
                model=model,
                accrual_count=accrual_count,
                status="running",
            )
        )


def update_run_accrual_count(run_id: str, accrual_count: int) -> None:
    """Patch accrual_count after the fetch/normalize stage completes."""
    with get_session() as s:
        run = s.get(RunMetadata, run_id)
        if run is None:
            raise ValueError(f"Unknown run_id: {run_id!r}")
        run.accrual_count = accrual_count


def record_run_finish(run_id: str, *, status: str) -> None:
    """Update the run row to final status ('completed' or 'failed')."""
    if status not in ("completed", "failed"):
        raise ValueError(f"Invalid run status: {status!r}")
    with get_session() as s:
        run = s.get(RunMetadata, run_id)
        if run is None:
            raise ValueError(f"Unknown run_id: {run_id!r}")
        run.finished_at = datetime.now(timezone.utc)
        run.status = status


def persist_flagged_item(
    *,
    run_id: str,
    accrual_id: str,
    tool_name: str,
    severity: str | None,
    reason: str,
    payload: dict[str, Any],
    accrual_snapshot: dict[str, Any] | None = None,
) -> int:
    """Insert a FlaggedItem row. Returns the new row id."""
    with get_session() as s:
        row = FlaggedItem(
            run_id=run_id,
            accrual_id=accrual_id,
            tool_name=tool_name,
            severity=severity,
            reason=reason,
            payload_json=json.dumps(payload, sort_keys=True, default=str),
            accrual_snapshot_json=(
                json.dumps(accrual_snapshot, sort_keys=True, default=str)
                if accrual_snapshot is not None
                else None
            ),
            created_at=datetime.now(timezone.utc),
        )
        s.add(row)
        s.flush()
        return row.id


def persist_approved_item(
    *,
    run_id: str,
    accrual_id: str,
    notes: str,
    accrual_snapshot: dict[str, Any] | None = None,
) -> int:
    """Insert an ApprovedItem row. Returns the new row id."""
    with get_session() as s:
        row = ApprovedItem(
            run_id=run_id,
            accrual_id=accrual_id,
            notes=notes,
            accrual_snapshot_json=(
                json.dumps(accrual_snapshot, sort_keys=True, default=str)
                if accrual_snapshot is not None
                else None
            ),
            created_at=datetime.now(timezone.utc),
        )
        s.add(row)
        s.flush()
        return row.id


def list_runs(limit: int = 50) -> list[dict[str, Any]]:
    """Return recent runs ordered newest first (no per-item rows)."""
    with get_session() as s:
        rows = list(s.scalars(
            select(RunMetadata).order_by(RunMetadata.started_at.desc()).limit(limit)
        ))
        flag_counts = {
            r.run_id: s.query(FlaggedItem).filter(FlaggedItem.run_id == r.run_id).count()
            for r in rows
        }
        approved_counts = {
            r.run_id: s.query(ApprovedItem).filter(ApprovedItem.run_id == r.run_id).count()
            for r in rows
        }
        return [
            {
                "run_id": r.run_id,
                "started_at": r.started_at.isoformat(),
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "model": r.model,
                "accrual_count": r.accrual_count,
                "status": r.status,
                "flagged_count": flag_counts.get(r.run_id, 0),
                "approved_count": approved_counts.get(r.run_id, 0),
            }
            for r in rows
        ]


def get_run_summary(run_id: str) -> dict[str, Any] | None:
    """Return run metadata + flagged items. None if run not found."""
    with get_session() as s:
        run = s.get(RunMetadata, run_id)
        if run is None:
            return None
        flagged = list(s.scalars(
            select(FlaggedItem).where(FlaggedItem.run_id == run_id)
            .order_by(FlaggedItem.id)
        ))
        approved = list(s.scalars(
            select(ApprovedItem).where(ApprovedItem.run_id == run_id)
            .order_by(ApprovedItem.id)
        ))
        return {
            "run_id": run.run_id,
            "started_at": run.started_at.isoformat(),
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "model": run.model,
            "accrual_count": run.accrual_count,
            "status": run.status,
            "flagged": [
                {
                    "id": i.id,
                    "accrual_id": i.accrual_id,
                    "tool_name": i.tool_name,
                    "severity": i.severity,
                    "reason": i.reason,
                    "payload": json.loads(i.payload_json),
                    "accrual": (
                        json.loads(i.accrual_snapshot_json)
                        if i.accrual_snapshot_json else None
                    ),
                    "created_at": i.created_at.isoformat(),
                }
                for i in flagged
            ],
            "approved": [
                {
                    "id": a.id,
                    "accrual_id": a.accrual_id,
                    "notes": a.notes,
                    "accrual": (
                        json.loads(a.accrual_snapshot_json)
                        if a.accrual_snapshot_json else None
                    ),
                    "created_at": a.created_at.isoformat(),
                }
                for a in approved
            ],
        }

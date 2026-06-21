from __future__ import annotations

import sqlite3
from typing import Any

from watchtower.models import InterventionFeedback
from watchtower.store_support import ConnectionFactory, iso


def upsert_feedback(
    connection_factory: ConnectionFactory, feedback: InterventionFeedback
) -> InterventionFeedback:
    with connection_factory() as connection:
        connection.execute(
            """
            INSERT INTO feedback (
                id, intervention_id, created_at, updated_at, rating, comment,
                channel, detector, detector_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(intervention_id) DO UPDATE SET
                updated_at = excluded.updated_at,
                rating = excluded.rating,
                comment = excluded.comment,
                channel = excluded.channel,
                detector = excluded.detector,
                detector_version = excluded.detector_version
            """,
            (
                feedback.id,
                feedback.intervention_id,
                iso(feedback.created_at),
                iso(feedback.updated_at),
                feedback.rating,
                feedback.comment,
                feedback.channel,
                feedback.detector,
                feedback.detector_version,
            ),
        )
        row = connection.execute(
            "SELECT * FROM feedback WHERE intervention_id = ?", (feedback.intervention_id,)
        ).fetchone()
    if row is None:
        raise RuntimeError("Feedback upsert did not create a row")
    return _feedback_from_row(row)


def get_feedback(
    connection_factory: ConnectionFactory, intervention_id: str
) -> InterventionFeedback | None:
    with connection_factory() as connection:
        row = connection.execute(
            "SELECT * FROM feedback WHERE intervention_id = ?", (intervention_id,)
        ).fetchone()
    return _feedback_from_row(row) if row else None


def delete_feedback(connection_factory: ConnectionFactory, intervention_id: str) -> bool:
    with connection_factory() as connection:
        cursor = connection.execute(
            "DELETE FROM feedback WHERE intervention_id = ?", (intervention_id,)
        )
        return cursor.rowcount == 1


def list_feedback(
    connection_factory: ConnectionFactory,
    *,
    limit: int = 100,
    detector: str | None = None,
    rating: str | None = None,
) -> list[InterventionFeedback]:
    clauses: list[str] = []
    parameters: list[Any] = []
    if detector is not None:
        clauses.append("detector = ?")
        parameters.append(detector)
    if rating is not None:
        clauses.append("rating = ?")
        parameters.append(rating)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    parameters.append(max(1, min(limit, 1000)))
    with connection_factory() as connection:
        rows = connection.execute(
            f"SELECT * FROM feedback{where} ORDER BY updated_at DESC LIMIT ?", parameters
        ).fetchall()
    return [_feedback_from_row(row) for row in rows]


def quality_metrics(connection_factory: ConnectionFactory) -> dict[str, Any]:
    positive = {"useful", "action_accepted"}
    negative = {
        "not_useful",
        "incorrect",
        "too_early",
        "too_late",
        "already_known",
        "too_disruptive",
        "action_rejected",
    }
    with connection_factory() as connection:
        rows = connection.execute(
            "SELECT detector, rating, COUNT(*) AS count FROM feedback "
            "GROUP BY detector, rating ORDER BY detector, rating"
        ).fetchall()
    by_detector: dict[str, dict[str, Any]] = {}
    overall: dict[str, Any] = {"total": 0, "positive": 0, "negative": 0}
    ratings: dict[str, int] = {}
    for row in rows:
        detector = str(row["detector"])
        rating = str(row["rating"])
        count = int(row["count"])
        bucket = by_detector.setdefault(
            detector,
            {"detector": detector, "total": 0, "positive": 0, "negative": 0, "ratings": {}},
        )
        bucket["total"] += count
        bucket["ratings"][rating] = count
        overall["total"] += count
        ratings[rating] = ratings.get(rating, 0) + count
        if rating in positive:
            bucket["positive"] += count
            overall["positive"] += count
        elif rating in negative:
            bucket["negative"] += count
            overall["negative"] += count
    for bucket in by_detector.values():
        total = int(bucket["total"])
        bucket["positive_rate"] = bucket["positive"] / total if total else None
    overall["positive_rate"] = overall["positive"] / overall["total"] if overall["total"] else None
    return {"overall": overall, "ratings": ratings, "by_detector": list(by_detector.values())}


def _feedback_from_row(row: sqlite3.Row) -> InterventionFeedback:
    return InterventionFeedback(
        id=row["id"],
        intervention_id=row["intervention_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        rating=row["rating"],
        comment=row["comment"],
        channel=row["channel"],
        detector=row["detector"],
        detector_version=row["detector_version"],
    )

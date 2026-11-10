import sqlite3

import pytest

from app.database import SCHEMA
from app import outcomes


def test_rejects_out_of_order_completion(tmp_path, monkeypatch):
    database = tmp_path / "chronology_test.db"

    def connect():
        conn = sqlite3.connect(database)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    conn = connect()
    conn.executescript(SCHEMA)

    conn.execute(
        """
        INSERT INTO learners
        (learner_id, name, enrolled_at, status)
        VALUES (?, ?, ?, ?)
        """,
        (
            "LRN-000001",
            "Test Learner",
            "2026-01-01T00:00:00",
            "ACTIVE"
        )
    )

    conn.execute(
        """
        INSERT INTO courses
        (course_id, title, created_at, status)
        VALUES (?, ?, ?, ?)
        """,
        (
            "CRS-000001",
            "Test Course",
            "2026-01-01T00:00:00",
            "ACTIVE"
        )
    )

    conn.execute(
        """
        INSERT INTO skills
        (skill_id, course_id, name, difficulty)
        VALUES (?, ?, ?, ?)
        """,
        (
            "SKL-000001",
            "CRS-000001",
            "Test Skill",
            1
        )
    )

    conn.execute(
        """
        INSERT INTO content_items
        (
            content_id,
            course_id,
            title,
            format,
            difficulty,
            duration_minutes,
            status,
            published_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "CNT-000001",
            "CRS-000001",
            "Test Activity",
            "EXERCISE",
            1,
            20,
            "PUBLISHED",
            "2026-01-01T00:00:00"
        )
    )

    conn.execute(
        """
        INSERT INTO learning_paths
        (path_id, learner_id, course_id, created_at, status)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "PATH-2026-000001",
            "LRN-000001",
            "CRS-000001",
            "2026-11-10T09:00:00",
            "ACTIVE"
        )
    )

    conn.execute(
        """
        INSERT INTO recommendations
        (
            recommendation_id,
            learner_id,
            path_id,
            content_id,
            target_skill_id,
            generated_at,
            mastery_at_decision,
            reason_code,
            rationale,
            priority_rank
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "REC-000000001",
            "LRN-000001",
            "PATH-2026-000001",
            "CNT-000001",
            "SKL-000001",
            "2026-11-10T09:30:00",
            0.5,
            "LOW_MASTERY",
            "Test recommendation",
            1
        )
    )

    conn.execute(
        """
        INSERT INTO learning_path_steps
        (
            step_id,
            path_id,
            content_id,
            step_number,
            mastery_before,
            mastery_after,
            recorded_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "STEP-000000001",
            "PATH-2026-000001",
            "CNT-000001",
            1,
            0.5,
            0.6,
            "2026-11-10T10:10:00"
        )
    )

    conn.commit()
    conn.close()

    monkeypatch.setattr(
        outcomes,
        "get_connection",
        connect
    )

    with pytest.raises(
        ValueError,
        match="previous learning-path step"
    ):
        outcomes.record_outcome(
            recommendation_id="REC-000000001",
            score=90,
            completed_at="2026-11-10T10:03:00"
        )

    conn = connect()

    try:
        attempts = conn.execute(
            "SELECT COUNT(*) FROM attempts"
        ).fetchone()[0]

        assert attempts == 0

    finally:
        conn.close()
import sqlite3

from app import outcomes
from app.database import SCHEMA


def test_activity_lifecycle(tmp_path, monkeypatch):
    database = tmp_path / "lifecycle.db"

    def connect():
        conn = sqlite3.connect(database)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    conn = connect()
    conn.executescript(SCHEMA)

    conn.executescript("""
        INSERT INTO learners
        (learner_id, name, enrolled_at)
        VALUES
        ('LRN-000001', 'Test Learner', '2026-01-01T00:00:00');

        INSERT INTO courses
        (course_id, title, created_at)
        VALUES
        ('CRS-000001', 'Python Basics', '2026-01-01T00:00:00');

        INSERT INTO skills
        (skill_id, course_id, name, difficulty)
        VALUES
        ('SKL-000001', 'CRS-000001', 'Python', 1);

        INSERT INTO content_items
        (
            content_id, course_id, title, format,
            difficulty, duration_minutes, published_at
        )
        VALUES
        (
            'CNT-000001', 'CRS-000001', 'Python Quiz',
            'QUIZ', 1, 10, '2026-01-01T00:00:00'
        );

        INSERT INTO learning_paths
        (path_id, learner_id, course_id, created_at)
        VALUES
        (
            'PATH-2026-000001', 'LRN-000001',
            'CRS-000001', '2026-11-10T09:00:00'
        );

        INSERT INTO recommendations
        (
            recommendation_id, learner_id, path_id,
            content_id, target_skill_id, generated_at,
            mastery_at_decision, reason_code,
            rationale, priority_rank
        )
        VALUES
        (
            'REC-000000001', 'LRN-000001',
            'PATH-2026-000001', 'CNT-000001',
            'SKL-000001', '2026-11-10T09:00:00',
            0.4, 'LOW_MASTERY', 'Needs practice', 1
        );

        INSERT INTO recommendation_events
        (
            event_id, recommendation_id,
            event_type, occurred_at
        )
        VALUES
        (
            'EVT-000000001', 'REC-000000001',
            'GENERATED', '2026-11-10T09:00:00'
        );
    """)

    conn.commit()
    conn.close()

    monkeypatch.setattr(outcomes, "get_connection", connect)

    mastery_values = iter([0.4, 0.85])

    monkeypatch.setattr(
        outcomes,
        "get_skill_mastery",
        lambda *args: next(mastery_values)
    )

    result = outcomes.record_outcome(
        recommendation_id="REC-000000001",
        score=90,
        completed_at="2026-11-10T09:05:00"
    )

    conn = connect()

    try:
        rows = conn.execute(
            """
            SELECT event_type, occurred_at
            FROM recommendation_events
            WHERE recommendation_id = ?
            ORDER BY event_id
            """,
            ("REC-000000001",)
        ).fetchall()

        events = [row["event_type"] for row in rows]

        assert events == [
            "GENERATED",
            "STARTED",
            "COMPLETED"
        ]

        assert rows[0]["occurred_at"] <= rows[1]["occurred_at"]
        assert rows[1]["occurred_at"] <= rows[2]["occurred_at"]

        assert result["status"] == "COMPLETED"
        assert result["improved"] is True

        attempts = conn.execute(
            "SELECT COUNT(*) FROM attempts"
        ).fetchone()[0]

        assessments = conn.execute(
            "SELECT COUNT(*) FROM assessment_results"
        ).fetchone()[0]

        steps = conn.execute(
            "SELECT COUNT(*) FROM learning_path_steps"
        ).fetchone()[0]

        assert attempts == 1
        assert assessments == 1
        assert steps == 1

    finally:
        conn.close()
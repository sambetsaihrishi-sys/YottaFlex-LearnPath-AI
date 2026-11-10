import sqlite3

from fastapi.testclient import TestClient

from app.main import app
from app.database import get_connection

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200


def test_dashboard():
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "LearnPath AI" in response.text


# Expected volumes per generator scale, keyed by learner count.
SCALES = {
    10000: {"skills": 500, "content_items": 2000, "attempts": 500000},  # full
    100: {"skills": 50, "content_items": 200, "attempts": 1000},        # starter
}


def test_statistics():
    response = client.get("/api/stats")
    assert response.status_code == 200

    data = response.json()

    expected = SCALES.get(data["learners"])
    assert expected is not None, (
        f"Unexpected learner count {data['learners']}; "
        "generate the starter or full dataset first"
    )

    assert data["skills"] == expected["skills"]
    assert data["content_items"] == expected["content_items"]
    assert data["attempts"] >= expected["attempts"]


def test_learner_list():
    response = client.get("/api/learners?limit=10")
    assert response.status_code == 200
    assert len(response.json()["learners"]) == 10


def test_mastery_api():
    response = client.get(
        "/api/learners/LRN-000001/mastery"
    )

    assert response.status_code == 200
    assert "skills" in response.json()


def test_database_integrity():
    conn = get_connection()

    try:
        result = conn.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        assert result == "ok"

    finally:
        conn.close()


def test_foreign_keys():
    conn = get_connection()

    try:
        violations = conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        assert len(violations) == 0

    finally:
        conn.close()


def test_assessment_score_range():
    conn = get_connection()

    try:
        invalid = conn.execute(
            """
            SELECT COUNT(*)
            FROM assessment_results
            WHERE score < 0 OR score > 100
            """
        ).fetchone()[0]

        assert invalid == 0

    finally:
        conn.close()


def test_attempt_timestamps():
    conn = get_connection()

    try:
        invalid = conn.execute(
            """
            SELECT COUNT(*)
            FROM attempts
            WHERE completed_at < started_at
            """
        ).fetchone()[0]

        assert invalid == 0

    finally:
        conn.close()


def test_recommendation_traceability():
    conn = get_connection()

    try:
        invalid = conn.execute(
            """
            SELECT COUNT(*)
            FROM recommendations r
            LEFT JOIN learning_paths p
              ON p.path_id = r.path_id
            WHERE p.path_id IS NULL
               OR p.learner_id != r.learner_id
            """
        ).fetchone()[0]

        assert invalid == 0

    finally:
        conn.close()


def test_negative_scenarios():
    from validation.negative_cases import (
        build_cases,
        detect_case
    )

    cases, valid_skills = build_cases()

    assert len(cases) == 5

    for case in cases:
        assert detect_case(case, valid_skills) is True


def test_completion_score_validation():
    response = client.post(
        "/api/recommendations/REC-000000001/complete",
        json={"score": 150}
    )

    assert response.status_code == 422
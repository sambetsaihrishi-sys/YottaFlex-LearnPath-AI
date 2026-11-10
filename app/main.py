from fastapi import FastAPI
from datetime import datetime, timezone
from app.mastery import get_skill_mastery

from app.database import get_connection

app = FastAPI(
    title="YottaFlex LearnPath AI",
    description="Adaptive Learning Recommendation System",
    version="1.0.0"
)


@app.get("/")
def home():
    return {
        "application": "YottaFlex LearnPath AI",
        "status": "running"
    }


@app.get("/health")
def health():
    conn = get_connection()

    try:
        conn.execute("SELECT 1")
        return {
            "status": "healthy",
            "database": "connected"
        }
    finally:
        conn.close()

from fastapi import HTTPException, Query

from app.recommender import recommend_for_learner


@app.get("/api/stats")
def get_stats():
    conn = get_connection()

    try:
        tables = [
            "learners",
            "courses",
            "skills",
            "content_items",
            "attempts",
            "assessment_results",
            "mastery_snapshots",
            "learning_paths",
            "recommendations",
            "recommendation_events"
        ]

        return {
            table: conn.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
            for table in tables
        }

    finally:
        conn.close()


@app.get("/api/learners")
def list_learners(
    limit: int = Query(20, ge=1, le=100)
):
    conn = get_connection()

    try:
        rows = conn.execute(
            """
            SELECT learner_id, name, enrolled_at, status
            FROM learners
            ORDER BY learner_id
            LIMIT ?
            """,
            (limit,)
        ).fetchall()

        return {
            "learners": [dict(row) for row in rows]
        }

    finally:
        conn.close()


@app.get("/api/learners/{learner_id}")
def get_learner(learner_id: str):
    conn = get_connection()

    try:
        row = conn.execute(
            """
            SELECT *
            FROM learners
            WHERE learner_id = ?
            """,
            (learner_id,)
        ).fetchone()

        if row is None:
            raise HTTPException(
                status_code=404,
                detail="Learner not found"
            )

        return dict(row)

    finally:
        conn.close()

@app.get("/api/learners/{learner_id}/mastery")
def learner_mastery(learner_id: str):
    conn = get_connection()

    try:
        learner = conn.execute(
            "SELECT 1 FROM learners WHERE learner_id = ?",
            (learner_id,)
        ).fetchone()

        if learner is None:
            raise HTTPException(
                status_code=404,
                detail="Learner not found"
            )

        rows = conn.execute(
            """
            SELECT
                ms.skill_id,
                s.name AS skill_name,
                ms.assessment_count
            FROM mastery_snapshots ms
            JOIN skills s
                ON ms.skill_id = s.skill_id
            WHERE ms.learner_id = ?
              AND ms.snapshot_id = (
                  SELECT latest.snapshot_id
                  FROM mastery_snapshots latest
                  WHERE latest.learner_id = ms.learner_id
                    AND latest.skill_id = ms.skill_id
                  ORDER BY latest.calculated_at DESC,
                           latest.snapshot_id DESC
                  LIMIT 1
              )
            """,
            (learner_id,)
        ).fetchall()

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        as_of = now.isoformat()

        skills = []

        for row in rows:
            mastery_score = get_skill_mastery(
                learner_id,
                row["skill_id"],
                as_of
            )

            skills.append({
                "skill_id": row["skill_id"],
                "skill_name": row["skill_name"],
                "mastery_score": mastery_score,
                "assessment_count": row["assessment_count"],
                "calculated_at": as_of
            })

        skills.sort(key=lambda item: item["mastery_score"])

        return {
            "learner_id": learner_id,
            "skills": skills
        }

    finally:
        conn.close()


@app.post("/api/learners/{learner_id}/recommend")
def generate_recommendations(
    learner_id: str,
    limit: int = Query(5, ge=1, le=20)
):
    try:
        recommendations = recommend_for_learner(
            learner_id,
            limit
        )

        return {
            "learner_id": learner_id,
            "count": len(recommendations),
            "recommendations": recommendations
        }

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error)
        )


@app.get("/api/learners/{learner_id}/recommendations")
def recommendation_history(learner_id: str):
    conn = get_connection()

    try:
        rows = conn.execute(
            """
            SELECT
                r.recommendation_id,
                r.content_id,
                ci.title AS content_title,
                r.target_skill_id,
                r.mastery_at_decision,
                r.reason_code,
                r.rationale,
                r.priority_rank,
                r.generated_at
            FROM recommendations r
            JOIN content_items ci
                ON r.content_id = ci.content_id
            WHERE r.learner_id = ?
            ORDER BY r.generated_at DESC, r.priority_rank
            LIMIT 50
            """,
            (learner_id,)
        ).fetchall()

        return {
            "learner_id": learner_id,
            "recommendations": [dict(row) for row in rows]
        }

    finally:
        conn.close()


@app.get("/api/learners/{learner_id}/paths")
def learning_paths(learner_id: str):
    conn = get_connection()

    try:
        rows = conn.execute(
            """
            SELECT
                lp.path_id,
                lp.course_id,
                c.title AS course_title,
                lp.created_at,
                lp.status
            FROM learning_paths lp
            JOIN courses c
                ON lp.course_id = c.course_id
            WHERE lp.learner_id = ?
            ORDER BY lp.created_at DESC
            """,
            (learner_id,)
        ).fetchall()

        return {
            "learner_id": learner_id,
            "paths": [dict(row) for row in rows]
        }

    finally:
        conn.close()


@app.get("/api/recommendations/{recommendation_id}/events")
def recommendation_events(recommendation_id: str):
    conn = get_connection()

    try:
        rows = conn.execute(
            """
            SELECT event_id, event_type, occurred_at
            FROM recommendation_events
            WHERE recommendation_id = ?
            ORDER BY occurred_at
            """,
            (recommendation_id,)
        ).fetchall()

        return {
            "recommendation_id": recommendation_id,
            "events": [dict(row) for row in rows]
        }

    finally:
        conn.close()
from pathlib import Path
from fastapi.responses import FileResponse

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@app.get("/dashboard", include_in_schema=False)
def dashboard():
    return FileResponse(FRONTEND_DIR / "index.html")

from pydantic import BaseModel, Field
from fastapi import HTTPException
from app.outcomes import record_outcome


class CompletionRequest(BaseModel):
    score: float = Field(ge=0, le=100)


@app.post("/api/recommendations/{recommendation_id}/complete")
def complete_recommendation(
    recommendation_id: str,
    payload: CompletionRequest
):
    try:
        return record_outcome(
            recommendation_id=recommendation_id,
            score=payload.score
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )
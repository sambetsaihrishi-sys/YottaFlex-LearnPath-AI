import argparse
import random
from datetime import datetime, timedelta, timezone

from app.database import get_connection
from app.mastery import get_skill_mastery


def record_outcome(recommendation_id, score, completed_at=None):
    if not 0 <= score <= 100:
        raise ValueError("Score must be between 0 and 100")

    conn = get_connection()

    try:
        recommendation = conn.execute(
            """
            SELECT
                r.recommendation_id,
                r.learner_id,
                r.content_id,
                r.target_skill_id,
                r.generated_at,
                r.mastery_at_decision
            FROM recommendations r
            WHERE r.recommendation_id = ?
            """,
            (recommendation_id,)
        ).fetchone()

        if recommendation is None:
            raise ValueError("Recommendation not found")

        existing = conn.execute(
            """
            SELECT attempt_id
            FROM attempts
            WHERE recommendation_id = ?
              AND status = 'COMPLETED'
            LIMIT 1
            """,
            (recommendation_id,)
        ).fetchone()

        if existing:
            raise ValueError("Outcome already recorded")

        generated_at = datetime.fromisoformat(
            recommendation["generated_at"]
        )

        if completed_at is None:
            completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        else:
            completed_at = datetime.fromisoformat(completed_at)

        if completed_at < generated_at:
            raise ValueError(
                "Activity cannot complete before recommendation"
            )

        started_at = max(
            generated_at,
            completed_at - timedelta(minutes=20)
        )

        latest_step = conn.execute(
            """
            SELECT recorded_at
            FROM learning_path_steps
            WHERE path_id = (
                SELECT path_id
                FROM recommendations
                WHERE recommendation_id = ?
            )
            ORDER BY step_number DESC
            LIMIT 1
            """,
            (recommendation_id,)
        ).fetchone()

        if latest_step is not None:
            if completed_at.isoformat() < latest_step["recorded_at"]:
                raise ValueError(
                    "Activity completion cannot occur before "
                    "the previous learning-path step"
                )

        learner_id = recommendation["learner_id"]
        skill_id = recommendation["target_skill_id"]

        mastery_before = get_skill_mastery(
            learner_id,
            skill_id,
            started_at.isoformat()
        )

        next_attempt = conn.execute(
            """
            SELECT COUNT(*) + 1
            FROM attempts
            WHERE learner_id = ?
            """,
            (learner_id,)
        ).fetchone()[0]

        attempt_id = (
            f"ATT-{learner_id}-{next_attempt:06d}"
        )

        next_result = conn.execute(
            "SELECT COUNT(*) + 1 FROM assessment_results"
        ).fetchone()[0]

        result_id = f"RES-{next_result:09d}"

        conn.execute(
            """
            INSERT INTO attempts
            (
                attempt_id,
                learner_id,
                content_id,
                recommendation_id,
                started_at,
                completed_at,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attempt_id,
                learner_id,
                recommendation["content_id"],
                recommendation_id,
                started_at.isoformat(),
                completed_at.isoformat(),
                "COMPLETED"
            )
        )

        conn.execute(
            """
            INSERT INTO assessment_results
            (
                result_id,
                attempt_id,
                score,
                assessed_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                result_id,
                attempt_id,
                score,
                completed_at.isoformat()
            )
        )

        conn.commit()

        mastery_after = get_skill_mastery(
            learner_id,
            skill_id,
            completed_at.isoformat()
        )

        next_event = conn.execute(
            """
            SELECT COUNT(*) + 1
            FROM recommendation_events
            """
        ).fetchone()[0]

        event_id = f"EVT-{next_event:09d}"

        conn.execute(
            """
            INSERT INTO recommendation_events
            (
                event_id,
                recommendation_id,
                event_type,
                occurred_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                event_id,
                recommendation_id,
                "COMPLETED",
                completed_at.isoformat()
            )
        )

        next_step = conn.execute(
            """
            SELECT COUNT(*) + 1
            FROM learning_path_steps
            """
        ).fetchone()[0]

        step_number = conn.execute(
            """
            SELECT COUNT(*) + 1
            FROM learning_path_steps
            WHERE path_id = (
                SELECT path_id
                FROM recommendations
                WHERE recommendation_id = ?
            )
            """,
            (recommendation_id,)
        ).fetchone()[0]

        path_id = conn.execute(
            """
            SELECT path_id
            FROM recommendations
            WHERE recommendation_id = ?
            """,
            (recommendation_id,)
        ).fetchone()[0]

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
                f"STEP-{next_step:09d}",
                path_id,
                recommendation["content_id"],
                step_number,
                mastery_before,
                mastery_after,
                completed_at.isoformat()
            )
        )

        conn.commit()

        improvement = round(
            mastery_after - mastery_before,
            4
        )

        return {
            "recommendation_id": recommendation_id,
            "attempt_id": attempt_id,
            "assessment_score": score,
            "mastery_before": mastery_before,
            "mastery_after": mastery_after,
            "mastery_improvement": improvement,
            "improved": improvement > 0,
            "status": "COMPLETED"
        }

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--recommendation",
        required=True
    )

    parser.add_argument(
        "--score",
        type=float,
        default=85
    )

    args = parser.parse_args()

    result = record_outcome(
        args.recommendation,
        args.score
    )

    for key, value in result.items():
        print(f"{key}: {value}")
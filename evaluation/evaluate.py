import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from app.database import get_connection
from app.mastery import calculate_mastery

BASE = Path(__file__).resolve().parent.parent
REPORTS = BASE / "reports"
REPORTS.mkdir(exist_ok=True)


def evaluate():
    conn = get_connection()

    try:
        rows = conn.execute(
            """
            SELECT
                a.learner_id,
                cs.skill_id,
                ar.score,
                ar.assessed_at,
                a.attempt_id
            FROM assessment_results ar
            JOIN attempts a
                ON ar.attempt_id = a.attempt_id
            JOIN content_skills cs
                ON a.content_id = cs.content_id
            WHERE a.status = 'COMPLETED'
              AND a.completed_at <= ar.assessed_at
            ORDER BY
                ar.assessed_at,
                a.attempt_id,
                cs.skill_id
            """
        ).fetchall()

        if not rows:
            raise RuntimeError("No assessment results found")

        timestamps = sorted(
            row["assessed_at"] for row in rows
        )

        cutoff = timestamps[int(len(timestamps) * 0.8)]

        history = defaultdict(list)
        test_records = []

        for row in rows:
            key = (
                row["learner_id"],
                row["skill_id"]
            )

            if row["assessed_at"] < cutoff:
                history[key].append(row["score"])
            else:
                test_records.append(row)

        errors = []
        predictions = 0

        for row in test_records:
            key = (
                row["learner_id"],
                row["skill_id"]
            )

            previous_scores = history.get(key, [])

            if not previous_scores:
                continue

            predicted = calculate_mastery(previous_scores) * 100
            actual = row["score"]

            errors.append(actual - predicted)
            predictions += 1

        if not errors:
            raise RuntimeError(
                "No test records have historical mastery evidence"
            )

        mae = sum(abs(error) for error in errors) / len(errors)

        rmse = math.sqrt(
            sum(error ** 2 for error in errors) / len(errors)
        )

        learner_count = conn.execute(
            "SELECT COUNT(*) FROM learners"
        ).fetchone()[0]

        active_learners = conn.execute(
            """
            SELECT COUNT(DISTINCT learner_id)
            FROM attempts
            WHERE started_at < ?
            """,
            (cutoff,)
        ).fetchone()[0]

        cold_start = learner_count - active_learners

        report = {
            "generated_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "temporal_cutoff": cutoff,
            "train_records": len(rows) - len(test_records),
            "test_records": len(test_records),
            "evaluated_predictions": predictions,
            "mae": round(mae, 4),
            "rmse": round(rmse, 4),
            "cold_start_learners": cold_start,
            "cold_start_rate": round(
                cold_start / learner_count,
                4
            ),
            "evaluation_method": "Temporal holdout with historical mastery"
        }

        output = REPORTS / "evaluation_report.json"

        output.write_text(
            json.dumps(report, indent=2),
            encoding="utf-8"
        )

        print("\n" + "=" * 55)
        print("LEARNPATH AI TEMPORAL EVALUATION")
        print("=" * 55)

        for key, value in report.items():
            print(f"{key}: {value}")

        print("=" * 55)

        return report

    finally:
        conn.close()


if __name__ == "__main__":
    evaluate()
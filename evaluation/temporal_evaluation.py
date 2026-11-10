import json
import math
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from app.database import get_connection


BASE = Path(__file__).resolve().parent.parent
REPORT_DIR = BASE / "reports"
REPORT_PATH = REPORT_DIR / "temporal_evaluation.json"


def calculate_metrics(actual, predicted):
    if not actual:
        return {
            "mae": None,
            "rmse": None,
            "accuracy_within_20_points": None
        }

    errors = [
        abs(a - p)
        for a, p in zip(actual, predicted)
    ]

    mae = sum(errors) / len(errors)

    rmse = math.sqrt(
        sum((a - p) ** 2 for a, p in zip(actual, predicted))
        / len(actual)
    )

    accuracy = sum(
        error <= 20 for error in errors
    ) / len(errors)

    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "accuracy_within_20_points": round(accuracy, 4)
    }


def run_evaluation():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    conn = get_connection()

    try:
        rows = conn.execute(
            """
            SELECT
                a.learner_id,
                cs.skill_id,
                a.completed_at,
                ar.score
            FROM attempts a
            JOIN assessment_results ar
                ON ar.attempt_id = a.attempt_id
            JOIN content_skills cs
                ON cs.content_id = a.content_id
            WHERE a.status = 'COMPLETED'
              AND a.completed_at IS NOT NULL
              AND ar.score IS NOT NULL
            ORDER BY
                a.learner_id,
                cs.skill_id,
                a.completed_at,
                a.attempt_id
            """
        ).fetchall()

        histories = defaultdict(list)

        for learner_id, skill_id, completed_at, score in rows:
            histories[(learner_id, skill_id)].append(
                (completed_at, float(score))
            )

        actual = []
        predicted = []

        evaluated_groups = 0

        for history in histories.values():
            if len(history) < 5:
                continue

            split = max(
                1,
                int(len(history) * 0.8)
            )

            training = history[:split]
            testing = history[split:]

            if not testing:
                continue

            training_scores = [
                score for _, score in training
            ]

            prediction = sum(
                training_scores[-5:]
            ) / len(training_scores[-5:])

            for _, score in testing:
                actual.append(score)
                predicted.append(prediction)

            evaluated_groups += 1

        metrics = calculate_metrics(
            actual,
            predicted
        )

        report = {
            "project": "YottaFlex LearnPath AI",
            "evaluation": "Temporal Holdout",
            "generated_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "split": "80% historical / 20% future within each learner-skill group",
            "prediction_method": "Mean of last five training assessment scores",
            "learner_skill_groups_evaluated": evaluated_groups,
            "future_assessments_evaluated": len(actual),
            "metrics": metrics
        }

        REPORT_PATH.write_text(
            json.dumps(report, indent=2),
            encoding="utf-8"
        )

        print("\nTEMPORAL EVALUATION RESULTS")
        print("=" * 45)
        print(f"Learner-skill groups: {evaluated_groups:,}")
        print(f"Future assessments: {len(actual):,}")
        print(f"MAE: {metrics['mae']}")
        print(f"RMSE: {metrics['rmse']}")
        print(
            "Accuracy within 20 points:",
            metrics["accuracy_within_20_points"]
        )
        print(f"Report: {REPORT_PATH}")

    finally:
        conn.close()


if __name__ == "__main__":
    run_evaluation()
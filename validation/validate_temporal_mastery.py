import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DATABASE = Path("data/learnpath.db")
REPORT = Path("reports/temporal_mastery_validation.json")


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def calculate_expected_mastery(scores):
    if not scores:
        return 0.0

    recent = scores[-5:]
    weights = range(1, len(recent) + 1)

    return round(
        sum(score * weight for score, weight in zip(recent, weights))
        / sum(weights)
        / 100,
        4,
    )


def main():
    if not DATABASE.exists():
        raise SystemExit(f"Database not found: {DATABASE}")

    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    recommendations = connection.execute(
        """
        SELECT
            recommendation_id,
            learner_id,
            target_skill_id,
            generated_at,
            mastery_at_decision
        FROM recommendations
        ORDER BY generated_at, recommendation_id
        """
    ).fetchall()

    results = []
    mismatches = []
    future_assessments_excluded = 0

    for recommendation in recommendations:
        learner_id = recommendation["learner_id"]
        skill_id = recommendation["target_skill_id"]
        decision_time = recommendation["generated_at"]

        assessments = connection.execute(
            """
            SELECT
                ar.score,
                ar.assessed_at,
                a.completed_at,
                a.attempt_id
            FROM assessment_results ar
            JOIN attempts a
                ON ar.attempt_id = a.attempt_id
            JOIN content_skills cs
                ON cs.content_id = a.content_id
            WHERE a.learner_id = ?
              AND cs.skill_id = ?
              AND a.status = 'COMPLETED'
            ORDER BY ar.assessed_at, a.attempt_id
            """,
            (learner_id, skill_id),
        ).fetchall()

        eligible = []

        for assessment in assessments:
            if (
                assessment["completed_at"] <= decision_time
                and assessment["assessed_at"] <= decision_time
            ):
                eligible.append(assessment)
            else:
                future_assessments_excluded += 1

        scores = [row["score"] for row in eligible]
        expected = calculate_expected_mastery(scores)

        recorded = recommendation["mastery_at_decision"]

        matched = (
            recorded is not None
            and abs(expected - recorded) <= 0.0001
        )

        item = {
            "recommendation_id": recommendation["recommendation_id"],
            "learner_id": learner_id,
            "skill_id": skill_id,
            "decision_time": decision_time,
            "eligible_assessment_count": len(eligible),
            "expected_mastery": expected,
            "recorded_mastery": recorded,
            "status": "PASS" if matched else "FAIL",
        }

        results.append(item)

        if not matched:
            mismatches.append(item)

    connection.close()

    report = {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "total_recommendations": len(results),
        "matched_recommendations": len(results) - len(mismatches),
        "mismatched_recommendations": len(mismatches),
        "future_assessments_excluded": future_assessments_excluded,
        "status": "PASS" if results and not mismatches else "FAIL",
        "mismatches": mismatches,
    }

    REPORT.parent.mkdir(parents=True, exist_ok=True)

    REPORT.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )

    print("\nTEMPORAL MASTERY VALIDATION")
    print("-" * 50)
    print("Recommendations checked:", len(results))
    print("Mastery values matched:", len(results) - len(mismatches))
    print("Mastery mismatches:", len(mismatches))
    print("Future assessments excluded:", future_assessments_excluded)
    print("Overall status:", report["status"])
    print("Report:", REPORT)

    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
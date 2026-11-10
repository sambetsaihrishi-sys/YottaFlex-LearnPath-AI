import json
from datetime import datetime, timezone
from pathlib import Path

from app.database import get_connection
from app.mastery import get_skill_mastery

BASE = Path(__file__).resolve().parent.parent
REPORTS = BASE / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)


def evaluate_recommendations():
    conn = get_connection()

    try:
        recommendations = conn.execute(
            """
            SELECT
                r.recommendation_id,
                r.learner_id,
                r.path_id,
                r.content_id,
                r.target_skill_id,
                r.generated_at,
                r.mastery_at_decision,
                r.reason_code,
                p.learner_id AS path_learner_id,
                p.course_id AS path_course_id,
                c.course_id AS content_course_id,
                s.course_id AS skill_course_id
            FROM recommendations r
            LEFT JOIN learning_paths p
                ON p.path_id = r.path_id
            LEFT JOIN content_items c
                ON c.content_id = r.content_id
            LEFT JOIN skills s
                ON s.skill_id = r.target_skill_id
            ORDER BY r.recommendation_id
            """
        ).fetchall()

        if not recommendations:
            raise RuntimeError(
                "No recommendations found. Generate recommendations first."
            )

        details = []
        failures = {
            "content_relevance": 0,
            "prerequisite_compliance": 0,
            "course_consistency": 0,
            "traceability": 0
        }

        for rec in recommendations:
            rec_id = rec["recommendation_id"]

            mapping = conn.execute(
                """
                SELECT 1
                FROM content_skills
                WHERE content_id = ?
                  AND skill_id = ?
                LIMIT 1
                """,
                (
                    rec["content_id"],
                    rec["target_skill_id"]
                )
            ).fetchone()

            content_relevant = mapping is not None

            prerequisites = conn.execute(
                """
                SELECT
                    required_skill_id,
                    minimum_mastery
                FROM skill_prerequisites
                WHERE skill_id = ?
                  AND status = 'ACTIVE'
                  AND effective_from <= ?
                  AND (
                      effective_to IS NULL
                      OR effective_to >= ?
                  )
                """,
                (
                    rec["target_skill_id"],
                    rec["generated_at"],
                    rec["generated_at"]
                )
            ).fetchall()

            prerequisite_violations = []

            for prerequisite in prerequisites:
                mastery = get_skill_mastery(
                    rec["learner_id"],
                    prerequisite["required_skill_id"],
                    as_of=rec["generated_at"]
                )

                if mastery < prerequisite["minimum_mastery"]:
                    prerequisite_violations.append({
                        "required_skill_id": prerequisite["required_skill_id"],
                        "actual_mastery": round(mastery, 4),
                        "required_mastery": prerequisite["minimum_mastery"]
                    })

            prerequisites_valid = (
                len(prerequisite_violations) == 0
            )

            course_consistent = (
                rec["path_course_id"] is not None
                and rec["path_course_id"] == rec["content_course_id"]
                and rec["content_course_id"] == rec["skill_course_id"]
            )

            generated_event = conn.execute(
                """
                SELECT 1
                FROM recommendation_events
                WHERE recommendation_id = ?
                  AND event_type = 'GENERATED'
                  AND occurred_at <= ?
                LIMIT 1
                """,
                (
                    rec_id,
                    rec["generated_at"]
                )
            ).fetchone()

            traceable = (
                rec["path_learner_id"] == rec["learner_id"]
                and generated_event is not None
            )

            checks = {
                "content_relevance": content_relevant,
                "prerequisite_compliance": prerequisites_valid,
                "course_consistency": course_consistent,
                "traceability": traceable
            }

            for name, passed in checks.items():
                if not passed:
                    failures[name] += 1

            details.append({
                "recommendation_id": rec_id,
                "checks": checks,
                "prerequisite_violations": prerequisite_violations,
                "passed": all(checks.values())
            })

        total = len(recommendations)

        metrics = {
            "content_relevance_rate": round(
                (total - failures["content_relevance"]) / total,
                4
            ),
            "prerequisite_compliance_rate": round(
                (total - failures["prerequisite_compliance"]) / total,
                4
            ),
            "course_consistency_rate": round(
                (total - failures["course_consistency"]) / total,
                4
            ),
            "traceability_rate": round(
                (total - failures["traceability"]) / total,
                4
            ),
            "fully_valid_rate": round(
                sum(item["passed"] for item in details) / total,
                4
            )
        }

        report = {
            "generated_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "total_recommendations": total,
            "metrics": metrics,
            "failures": failures,
            "details": details
        }

        output = REPORTS / "recommendation_evaluation.json"

        output.write_text(
            json.dumps(report, indent=2),
            encoding="utf-8"
        )

        print("\n" + "=" * 55)
        print("LEARNPATH AI RECOMMENDATION EVALUATION")
        print("=" * 55)
        print(f"Recommendations Evaluated: {total}")

        for name, value in metrics.items():
            print(f"{name}: {value * 100:.2f}%")

        print("-" * 55)

        for name, count in failures.items():
            print(f"{name} failures: {count}")

        print("=" * 55)

        return report

    finally:
        conn.close()


if __name__ == "__main__":
    evaluate_recommendations()
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path

from app.database import get_connection


BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_DIR = BASE_DIR / "reports"


def validate_database():
    conn = get_connection()

    try:
        checks = {}

        integrity = conn.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        checks["database_integrity"] = {
            "passed": integrity == "ok",
            "violations": 0 if integrity == "ok" else 1
        }

        fk_violations = conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        checks["foreign_keys"] = {
            "passed": len(fk_violations) == 0,
            "violations": len(fk_violations)
        }

        invalid_timestamps = conn.execute(
            """
            SELECT COUNT(*)
            FROM attempts
            WHERE completed_at IS NOT NULL
              AND completed_at < started_at
            """
        ).fetchone()[0]

        checks["attempt_timestamps"] = {
            "passed": invalid_timestamps == 0,
            "violations": invalid_timestamps
        }

        invalid_scores = conn.execute(
            """
            SELECT COUNT(*)
            FROM assessment_results
            WHERE score < 0 OR score > 100
            """
        ).fetchone()[0]

        checks["assessment_scores"] = {
            "passed": invalid_scores == 0,
            "violations": invalid_scores
        }

        invalid_mastery = conn.execute(
            """
            SELECT COUNT(*)
            FROM mastery_snapshots
            WHERE mastery_score < 0
               OR mastery_score > 1
            """
        ).fetchone()[0]

        checks["mastery_range"] = {
            "passed": invalid_mastery == 0,
            "violations": invalid_mastery
        }

        future_mastery = conn.execute(
            """
            SELECT COUNT(*)
            FROM recommendations r
            JOIN attempts a
              ON a.learner_id = r.learner_id
            JOIN content_skills cs
              ON cs.content_id = a.content_id
             AND cs.skill_id = r.target_skill_id
            JOIN assessment_results ar
              ON ar.attempt_id = a.attempt_id
            WHERE ar.assessed_at > r.generated_at
              AND r.mastery_at_decision < 0
            """
        ).fetchone()[0]

        checks["future_mastery_marker"] = {
            "passed": future_mastery == 0,
            "violations": future_mastery
        }

        duplicate_content_skills = conn.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT content_id, skill_id
                FROM content_skills
                GROUP BY content_id, skill_id
                HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]

        checks["duplicate_content_skill_mappings"] = {
            "passed": duplicate_content_skills == 0,
            "violations": duplicate_content_skills
        }

        total_checks = len(checks)
        passed_checks = sum(
            result["passed"]
            for result in checks.values()
        )

        report = {
            "generated_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "failed_checks": total_checks - passed_checks,
            "status": (
                "PASS"
                if passed_checks == total_checks
                else "FAIL"
            ),
            "checks": checks
        }

        REPORT_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        output_path = (
            REPORT_DIR / "validation_report.json"
        )

        output_path.write_text(
            json.dumps(report, indent=2),
            encoding="utf-8"
        )

        return report

    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.parse_args()

    result = validate_database()

    print("\n" + "=" * 55)
    print("LEARNPATH AI DATA VALIDATION")
    print("=" * 55)

    for name, check in result["checks"].items():
        status = "PASS" if check["passed"] else "FAIL"

        print(
            f"{name:<38} "
            f"{status:<6} "
            f"Violations: {check['violations']}"
        )

    print("-" * 55)
    print(f"Total Checks: {result['total_checks']}")
    print(f"Passed: {result['passed_checks']}")
    print(f"Failed: {result['failed_checks']}")
    print(f"Overall Status: {result['status']}")
    print("=" * 55)
import json
from pathlib import Path

from app.database import get_connection
from app.mastery import get_skill_mastery

BASE = Path(__file__).resolve().parent.parent
OUTPUT = BASE / "reports"
OUTPUT.mkdir(exist_ok=True)

AS_OF = "2026-05-01T12:00:00"


def detect_prerequisite_violation(case):
    return case["prerequisite_mastery"] < case["required_mastery"]


def detect_invalid_timestamp(case):
    return case["completed_at"] < case["started_at"]


def detect_missing_skill(case, valid_skills):
    return case["skill_id"] not in valid_skills


def detect_future_leakage(case):
    return case["evidence_timestamp"] > case["decision_timestamp"]


def detect_no_progress_loop(case):
    steps = case["steps"]

    for index in range(1, len(steps)):
        previous = steps[index - 1]
        current = steps[index]

        if (
            current["content_id"] == previous["content_id"]
            and current["mastery_after"] <= previous["mastery_after"]
        ):
            return True

    return False


def build_cases():
    conn = get_connection()

    try:
        skills = {
            row["skill_id"]
            for row in conn.execute("SELECT skill_id FROM skills")
        }

        prerequisite = conn.execute(
            """
            SELECT skill_id, required_skill_id, minimum_mastery
            FROM skill_prerequisites
            ORDER BY prerequisite_id
            LIMIT 1
            """
        ).fetchone()

        if prerequisite is None:
            raise RuntimeError("No prerequisites found")

        cases = [
            {
                "case_id": "NEG-001",
                "type": "PREREQUISITE_VIOLATION",
                "skill_id": prerequisite["skill_id"],
                "required_skill_id": prerequisite["required_skill_id"],
                "prerequisite_mastery": 0.20,
                "required_mastery": prerequisite["minimum_mastery"]
            },
            {
                "case_id": "NEG-002",
                "type": "INVALID_ATTEMPT_TIMESTAMP",
                "started_at": "2026-05-10T12:00:00",
                "completed_at": "2026-05-10T11:00:00"
            },
            {
                "case_id": "NEG-003",
                "type": "MISSING_SKILL_REFERENCE",
                "content_id": "CNT-000001",
                "skill_id": "SKL-999999"
            },
            {
                "case_id": "NEG-004",
                "type": "FUTURE_MASTERY_LEAKAGE",
                "decision_timestamp": "2026-05-01T12:00:00",
                "evidence_timestamp": "2026-05-02T12:00:00"
            },
            {
                "case_id": "NEG-005",
                "type": "LEARNING_PATH_NO_PROGRESS_LOOP",
                "steps": [
                    {
                        "content_id": "CNT-000001",
                        "mastery_after": 0.40
                    },
                    {
                        "content_id": "CNT-000001",
                        "mastery_after": 0.40
                    },
                    {
                        "content_id": "CNT-000001",
                        "mastery_after": 0.40
                    }
                ]
            }
        ]

        return cases, skills

    finally:
        conn.close()


def detect_case(case, valid_skills):
    case_type = case["type"]

    if case_type == "PREREQUISITE_VIOLATION":
        return detect_prerequisite_violation(case)

    if case_type == "INVALID_ATTEMPT_TIMESTAMP":
        return detect_invalid_timestamp(case)

    if case_type == "MISSING_SKILL_REFERENCE":
        return detect_missing_skill(case, valid_skills)

    if case_type == "FUTURE_MASTERY_LEAKAGE":
        return detect_future_leakage(case)

    if case_type == "LEARNING_PATH_NO_PROGRESS_LOOP":
        return detect_no_progress_loop(case)

    return False


def run_validation():
    cases, valid_skills = build_cases()

    ground_truth = [
        {
            "case_id": case["case_id"],
            "expected_label": case["type"]
        }
        for case in cases
    ]

    detections = []

    for case in cases:
        detected = detect_case(case, valid_skills)

        detections.append({
            "case_id": case["case_id"],
            "detected": detected,
            "detected_label": case["type"] if detected else None
        })

    results = {
        "total_cases": len(cases),
        "detected_cases": sum(
            item["detected"] for item in detections
        ),
        "detections": detections
    }

    (OUTPUT / "negative_cases.json").write_text(
        json.dumps(cases, indent=2),
        encoding="utf-8"
    )

    (OUTPUT / "ground_truth.json").write_text(
        json.dumps(ground_truth, indent=2),
        encoding="utf-8"
    )

    (OUTPUT / "negative_validation_report.json").write_text(
        json.dumps(results, indent=2),
        encoding="utf-8"
    )

    print("\n" + "=" * 55)
    print("NEGATIVE SCENARIO VALIDATION")
    print("=" * 55)

    for result in detections:
        status = "DETECTED" if result["detected"] else "MISSED"
        print(f"{result['case_id']}: {status}")

    print("-" * 55)
    print(f"Total Cases: {results['total_cases']}")
    print(f"Detected: {results['detected_cases']}")
    print("=" * 55)

    return results


if __name__ == "__main__":
    run_validation()
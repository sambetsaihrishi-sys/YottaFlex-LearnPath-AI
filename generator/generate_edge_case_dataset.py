import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

from app.database import DB_PATH, get_connection
from validation.negative_case_benchmark import detect_issues, evaluate

OUTPUT = Path("reports/injected_edge_cases")


def required_row(conn, query, params=()):
    row = conn.execute(query, params).fetchone()

    if row is None:
        raise RuntimeError(
            "Required baseline records not found; "
            "generate the dataset and mastery snapshots first"
        )

    return dict(row)


def create_cases(conn):
    prerequisite = required_row(
        conn,
        "SELECT prerequisite_id, skill_id, required_skill_id, "
        "minimum_mastery, status, effective_from, effective_to "
        "FROM skill_prerequisites "
        "WHERE status = 'ACTIVE' "
        "ORDER BY prerequisite_id LIMIT 1"
    )

    attempt = required_row(
        conn,
        "SELECT a.attempt_id, a.learner_id, a.content_id, "
        "a.started_at, a.completed_at, a.status "
        "FROM attempts a "
        "WHERE a.status = 'COMPLETED' "
        "ORDER BY a.attempt_id LIMIT 1"
    )

    mapping = required_row(
        conn,
        "SELECT mapping_id, content_id, skill_id "
        "FROM content_skills "
        "ORDER BY mapping_id LIMIT 1"
    )

    snapshot = required_row(
        conn,
        "SELECT snapshot_id, learner_id, skill_id, calculated_at "
        "FROM mastery_snapshots "
        "ORDER BY snapshot_id LIMIT 1"
    )

    assessment = required_row(
        conn,
        "SELECT ar.result_id, ar.assessed_at "
        "FROM assessment_results ar "
        "JOIN attempts a ON a.attempt_id = ar.attempt_id "
        "JOIN content_skills cs ON cs.content_id = a.content_id "
        "WHERE a.learner_id = ? "
        "AND cs.skill_id = ? "
        "AND ar.assessed_at <= ? "
        "ORDER BY ar.assessed_at LIMIT 1",
        (
            snapshot["learner_id"],
            snapshot["skill_id"],
            snapshot["calculated_at"]
        )
    )

    second_content = required_row(
        conn,
        "SELECT content_id FROM content_items "
        "WHERE content_id != ? "
        "ORDER BY content_id LIMIT 1",
        (mapping["content_id"],)
    )["content_id"]

    known_skills = [
        row["skill_id"]
        for row in conn.execute(
            "SELECT skill_id FROM skills"
        )
    ]

    decision_time = "2026-10-22T12:00:00"

    decision = {
        "recommendation": {
            "target_skill_id": prerequisite["skill_id"],
            "generated_at": decision_time
        },
        "prerequisites": [prerequisite]
    }

    threshold = prerequisite["minimum_mastery"]

    invalid_attempt = dict(attempt)

    invalid_attempt["completed_at"] = (
        datetime.fromisoformat(attempt["started_at"])
        - timedelta(minutes=1)
    ).isoformat()

    invalid_mapping = dict(mapping)
    invalid_mapping["skill_id"] = "SKL-999999"

    future_assessment = dict(assessment)

    future_assessment["assessed_at"] = (
        datetime.fromisoformat(snapshot["calculated_at"])
        + timedelta(days=1)
    ).isoformat()

    snapshot_input = {
        "calculated_at": snapshot["calculated_at"],
        "source_assessment_ids": [
            assessment["result_id"]
        ]
    }

    steps = [
        {
            "step_number": 1,
            "content_id": mapping["content_id"],
            "mastery_before": 0.5,
            "mastery_after": 0.5
        },
        {
            "step_number": 2,
            "content_id": second_content,
            "mastery_before": 0.5,
            "mastery_after": 0.5
        },
        {
            "step_number": 3,
            "content_id": mapping["content_id"],
            "mastery_before": 0.5,
            "mastery_after": 0.5
        }
    ]

    improved_steps = [
        dict(step)
        for step in steps
    ]

    improved_steps[1]["mastery_after"] = 0.6

    return [
        (
            "NEG-001",
            {
                **decision,
                "mastery_by_skill": {
                    prerequisite["required_skill_id"]:
                        max(0, threshold - 0.2)
                }
            },
            ["PREREQUISITE_VIOLATION"],
            prerequisite["prerequisite_id"]
        ),
        (
            "OK-001",
            {
                **decision,
                "mastery_by_skill": {
                    prerequisite["required_skill_id"]:
                        min(1, threshold + 0.2)
                }
            },
            [],
            prerequisite["prerequisite_id"]
        ),
        (
            "NEG-002",
            {
                "attempt": invalid_attempt
            },
            ["INVALID_ATTEMPT_TIMESTAMPS"],
            attempt["attempt_id"]
        ),
        (
            "OK-002",
            {
                "attempt": attempt
            },
            [],
            attempt["attempt_id"]
        ),
        (
            "NEG-003",
            {
                "known_skill_ids": known_skills,
                "content_skill_mappings": [
                    invalid_mapping
                ]
            },
            ["UNKNOWN_SKILL_REFERENCE"],
            mapping["mapping_id"]
        ),
        (
            "OK-003",
            {
                "known_skill_ids": known_skills,
                "content_skill_mappings": [
                    mapping
                ]
            },
            [],
            mapping["mapping_id"]
        ),
        (
            "NEG-004",
            {
                "mastery_snapshot": snapshot_input,
                "assessments": [
                    future_assessment
                ]
            },
            ["FUTURE_MASTERY_LEAKAGE"],
            snapshot["snapshot_id"]
        ),
        (
            "OK-004",
            {
                "mastery_snapshot": snapshot_input,
                "assessments": [
                    assessment
                ]
            },
            [],
            snapshot["snapshot_id"]
        ),
        (
            "NEG-005",
            {
                "learning_path_steps": steps
            },
            ["PATH_LOOP_NO_PROGRESS"],
            mapping["content_id"]
        ),
        (
            "OK-005",
            {
                "learning_path_steps": improved_steps
            },
            [],
            mapping["content_id"]
        )
    ]


def main():
    if not DB_PATH.exists():
        raise SystemExit(
            f"Database not found: {DB_PATH}"
        )

    conn = get_connection()

    try:
        cases = create_cases(conn)

    finally:
        conn.close()

    result = evaluate([
        (case_id, data, labels)
        for case_id, data, labels, _ in cases
    ])

    OUTPUT.mkdir(
        parents=True,
        exist_ok=True
    )

    inputs = [
        {
            "case_id": case_id,
            "source_record_id": source_id,
            "data": data
        }
        for case_id, data, _, source_id in cases
    ]

    truth = [
        {
            "case_id": case_id,
            "source_record_id": source_id,
            "is_anomaly": bool(labels),
            "expected_issues": labels
        }
        for case_id, _, labels, source_id in cases
    ]

    (OUTPUT / "inputs.json").write_text(
        json.dumps(inputs, indent=2) + "\n",
        encoding="utf-8"
    )

    (OUTPUT / "ground_truth.json").write_text(
        json.dumps(truth, indent=2) + "\n",
        encoding="utf-8"
    )

    (OUTPUT / "validation_report.json").write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8"
    )

    with (OUTPUT / "ground_truth.csv").open(
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=[
                "case_id",
                "source_record_id",
                "is_anomaly",
                "expected_issues"
            ]
        )

        writer.writeheader()

        for row in truth:
            writer.writerow({
                **row,
                "expected_issues": ";".join(
                    row["expected_issues"]
                )
            })

    print(
        f"Cases: {result['total_cases']}"
    )

    print(
        f"Exact matches: "
        f"{result['exact_matches']}/"
        f"{result['total_cases']}"
    )

    print(
        f"Precision: {result['precision']:.2%}"
    )

    print(
        f"Recall: {result['recall']:.2%}"
    )

    print(
        f"Output: {OUTPUT}"
    )

    if result["exact_matches"] != result["total_cases"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
import csv
import json
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path("reports/negative_cases")


def parsed(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def detect_issues(data):
    issues = set()

    if "recommendation" in data and "prerequisites" in data:
        recommendation = data["recommendation"]
        decision_time = parsed(recommendation["generated_at"])

        for rule in data["prerequisites"]:
            if rule["skill_id"] != recommendation["target_skill_id"]:
                continue

            if rule["status"] != "ACTIVE":
                continue

            if parsed(rule["effective_from"]) > decision_time:
                continue

            if rule.get("effective_to") and parsed(
                rule["effective_to"]
            ) < decision_time:
                continue

            actual = data["mastery_by_skill"].get(
                rule["required_skill_id"], 0.0
            )

            if actual < rule["minimum_mastery"]:
                issues.add("PREREQUISITE_VIOLATION")

    if "attempt" in data:
        attempt = data["attempt"]
        start = parsed(attempt["started_at"])
        end = attempt.get("completed_at")

        if (
            end is not None and parsed(end) < start
        ) or (
            attempt["status"] == "COMPLETED" and end is None
        ):
            issues.add("INVALID_ATTEMPT_TIMESTAMPS")

    if "content_skill_mappings" in data:
        known_skills = set(data["known_skill_ids"])

        if any(
            row["skill_id"] not in known_skills
            for row in data["content_skill_mappings"]
        ):
            issues.add("UNKNOWN_SKILL_REFERENCE")

    if "mastery_snapshot" in data:
        snapshot = data["mastery_snapshot"]
        as_of = parsed(snapshot["calculated_at"])

        assessments = {
            item["result_id"]: item
            for item in data["assessments"]
        }

        if any(
            result_id not in assessments
            or parsed(assessments[result_id]["assessed_at"]) > as_of
            for result_id in snapshot["source_assessment_ids"]
        ):
            issues.add("FUTURE_MASTERY_LEAKAGE")

    if "learning_path_steps" in data:
        steps = sorted(
            data["learning_path_steps"],
            key=lambda x: x["step_number"]
        )

        last_seen = {}

        for index, step in enumerate(steps):
            content_id = step["content_id"]

            if content_id in last_seen:
                first_index = last_seen[content_id]
                segment = steps[first_index:index + 1]

                made_progress = any(
                    item["mastery_after"] > item["mastery_before"]
                    for item in segment
                )

                if not made_progress:
                    issues.add("PATH_LOOP_NO_PROGRESS")

            last_seen[content_id] = index

    return sorted(issues)


def build_cases():
    time = "2026-10-22T12:00:00"

    prerequisite = {
        "skill_id": "SKL-000002",
        "required_skill_id": "SKL-000001",
        "minimum_mastery": 0.70,
        "status": "ACTIVE",
        "effective_from": "2026-01-01T00:00:00",
        "effective_to": None,
    }

    decision = {
        "recommendation": {
            "target_skill_id": "SKL-000002",
            "generated_at": time,
        },
        "prerequisites": [prerequisite],
    }

    attempt = {
        "started_at": "2026-10-22T10:00:00",
        "completed_at": "2026-10-22T10:30:00",
        "status": "COMPLETED",
    }

    mapping = {
        "known_skill_ids": [
            "SKL-000001",
            "SKL-000002"
        ],
    }

    snapshot = {
        "mastery_snapshot": {
            "calculated_at": time,
            "source_assessment_ids": ["RES-000001"],
        },
    }

    no_progress_steps = [
        {
            "step_number": 1,
            "content_id": "CNT-000001",
            "mastery_before": 0.5,
            "mastery_after": 0.5,
        },
        {
            "step_number": 2,
            "content_id": "CNT-000002",
            "mastery_before": 0.5,
            "mastery_after": 0.5,
        },
        {
            "step_number": 3,
            "content_id": "CNT-000001",
            "mastery_before": 0.5,
            "mastery_after": 0.5,
        },
    ]

    improved_steps = [
        dict(step)
        for step in no_progress_steps
    ]

    improved_steps[1]["mastery_after"] = 0.6

    return [
        (
            "NEG-001",
            {
                **decision,
                "mastery_by_skill": {
                    "SKL-000001": 0.45
                },
            },
            ["PREREQUISITE_VIOLATION"],
        ),
        (
            "OK-001",
            {
                **decision,
                "mastery_by_skill": {
                    "SKL-000001": 0.85
                },
            },
            [],
        ),
        (
            "NEG-002",
            {
                "attempt": {
                    **attempt,
                    "completed_at": "2026-10-22T09:55:00",
                }
            },
            ["INVALID_ATTEMPT_TIMESTAMPS"],
        ),
        (
            "OK-002",
            {
                "attempt": attempt
            },
            [],
        ),
        (
            "NEG-003",
            {
                **mapping,
                "content_skill_mappings": [
                    {
                        "content_id": "CNT-000001",
                        "skill_id": "SKL-999999",
                    }
                ],
            },
            ["UNKNOWN_SKILL_REFERENCE"],
        ),
        (
            "OK-003",
            {
                **mapping,
                "content_skill_mappings": [
                    {
                        "content_id": "CNT-000001",
                        "skill_id": "SKL-000001",
                    }
                ],
            },
            [],
        ),
        (
            "NEG-004",
            {
                **snapshot,
                "assessments": [
                    {
                        "result_id": "RES-000001",
                        "assessed_at": "2026-10-23T08:00:00",
                    }
                ],
            },
            ["FUTURE_MASTERY_LEAKAGE"],
        ),
        (
            "OK-004",
            {
                **snapshot,
                "assessments": [
                    {
                        "result_id": "RES-000001",
                        "assessed_at": "2026-10-22T11:00:00",
                    }
                ],
            },
            [],
        ),
        (
            "NEG-005",
            {
                "learning_path_steps": no_progress_steps
            },
            ["PATH_LOOP_NO_PROGRESS"],
        ),
        (
            "OK-005",
            {
                "learning_path_steps": improved_steps
            },
            [],
        ),
    ]


def evaluate(cases):
    tp = 0
    fp = 0
    tn = 0
    fn = 0
    exact = 0

    predictions = []

    for case_id, inputs, expected in cases:
        detected = detect_issues(inputs)

        match = detected == expected
        exact += int(match)

        if expected and detected:
            tp += 1
        elif not expected and detected:
            fp += 1
        elif expected and not detected:
            fn += 1
        else:
            tn += 1

        predictions.append({
            "case_id": case_id,
            "detected_issues": detected,
            "status": "PASS" if match else "FAIL",
        })

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0

    return {
        "scope": (
            "10 isolated synthetic fixtures "
            "(5 negative, 5 valid controls); "
            "not production detection performance"
        ),
        "total_cases": len(cases),
        "exact_matches": exact,
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "precision": precision,
        "recall": recall,
        "predictions": predictions,
    }


def main():
    cases = build_cases()

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    inputs = [
        {
            "case_id": case_id,
            "data": data
        }
        for case_id, data, _ in cases
    ]

    ground_truth = [
        {
            "case_id": case_id,
            "is_anomaly": bool(expected),
            "expected_issues": expected,
        }
        for case_id, _, expected in cases
    ]

    report = evaluate(cases)

    (OUTPUT_DIR / "inputs.json").write_text(
        json.dumps(inputs, indent=2) + "\n",
        encoding="utf-8",
    )

    (OUTPUT_DIR / "ground_truth.json").write_text(
        json.dumps(ground_truth, indent=2) + "\n",
        encoding="utf-8",
    )

    with (
        OUTPUT_DIR / "ground_truth.csv"
    ).open(
        "w",
        encoding="utf-8",
        newline=""
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=[
                "case_id",
                "is_anomaly",
                "expected_issues",
            ],
        )

        writer.writeheader()

        for row in ground_truth:
            writer.writerow({
                **row,
                "expected_issues": ";".join(
                    row["expected_issues"]
                ),
            })

    (
        OUTPUT_DIR / "validation_report.json"
    ).write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )

    print("\nNEGATIVE-CASE BENCHMARK")
    print("-" * 50)

    for item in report["predictions"]:
        print(
            f"{item['case_id']:<10} "
            f"{item['status']:<5} "
            f"{', '.join(item['detected_issues']) or 'valid control'}"
        )

    print(
        f"\nExact matches: "
        f"{report['exact_matches']}/{report['total_cases']}"
    )

    print(
        f"Precision: {report['precision']:.2%}"
    )

    print(
        f"Recall: {report['recall']:.2%}"
    )

    print(
        f"Report folder: {OUTPUT_DIR}"
    )

    if report["exact_matches"] != report["total_cases"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
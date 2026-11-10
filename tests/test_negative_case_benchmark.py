from validation.negative_case_benchmark import (
    build_cases,
    detect_issues,
    evaluate,
)


def test_five_required_anomalies_and_five_valid_controls():
    cases = build_cases()

    assert len(cases) == 10

    assert sum(
        bool(expected)
        for _, _, expected in cases
    ) == 5

    assert sum(
        not expected
        for _, _, expected in cases
    ) == 5

    for _, data, expected in cases:
        assert detect_issues(data) == expected


def test_ground_truth_is_not_part_of_detector_inputs():
    for _, data, _ in build_cases():
        assert "expected_issues" not in data
        assert "is_anomaly" not in data
        assert "issue_type" not in data


def test_fixture_benchmark_has_no_false_positives_or_negatives():
    result = evaluate(build_cases())

    assert result["exact_matches"] == 10
    assert result["true_positives"] == 5
    assert result["true_negatives"] == 5
    assert result["false_positives"] == 0
    assert result["false_negatives"] == 0
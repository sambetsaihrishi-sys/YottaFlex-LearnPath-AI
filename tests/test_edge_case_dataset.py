from app.database import get_connection
from generator.generate_edge_case_dataset import create_cases
from validation.negative_case_benchmark import detect_issues, evaluate


def test_database_linked_edge_cases():
    conn = get_connection()

    try:
        cases = create_cases(conn)
    finally:
        conn.close()

    assert len(cases) == 10

    negative_cases = [
        case for case in cases if case[2]
    ]

    valid_cases = [
        case for case in cases if not case[2]
    ]

    assert len(negative_cases) == 5
    assert len(valid_cases) == 5

    for case_id, data, expected, source_id in cases:
        assert case_id
        assert source_id
        assert detect_issues(data) == expected
        assert "expected_issues" not in data
        assert "is_anomaly" not in data

    result = evaluate([
        (case_id, data, expected)
        for case_id, data, expected, _ in cases
    ])

    assert result["exact_matches"] == 10
    assert result["false_positives"] == 0
    assert result["false_negatives"] == 0
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DATABASE = Path("data/learnpath.db")
REPORT = Path("reports/relationship_validation.json")


def connect():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def count(connection, query):
    return connection.execute(query).fetchone()[0]


def find_cycles(connection):
    rows = connection.execute(
        """
        SELECT skill_id, required_skill_id
        FROM skill_prerequisites
        WHERE status = 'ACTIVE'
        """
    ).fetchall()

    graph = {}

    for row in rows:
        graph.setdefault(row["skill_id"], []).append(
            row["required_skill_id"]
        )

    visited = set()
    active = set()
    cycles = []

    def visit(node, path):
        if node in active:
            start = path.index(node)
            cycles.append(path[start:] + [node])
            return

        if node in visited:
            return

        active.add(node)

        for neighbor in graph.get(node, []):
            visit(neighbor, path + [neighbor])

        active.remove(node)
        visited.add(node)

    for node in graph:
        if node not in visited:
            visit(node, [node])

    return cycles


def main():
    if not DATABASE.exists():
        raise SystemExit("Database not found")

    connection = connect()

    checks = {
        "cross_course_content_skill": """
            SELECT COUNT(*)
            FROM content_skills cs
            JOIN content_items c ON c.content_id = cs.content_id
            JOIN skills s ON s.skill_id = cs.skill_id
            WHERE c.course_id != s.course_id
        """,
        "recommendation_wrong_learner_path": """
            SELECT COUNT(*)
            FROM recommendations r
            JOIN learning_paths p ON p.path_id = r.path_id
            WHERE r.learner_id != p.learner_id
        """,
        "recommendation_wrong_course": """
            SELECT COUNT(*)
            FROM recommendations r
            JOIN learning_paths p ON p.path_id = r.path_id
            JOIN content_items c ON c.content_id = r.content_id
            JOIN skills s ON s.skill_id = r.target_skill_id
            WHERE p.course_id != c.course_id
               OR p.course_id != s.course_id
        """,
        "assessment_on_unfinished_attempt": """
            SELECT COUNT(*)
            FROM assessment_results ar
            JOIN attempts a ON a.attempt_id = ar.attempt_id
            WHERE a.status != 'COMPLETED'
        """,
        "assessment_before_completion": """
            SELECT COUNT(*)
            FROM assessment_results ar
            JOIN attempts a ON a.attempt_id = ar.attempt_id
            WHERE a.completed_at IS NULL
               OR ar.assessed_at < a.completed_at
        """,
        "attempt_recommendation_wrong_learner": """
            SELECT COUNT(*)
            FROM attempts a
            JOIN recommendations r
              ON r.recommendation_id = a.recommendation_id
            WHERE a.learner_id != r.learner_id
        """,
        "attempt_recommendation_wrong_content": """
            SELECT COUNT(*)
            FROM attempts a
            JOIN recommendations r
              ON r.recommendation_id = a.recommendation_id
            WHERE a.content_id != r.content_id
        """,
        "unmapped_recommendation_skill": """
            SELECT COUNT(*)
            FROM recommendations r
            WHERE NOT EXISTS (
                SELECT 1
                FROM content_skills cs
                WHERE cs.content_id = r.content_id
                  AND cs.skill_id = r.target_skill_id
            )
        """,
    }

    results = {}

    for name, query in checks.items():
        violations = count(connection, query)
        results[name] = {
            "violations": violations,
            "status": "PASS" if violations == 0 else "FAIL",
        }

    cycles = find_cycles(connection)

    results["prerequisite_cycles"] = {
        "violations": len(cycles),
        "status": "PASS" if not cycles else "FAIL",
        "examples": cycles[:5],
    }

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        json.dumps(results, indent=2),
        encoding="utf-8",
    )

    print("\nRELATIONSHIP VALIDATION")
    print("-" * 60)

    for name, result in results.items():
        print(
            f"{name:<43} "
            f"{result['status']:<6} "
            f"{result['violations']}"
        )

    connection.close()

    failed = [
        name
        for name, result in results.items()
        if result["status"] == "FAIL"
    ]

    print("\nFailed checks:", len(failed))
    print("Report:", REPORT)

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
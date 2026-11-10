from datetime import datetime

from app.database import get_connection


def validate_path_chronology():
    conn = get_connection()

    try:
        rows = conn.execute(
            """
            SELECT
                path_id,
                step_id,
                step_number,
                recorded_at
            FROM learning_path_steps
            ORDER BY path_id, step_number
            """
        ).fetchall()

        violations = []
        previous = {}

        for row in rows:
            path_id = row["path_id"]
            current_time = datetime.fromisoformat(
                row["recorded_at"]
            )

            if path_id in previous:
                previous_step, previous_time = previous[path_id]

                if current_time < previous_time:
                    violations.append({
                        "path_id": path_id,
                        "previous_step": previous_step,
                        "current_step": row["step_number"],
                        "previous_time": previous_time.isoformat(),
                        "current_time": current_time.isoformat()
                    })

            previous[path_id] = (
                row["step_number"],
                current_time
            )

        print("\nLEARNING PATH CHRONOLOGY VALIDATION")
        print("-" * 50)
        print(f"Steps checked: {len(rows)}")
        print(f"Chronology violations: {len(violations)}")

        for violation in violations:
            print(
                f"FAIL: {violation['path_id']} | "
                f"Step {violation['previous_step']} -> "
                f"Step {violation['current_step']}"
            )

        if violations:
            print("Overall: FAIL")
        else:
            print("Overall: PASS")

        return violations

    finally:
        conn.close()


if __name__ == "__main__":
    issues = validate_path_chronology()

    if issues:
        raise SystemExit(1)
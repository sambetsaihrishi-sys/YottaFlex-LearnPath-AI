import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_PATH = BASE_DIR / "reports" / "reproducibility_validation.json"

TABLES = [
    "learners",
    "courses",
    "skills",
    "skill_prerequisites",
    "content_items",
    "content_skills",
    "attempts",
    "assessment_results",
]


def execute_generator(module, scale, database_path):
    environment = os.environ.copy()
    environment["LEARNPATH_DB_PATH"] = str(database_path)
    environment["PYTHONHASHSEED"] = "0"

    command = [
        sys.executable,
        "-m",
        module,
        "--scale",
        scale,
    ]

    print(f"\nRunning {module} ({scale})", flush=True)

    subprocess.run(
        command,
        cwd=BASE_DIR,
        env=environment,
        check=True,
    )


def calculate_table_hash(connection, table):
    columns = [
        row["name"]
        for row in connection.execute(
            f"PRAGMA table_info({table})"
        )
    ]

    primary_key = next(
        (
            row["name"]
            for row in connection.execute(
                f"PRAGMA table_info({table})"
            )
            if row["pk"] == 1
        ),
        columns[0],
    )

    digest = hashlib.sha256()

    cursor = connection.execute(
        f"SELECT * FROM {table} ORDER BY {primary_key}"
    )

    for row in cursor:
        values = [row[column] for column in columns]

        encoded = json.dumps(
            values,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)

    return digest.hexdigest()


def inspect_database(database_path):
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row

    try:
        results = {}

        for table in TABLES:
            count = connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]

            results[table] = {
                "row_count": count,
                "sha256": calculate_table_hash(
                    connection,
                    table,
                ),
            }

        foreign_key_violations = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        integrity = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        return {
            "tables": results,
            "foreign_key_violations": len(
                foreign_key_violations
            ),
            "integrity_check": integrity,
        }

    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--scale",
        choices=["starter", "full"],
        default="starter",
    )

    args = parser.parse_args()

    production_database = (
        BASE_DIR / "data" / "learnpath.db"
    ).resolve()

    with tempfile.TemporaryDirectory(
        prefix="learnpath_repro_"
    ) as directory:
        temporary_directory = Path(directory)

        database_a = temporary_directory / "run_a.db"
        database_b = temporary_directory / "run_b.db"

        for database in [database_a, database_b]:
            if database.resolve() == production_database:
                raise RuntimeError(
                    "Refusing to overwrite production database"
                )

            execute_generator(
                "generator.generate_master",
                args.scale,
                database,
            )

            execute_generator(
                "generator.generate_attempts",
                args.scale,
                database,
            )

        first = inspect_database(database_a)
        second = inspect_database(database_b)

    comparisons = {}

    for table in TABLES:
        first_table = first["tables"][table]
        second_table = second["tables"][table]

        count_match = (
            first_table["row_count"]
            == second_table["row_count"]
        )

        hash_match = (
            first_table["sha256"]
            == second_table["sha256"]
        )

        comparisons[table] = {
            "run_a_count": first_table["row_count"],
            "run_b_count": second_table["row_count"],
            "run_a_sha256": first_table["sha256"],
            "run_b_sha256": second_table["sha256"],
            "count_match": count_match,
            "hash_match": hash_match,
            "status": (
                "PASS"
                if count_match and hash_match
                else "FAIL"
            ),
        }

    integrity_passed = (
        first["foreign_key_violations"] == 0
        and second["foreign_key_violations"] == 0
        and first["integrity_check"] == "ok"
        and second["integrity_check"] == "ok"
    )

    all_tables_match = all(
        item["status"] == "PASS"
        for item in comparisons.values()
    )

    passed = integrity_passed and all_tables_match

    report = {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "seed": 20261022,
        "scale": args.scale,
        "independent_runs": 2,
        "production_database_modified": False,
        "integrity_passed": integrity_passed,
        "tables": comparisons,
        "status": "PASS" if passed else "FAIL",
    }

    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    REPORT_PATH.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )

    print("\nFIXED-SEED REPRODUCIBILITY VALIDATION")
    print("-" * 65)

    for table, result in comparisons.items():
        print(
            f"{table:<25}"
            f"{result['run_a_count']:>10,} "
            f"{result['run_b_count']:>10,} "
            f"{result['status']}"
        )

    print("-" * 65)
    print("Seed:", 20261022)
    print("Scale:", args.scale)
    print("Integrity:", "PASS" if integrity_passed else "FAIL")
    print("Overall:", report["status"])
    print("Report:", REPORT_PATH)

    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
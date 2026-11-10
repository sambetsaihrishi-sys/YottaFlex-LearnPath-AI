import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from app.database import get_connection


BASE = Path(__file__).resolve().parent.parent
EXPORT_DIR = BASE / "exports"
CSV_DIR = EXPORT_DIR / "csv"
JSON_DIR = EXPORT_DIR / "json"

TABLES = [
    "learners",
    "courses",
    "skills",
    "skill_prerequisites",
    "content_items",
    "content_skills",
    "attempts",
    "assessment_results",
    "learning_paths",
    "recommendations",
    "mastery_snapshots",
    "recommendation_events",
    "learning_path_steps"
]


def sha256_file(path):
    digest = hashlib.sha256()

    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def export_dataset():
    CSV_DIR.mkdir(parents=True, exist_ok=True)
    JSON_DIR.mkdir(parents=True, exist_ok=True)

    conn = get_connection()

    try:
        manifest = {
            "project": "YottaFlex LearnPath AI",
            "seed": 20261022,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tables": {}
        }

        for table in TABLES:
            output_path = CSV_DIR / f"{table}.csv"

            cursor = conn.execute(
                f"SELECT * FROM {table} ORDER BY rowid"
            )

            columns = [
                description[0]
                for description in cursor.description
            ]

            count = 0
            sample = []

            with open(
                output_path,
                "w",
                newline="",
                encoding="utf-8"
            ) as file:
                writer = csv.writer(file)
                writer.writerow(columns)

                while True:
                    rows = cursor.fetchmany(10000)

                    if not rows:
                        break

                    writer.writerows(rows)

                    if len(sample) < 5:
                        for row in rows[:5 - len(sample)]:
                            sample.append(dict(zip(columns, row)))

                    count += len(rows)

            sample_path = JSON_DIR / f"{table}_sample.json"

            sample_path.write_text(
                json.dumps(sample, indent=2, default=str),
                encoding="utf-8"
            )

            manifest["tables"][table] = {
                "rows": count,
                "csv_file": str(output_path.relative_to(BASE)),
                "sha256": sha256_file(output_path)
            }

            print(f"{table:<25} {count:>10,} rows")

        manifest_path = EXPORT_DIR / "manifest.json"

        manifest_path.write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8"
        )

        print("\nExport completed successfully.")
        print(f"CSV directory: {CSV_DIR}")
        print(f"JSON directory: {JSON_DIR}")
        print(f"Manifest: {manifest_path}")

    finally:
        conn.close()


if __name__ == "__main__":
    export_dataset()
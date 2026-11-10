import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.database import DB_PATH

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "exports" / "sql"

TABLES = [
    "courses",
    "learners",
    "skills",
    "skill_prerequisites",
    "content_items",
    "content_skills",
    "learning_paths",
    "recommendations",
    "attempts",
    "assessment_results",
    "mastery_snapshots",
    "recommendation_events",
    "learning_path_steps",
]


def quote_identifier(value):
    return '"' + value.replace('"', '""') + '"'


def sql_literal(value):
    if value is None:
        return "NULL"

    if isinstance(value, bool):
        return "1" if value else "0"

    if isinstance(value, int):
        return str(value)

    if isinstance(value, float):
        return repr(value)

    if isinstance(value, bytes):
        return "X'" + value.hex() + "'"

    return "'" + str(value).replace("'", "''") + "'"


def export_sql_seed(output_path, tables):
    if not DB_PATH.is_file():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )

    connection = sqlite3.connect(
        f"{DB_PATH.as_uri()}?mode=ro",
        uri=True
    )

    connection.row_factory = sqlite3.Row

    counts = {}

    try:
        with output_path.open(
            "w",
            encoding="utf-8",
            newline="\n"
        ) as output:
            output.write("PRAGMA foreign_keys = ON;\n")
            output.write("BEGIN TRANSACTION;\n\n")

            for table in tables:
                columns = [
                    row["name"]
                    for row in connection.execute(
                        f"PRAGMA table_info({quote_identifier(table)})"
                    )
                ]

                if not columns:
                    raise RuntimeError(
                        f"Missing table: {table}"
                    )

                primary_keys = [
                    row["name"]
                    for row in connection.execute(
                        f"PRAGMA table_info({quote_identifier(table)})"
                    )
                    if row["pk"]
                ]

                ordering = primary_keys or columns

                column_sql = ", ".join(
                    quote_identifier(column)
                    for column in columns
                )

                order_sql = ", ".join(
                    quote_identifier(column)
                    for column in ordering
                )

                query = (
                    f"SELECT {column_sql} "
                    f"FROM {quote_identifier(table)} "
                    f"ORDER BY {order_sql}"
                )

                prefix = (
                    f"INSERT INTO {quote_identifier(table)} "
                    f"({column_sql}) VALUES "
                )

                count = 0

                for row in connection.execute(query):
                    values = ", ".join(
                        sql_literal(row[column])
                        for column in columns
                    )

                    output.write(
                        f"{prefix}({values});\n"
                    )

                    count += 1

                counts[table] = count

                output.write("\n")

                print(
                    f"{table:<25}: {count:,}",
                    flush=True
                )

            output.write("COMMIT;\n")

    finally:
        connection.close()

    digest = hashlib.sha256()

    with output_path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b""
        ):
            digest.update(chunk)

    return counts, digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--output",
        default=str(OUTPUT_DIR / "learnpath_seed.sql")
    )

    parser.add_argument(
        "--core-only",
        action="store_true"
    )

    args = parser.parse_args()

    output_path = Path(args.output).resolve()

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    tables = (
        TABLES[:6] + TABLES[8:10]
        if args.core_only
        else TABLES
    )

    print("\nSQL SEED EXPORT")
    print("-" * 55)

    counts, checksum = export_sql_seed(
        output_path,
        tables
    )

    manifest = {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "source_database": str(DB_PATH),
        "sql_seed_file": str(output_path),
        "sha256": checksum,
        "table_counts": counts,
        "total_rows": sum(counts.values()),
        "requires_schema": True,
    }

    manifest_path = output_path.with_suffix(
        ".manifest.json"
    )

    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8"
    )

    print("-" * 55)
    print("Total rows:", f"{sum(counts.values()):,}")
    print("SQL seed:", output_path)
    print("Manifest:", manifest_path)
    print("SHA-256:", checksum)
    print("Status: EXPORTED")


if __name__ == "__main__":
    main()
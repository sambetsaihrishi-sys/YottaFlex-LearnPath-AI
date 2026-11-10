import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path

from app.database import BASE_DIR, DB_PATH, SCHEMA

SEED_PATH = BASE_DIR / "exports" / "sql" / "learnpath_seed.sql"
MANIFEST_PATH = BASE_DIR / "exports" / "sql" / "learnpath_seed.manifest.json"
REPORT_PATH = BASE_DIR / "reports" / "sql_restore_validation.json"


def file_sha256(path):
    digest = hashlib.sha256()

    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def table_digest(connection, table):
    columns = [
        row[1]
        for row in connection.execute(
            f'PRAGMA table_info("{table}")'
        )
    ]

    primary_keys = [
        row[1]
        for row in sorted(
            connection.execute(f'PRAGMA table_info("{table}")'),
            key=lambda item: item[5]
        )
        if row[5]
    ]

    order_columns = primary_keys or columns
    ordering = ", ".join(f'"{column}"' for column in order_columns)

    digest = hashlib.sha256()
    count = 0

    for row in connection.execute(
        f'SELECT * FROM "{table}" ORDER BY {ordering}'
    ):
        encoded = json.dumps(
            list(row),
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        count += 1

    return count, digest.hexdigest()


def main():
    if not SEED_PATH.is_file():
        raise FileNotFoundError(SEED_PATH)

    if not MANIFEST_PATH.is_file():
        raise FileNotFoundError(MANIFEST_PATH)

    manifest = json.loads(
        MANIFEST_PATH.read_text(encoding="utf-8")
    )

    actual_seed_hash = file_sha256(SEED_PATH)

    if actual_seed_hash != manifest["sha256"]:
        raise RuntimeError("SQL seed checksum mismatch")

    tables = list(manifest["table_counts"])

    with tempfile.TemporaryDirectory(
        prefix="learnpath_restore_"
    ) as temporary_directory:
        restored_path = (
            Path(temporary_directory) / "restored.db"
        )

        restored = sqlite3.connect(restored_path)

        try:
            restored.executescript(SCHEMA)

            with SEED_PATH.open(
                "r",
                encoding="utf-8"
            ) as source:
                restored.executescript(source.read())

            restored.commit()

            source_database = sqlite3.connect(
                f"{DB_PATH.as_uri()}?mode=ro",
                uri=True
            )

            try:
                results = {}

                for table in tables:
                    original_count, original_hash = table_digest(
                        source_database,
                        table
                    )

                    restored_count, restored_hash = table_digest(
                        restored,
                        table
                    )

                    passed = (
                        original_count == restored_count
                        and original_hash == restored_hash
                        and restored_count
                        == manifest["table_counts"][table]
                    )

                    results[table] = {
                        "original_count": original_count,
                        "restored_count": restored_count,
                        "hash_match": original_hash == restored_hash,
                        "status": "PASS" if passed else "FAIL",
                    }

                    print(
                        f"{table:<25} "
                        f"{restored_count:>10,} "
                        f"{results[table]['status']}",
                        flush=True
                    )

                fk_violations = len(
                    restored.execute(
                        "PRAGMA foreign_key_check"
                    ).fetchall()
                )

                integrity = restored.execute(
                    "PRAGMA integrity_check"
                ).fetchone()[0]

            finally:
                source_database.close()

        finally:
            restored.close()

    passed = (
        all(
            result["status"] == "PASS"
            for result in results.values()
        )
        and fk_violations == 0
        and integrity == "ok"
    )

    report = {
        "sql_seed_sha256": actual_seed_hash,
        "tables": results,
        "foreign_key_violations": fk_violations,
        "integrity_check": integrity,
        "status": "PASS" if passed else "FAIL",
    }

    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    REPORT_PATH.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8"
    )

    print("\nSQL RESTORATION VALIDATION")
    print("Tables checked:", len(results))
    print("Foreign-key violations:", fk_violations)
    print("Integrity:", integrity)
    print("Overall:", report["status"])
    print("Report:", REPORT_PATH)

    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
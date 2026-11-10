import hashlib
import json
from pathlib import Path


BASE = Path(__file__).resolve().parent.parent
MANIFEST = BASE / "exports" / "manifest.json"


def calculate_hash(path):
    digest = hashlib.sha256()

    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def verify_exports():
    manifest = json.loads(
        MANIFEST.read_text(encoding="utf-8")
    )

    passed = 0
    failed = 0

    for table, details in manifest["tables"].items():
        path = BASE / details["csv_file"]

        if not path.exists():
            print(f"FAIL {table}: File missing")
            failed += 1
            continue

        actual = calculate_hash(path)
        expected = details["sha256"]

        if actual == expected:
            print(f"PASS {table}")
            passed += 1
        else:
            print(f"FAIL {table}: Hash mismatch")
            failed += 1

    print()
    print(f"Verified: {passed}")
    print(f"Failed: {failed}")

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    verify_exports()
import argparse
from collections import defaultdict
from datetime import datetime, timezone

from app.database import get_connection


def calculate_mastery(scores):
    if not scores:
        return 0.0

    recent_scores = scores[-5:]
    weights = list(range(1, len(recent_scores) + 1))

    weighted_sum = sum(
        score * weight
        for score, weight in zip(recent_scores, weights)
    )

    return round(
        weighted_sum / sum(weights) / 100,
        4
    )


def build_mastery_snapshots(as_of=None):
    conn = get_connection()

    try:
        if as_of is None:
            as_of = datetime.now(timezone.utc).replace(
                tzinfo=None
            ).isoformat()

        existing = conn.execute(
            """
            SELECT COUNT(*)
            FROM mastery_snapshots
            WHERE calculated_at = ?
            """,
            (as_of,)
        ).fetchone()[0]

        if existing:
            raise ValueError(
                f"Mastery snapshots already exist for {as_of}. "
                "Choose a new calculation timestamp."
            )

        rows = conn.execute(
            """
            SELECT
                a.learner_id,
                cs.skill_id,
                ar.score,
                ar.assessed_at,
                a.attempt_id
            FROM assessment_results ar
            JOIN attempts a
                ON ar.attempt_id = a.attempt_id
            JOIN content_skills cs
                ON a.content_id = cs.content_id
            WHERE
                a.status = 'COMPLETED'
                AND a.completed_at <= ?
                AND ar.assessed_at <= ?
            ORDER BY
                a.learner_id,
                cs.skill_id,
                ar.assessed_at,
                a.attempt_id
            """,
            (as_of, as_of)
        ).fetchall()

        grouped = defaultdict(list)

        for row in rows:
            key = (
                row["learner_id"],
                row["skill_id"]
            )

            grouped[key].append(row["score"])

        snapshots = []

        next_id = conn.execute(
            """
            SELECT COALESCE(
                MAX(CAST(SUBSTR(snapshot_id, 5) AS INTEGER)),
                0
            ) + 1
            FROM mastery_snapshots
            WHERE snapshot_id GLOB 'MST-[0-9]*'
            """
        ).fetchone()[0]

        for learner_id, skill_id in sorted(grouped):
            scores = grouped[(learner_id, skill_id)]

            snapshots.append((
                f"MST-{next_id:09d}",
                learner_id,
                skill_id,
                calculate_mastery(scores),
                len(scores),
                "RECENCY_WEIGHTED_LAST_5",
                as_of
            ))

            next_id += 1

        conn.executemany(
            """
            INSERT INTO mastery_snapshots
            (
                snapshot_id,
                learner_id,
                skill_id,
                mastery_score,
                assessment_count,
                calculation_method,
                calculated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            snapshots
        )

        conn.commit()

        print("\n" + "=" * 50)
        print("MASTERY ENGINE COMPLETE")
        print("=" * 50)
        print(f"New Mastery Snapshots: {len(snapshots):,}")
        print(f"Calculation Time: {as_of}")
        print("Method: Recency Weighted Last 5 Assessments")
        print("Historical Snapshots: PRESERVED")
        print("=" * 50)

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_skill_mastery(learner_id, skill_id, as_of=None, conn=None):
    owns_connection = conn is None

    if owns_connection:
        conn = get_connection()

    try:
        if as_of is None:
            as_of = datetime.now(timezone.utc).replace(
                tzinfo=None
            ).isoformat()

        rows = conn.execute(
            """
            SELECT ar.score
            FROM assessment_results ar
            JOIN attempts a
                ON ar.attempt_id = a.attempt_id
            JOIN content_skills cs
                ON a.content_id = cs.content_id
            WHERE
                a.learner_id = ?
                AND cs.skill_id = ?
                AND a.status = 'COMPLETED'
                AND a.completed_at <= ?
                AND ar.assessed_at <= ?
            ORDER BY
                ar.assessed_at DESC,
                a.attempt_id DESC
            LIMIT 5
            """,
            (
                learner_id,
                skill_id,
                as_of,
                as_of
            )
        ).fetchall()

        scores = [
            row["score"]
            for row in reversed(rows)
        ]

        return calculate_mastery(scores)

    finally:
        if owns_connection:
            conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--as-of",
        default=None
    )

    args = parser.parse_args()

    build_mastery_snapshots(args.as_of)

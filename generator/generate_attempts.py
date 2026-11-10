import argparse
import random
from collections import defaultdict
from datetime import datetime, timedelta

from app.database import get_connection

SEED = 20261022


def generate_attempts(scale="starter"):
    rng = random.Random(SEED + 1)
    target = 500000 if scale == "full" else 1000

    conn = get_connection()

    try:
        learners = [
            dict(row)
            for row in conn.execute(
                """
                SELECT learner_id, enrolled_at
                FROM learners
                ORDER BY learner_id
                """
            )
        ]

        content = [
            dict(row)
            for row in conn.execute(
                """
                SELECT content_id, course_id, difficulty, format
                FROM content_items
                ORDER BY content_id
                """
            )
        ]

        expected_learners = 10000 if scale == "full" else 100
        expected_content = 2000 if scale == "full" else 200

        if len(learners) != expected_learners:
            raise RuntimeError(
                f"Expected {expected_learners} learners, found {len(learners)}"
            )

        if len(content) != expected_content:
            raise RuntimeError(
                f"Expected {expected_content} content items, found {len(content)}"
            )

        existing = conn.execute(
            "SELECT COUNT(*) FROM attempts"
        ).fetchone()[0]

        if existing:
            raise RuntimeError("Attempts already exist")

        eligible_count = int(len(learners) * 0.90)
        eligible = learners[:eligible_count]

        course_content = defaultdict(list)

        for item in content:
            course_content[item["course_id"]].append(item)

        course_ids = sorted(course_content)

        abilities = {}
        assignments = {}
        enrollment = {}

        for learner in learners:
            learner_id = learner["learner_id"]

            abilities[learner_id] = rng.uniform(0.30, 0.90)
            enrollment[learner_id] = datetime.fromisoformat(
                learner["enrolled_at"]
            )

        for learner in eligible:
            assignments[learner["learner_id"]] = rng.choice(course_ids)

        practice_counts = defaultdict(int)
        attempt_counters = defaultdict(int)

        attempts_batch = []
        results_batch = []

        batch_size = 10000
        inserted = 0

        print(f"Generating {target:,} attempts...")

        for index in range(target):
            learner = eligible[index % eligible_count]
            learner_id = learner["learner_id"]

            course_id = assignments[learner_id]
            item = rng.choice(course_content[course_id])

            content_id = item["content_id"]
            difficulty = item["difficulty"]

            key = (learner_id, content_id)
            practice_number = practice_counts[key]
            practice_counts[key] += 1

            attempt_counters[learner_id] += 1
            sequence = attempt_counters[learner_id]

            attempt_id = f"ATT-{learner_id}-{sequence:06d}"

            started_at = (
                enrollment[learner_id]
                + timedelta(days=1 + (sequence - 1) * 2)
                + timedelta(minutes=rng.randint(0, 600))
            )

            completed_at = started_at + timedelta(
                minutes=rng.randint(5, 45)
            )

            practice_gain = min(
                0.20,
                practice_number * 0.045
            )

            difficulty_penalty = (difficulty - 1) * 0.12
            noise = rng.gauss(0, 0.10)

            raw_score = (
                abilities[learner_id]
                + practice_gain
                - difficulty_penalty
                + noise
            )

            score = round(
                max(0, min(100, raw_score * 100)),
                2
            )

            attempts_batch.append((
                attempt_id,
                learner_id,
                content_id,
                None,
                started_at.isoformat(),
                completed_at.isoformat(),
                "COMPLETED"
            ))

            results_batch.append((
                f"RES-{index + 1:09d}",
                attempt_id,
                score,
                completed_at.isoformat()
            ))

            if len(attempts_batch) >= batch_size:
                conn.executemany(
                    """
                    INSERT INTO attempts
                    (
                        attempt_id,
                        learner_id,
                        content_id,
                        recommendation_id,
                        started_at,
                        completed_at,
                        status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    attempts_batch
                )

                conn.executemany(
                    """
                    INSERT INTO assessment_results
                    (
                        result_id,
                        attempt_id,
                        score,
                        assessed_at
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    results_batch
                )

                conn.commit()

                inserted += len(attempts_batch)

                print(f"Generated {inserted:,}/{target:,}")

                attempts_batch.clear()
                results_batch.clear()

        if attempts_batch:
            conn.executemany(
                """
                INSERT INTO attempts
                (
                    attempt_id,
                    learner_id,
                    content_id,
                    recommendation_id,
                    started_at,
                    completed_at,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                attempts_batch
            )

            conn.executemany(
                """
                INSERT INTO assessment_results
                (
                    result_id,
                    attempt_id,
                    score,
                    assessed_at
                )
                VALUES (?, ?, ?, ?)
                """,
                results_batch
            )

            conn.commit()

            inserted += len(attempts_batch)

        violations = conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if violations:
            raise RuntimeError(
                f"Foreign-key violations: {len(violations)}"
            )

        print("\n" + "=" * 50)
        print("ATTEMPT GENERATION COMPLETE")
        print("=" * 50)
        print(f"Attempts: {inserted:,}")
        print(f"Assessment Results: {inserted:,}")
        print(f"Cold-start Learners: {len(learners) - eligible_count:,}")
        print(f"Foreign-key Violations: {len(violations)}")
        print("=" * 50)

    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--scale",
        choices=["starter", "full"],
        default="starter"
    )

    args = parser.parse_args()

    generate_attempts(args.scale)
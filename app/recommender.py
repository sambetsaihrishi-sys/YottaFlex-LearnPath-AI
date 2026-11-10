import argparse
from datetime import datetime, timezone

from app.database import get_connection
from app.mastery import get_skill_mastery


MASTERY_THRESHOLD = 0.70


def recommend_for_learner(learner_id, limit=5, as_of=None):
    if as_of is None:
        as_of = datetime.now(timezone.utc).replace(
            tzinfo=None
        ).isoformat()

    conn = get_connection()

    try:
        learner = conn.execute(
            """
            SELECT learner_id
            FROM learners
            WHERE learner_id = ?
            """,
            (learner_id,)
        ).fetchone()

        if learner is None:
            raise ValueError(f"Learner not found: {learner_id}")

        course_row = conn.execute(
            """
            SELECT ci.course_id
            FROM attempts a
            JOIN content_items ci
                ON a.content_id = ci.content_id
            WHERE a.learner_id = ?
              AND a.started_at <= ?
            GROUP BY ci.course_id
            ORDER BY COUNT(*) DESC, ci.course_id
            LIMIT 1
            """,
            (learner_id, as_of)
        ).fetchone()

        if course_row is None:
            course_row = conn.execute(
                """
                SELECT course_id
                FROM courses
                WHERE status = 'ACTIVE'
                ORDER BY course_id
                LIMIT 1
                """
            ).fetchone()

        if course_row is None:
            raise ValueError("No active courses available")

        course_id = course_row["course_id"]

        skills = conn.execute(
            """
            SELECT skill_id, name, difficulty
            FROM skills
            WHERE course_id = ?
            ORDER BY skill_id
            """,
            (course_id,)
        ).fetchall()

        mastery_cache = {}

        for skill in skills:
            skill_id = skill["skill_id"]

            mastery_cache[skill_id] = get_skill_mastery(
                learner_id,
                skill_id,
                as_of
            )

        candidates = []

        for skill in skills:
            skill_id = skill["skill_id"]
            mastery = mastery_cache[skill_id]

            if mastery >= MASTERY_THRESHOLD:
                continue

            prerequisites = conn.execute(
                """
                SELECT required_skill_id, minimum_mastery
                FROM skill_prerequisites
                WHERE skill_id = ?
                  AND status = 'ACTIVE'
                  AND effective_from <= ?
                  AND (
                      effective_to IS NULL
                      OR effective_to >= ?
                  )
                """,
                (skill_id, as_of, as_of)
            ).fetchall()

            unmet_prerequisites = []

            for prerequisite in prerequisites:
                required_skill_id = prerequisite["required_skill_id"]

                required_mastery = mastery_cache.get(
                    required_skill_id
                )

                if required_mastery is None:
                    required_mastery = get_skill_mastery(
                        learner_id,
                        required_skill_id,
                        as_of
                    )

                    mastery_cache[required_skill_id] = required_mastery

                if required_mastery < prerequisite["minimum_mastery"]:
                    unmet_prerequisites.append(required_skill_id)

            if unmet_prerequisites:
                continue

            content_items = conn.execute(
                """
                SELECT
                    ci.content_id,
                    ci.title,
                    ci.format,
                    ci.difficulty,
                    ci.duration_minutes
                FROM content_items ci
                JOIN content_skills cs
                    ON ci.content_id = cs.content_id
                WHERE cs.skill_id = ?
                  AND ci.status = 'PUBLISHED'
                  AND ci.published_at <= ?
                ORDER BY ci.content_id
                """,
                (skill_id, as_of)
            ).fetchall()

            target_difficulty = max(
                1,
                min(3, int(mastery * 3) + 1)
            )

            for item in content_items:
                difficulty_gap = abs(
                    item["difficulty"] - target_difficulty
                )

                priority_score = (
                    (1.0 - mastery) * 100
                    - difficulty_gap * 15
                    - item["duration_minutes"] * 0.05
                )

                if mastery == 0:
                    reason_code = "COLD_START_OR_NEW_SKILL"
                    rationale = (
                        f"No prior mastery evidence for {skill['name']}. "
                        f"Start with an appropriate learning activity."
                    )
                elif mastery < 0.40:
                    reason_code = "LOW_MASTERY"
                    rationale = (
                        f"Current mastery is {mastery:.0%}. "
                        f"Foundational practice is recommended."
                    )
                else:
                    reason_code = "MASTERY_GAP"
                    rationale = (
                        f"Current mastery is {mastery:.0%}, "
                        f"below the required 70%. "
                        f"Additional practice is recommended."
                    )

                candidates.append({
                    "learner_id": learner_id,
                    "course_id": course_id,
                    "skill_id": skill_id,
                    "skill_name": skill["name"],
                    "content_id": item["content_id"],
                    "content_title": item["title"],
                    "format": item["format"],
                    "difficulty": item["difficulty"],
                    "mastery": mastery,
                    "priority_score": round(priority_score, 4),
                    "reason_code": reason_code,
                    "rationale": rationale
                })

        candidates.sort(
            key=lambda item: (
                -item["priority_score"],
                item["skill_id"],
                item["content_id"]
            )
        )

        selected = candidates[:limit]

        if not selected:
            return []

        existing_path = conn.execute(
            """
            SELECT path_id
            FROM learning_paths
            WHERE learner_id = ?
              AND course_id = ?
              AND status = 'ACTIVE'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (learner_id, course_id)
        ).fetchone()

        if existing_path:
            path_id = existing_path["path_id"]
        else:
            next_path = conn.execute(
                """
                SELECT COUNT(*) + 1
                FROM learning_paths
                """
            ).fetchone()[0]

            path_id = f"PATH-2026-{next_path:06d}"

            conn.execute(
                """
                INSERT INTO learning_paths
                (
                    path_id,
                    learner_id,
                    course_id,
                    created_at,
                    status
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    path_id,
                    learner_id,
                    course_id,
                    as_of,
                    "ACTIVE"
                )
            )

        next_recommendation = conn.execute(
            """
            SELECT COUNT(*) + 1
            FROM recommendations
            """
        ).fetchone()[0]

        next_event = conn.execute(
            """
            SELECT COUNT(*) + 1
            FROM recommendation_events
            """
        ).fetchone()[0]

        for rank, item in enumerate(selected, start=1):
            recommendation_id = (
                f"REC-{next_recommendation:09d}"
            )

            event_id = f"EVT-{next_event:09d}"

            conn.execute(
                """
                INSERT INTO recommendations
                (
                    recommendation_id,
                    learner_id,
                    path_id,
                    content_id,
                    target_skill_id,
                    generated_at,
                    mastery_at_decision,
                    reason_code,
                    rationale,
                    priority_rank
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    recommendation_id,
                    learner_id,
                    path_id,
                    item["content_id"],
                    item["skill_id"],
                    as_of,
                    item["mastery"],
                    item["reason_code"],
                    item["rationale"],
                    rank
                )
            )

            conn.execute(
                """
                INSERT INTO recommendation_events
                (
                    event_id,
                    recommendation_id,
                    event_type,
                    occurred_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    event_id,
                    recommendation_id,
                    "GENERATED",
                    as_of
                )
            )

            item["recommendation_id"] = recommendation_id
            item["path_id"] = path_id
            item["priority_rank"] = rank

            next_recommendation += 1
            next_event += 1

        conn.commit()

        return selected

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--learner",
        default="LRN-000001"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=5
    )

    args = parser.parse_args()

    recommendations = recommend_for_learner(
        args.learner,
        args.limit
    )

    print("\n" + "=" * 60)
    print("ADAPTIVE LEARNING RECOMMENDATIONS")
    print("=" * 60)

    if not recommendations:
        print("No eligible recommendations found.")

    for recommendation in recommendations:
        print(
            f"\nRank: {recommendation['priority_rank']}"
        )
        print(
            f"Skill: {recommendation['skill_name']}"
        )
        print(
            f"Content: {recommendation['content_title']}"
        )
        print(
            f"Mastery: {recommendation['mastery']:.2f}"
        )
        print(
            f"Reason: {recommendation['reason_code']}"
        )
        print(
            f"Explanation: {recommendation['rationale']}"
        )

    print("\n" + "=" * 60)
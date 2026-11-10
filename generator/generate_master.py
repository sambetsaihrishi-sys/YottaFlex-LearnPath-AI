import random
import argparse
from datetime import datetime, timedelta

from app.database import get_connection, initialize_database


# =========================================================
# CONFIGURATION
# =========================================================

SEED = 20261022

COURSE_TOPICS = [
    "Python Programming",
    "Machine Learning",
    "Data Science",
    "Artificial Intelligence",
    "Web Development",
    "Database Management",
    "Cloud Computing",
    "Cybersecurity",
    "Data Structures",
    "Software Engineering",
]

CONTENT_FORMATS = [
    "VIDEO",
    "ARTICLE",
    "QUIZ",
    "EXERCISE",
]


# =========================================================
# MASTER DATA GENERATOR
# =========================================================

def generate_master(scale="starter"):

    rng = random.Random(SEED)

    if scale == "full":
        num_learners = 10000
        num_courses = 50
        num_skills = 500
        num_content = 2000
    else:
        num_learners = 100
        num_courses = 5
        num_skills = 50
        num_content = 200

    # Initialize database
    initialize_database()

    conn = get_connection()

    try:

        # Prevent duplicate generation
        tables_to_check = [
            "learners",
            "courses",
            "skills",
            "skill_prerequisites",
            "content_items",
            "content_skills",
        ]

        for table in tables_to_check:
            count = conn.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]

            if count > 0:
                raise RuntimeError(
                    f"Table '{table}' already contains data. "
                    "Use a fresh database before regenerating."
                )

        base_date = datetime(2026, 1, 1)

        # =================================================
        # 1. GENERATE COURSES
        # =================================================

        print("\nGenerating courses...")

        courses = []

        for i in range(1, num_courses + 1):

            course_id = f"CRS-{i:06d}"

            topic = COURSE_TOPICS[
                (i - 1) % len(COURSE_TOPICS)
            ]

            level = (i - 1) // len(COURSE_TOPICS) + 1

            title = f"{topic} - Level {level}"

            courses.append((
                course_id,
                title,
                base_date.isoformat(),
                "ACTIVE"
            ))

        conn.executemany(
            """
            INSERT INTO courses
            (course_id, title, created_at, status)
            VALUES (?, ?, ?, ?)
            """,
            courses
        )

        # =================================================
        # 2. GENERATE SKILLS
        # =================================================

        print("Generating skills...")

        skills = []

        skills_per_course = num_skills // num_courses

        for i in range(1, num_skills + 1):

            course_index = (
                (i - 1) // skills_per_course
            ) + 1

            position = (
                (i - 1) % skills_per_course
            ) + 1

            skill_id = f"SKL-{i:06d}"

            course_id = f"CRS-{course_index:06d}"

            difficulty = min(
                3,
                (position - 1) // 4 + 1
            )

            skills.append((
                skill_id,
                course_id,
                f"Skill {position:02d}",
                difficulty
            ))

        conn.executemany(
            """
            INSERT INTO skills
            (skill_id, course_id, name, difficulty)
            VALUES (?, ?, ?, ?)
            """,
            skills
        )

        # =================================================
        # 3. GENERATE SKILL PREREQUISITES
        # =================================================

        print("Generating skill prerequisites...")

        prerequisites = []

        prerequisite_counter = 1

        for course_index in range(num_courses):

            start = (
                course_index * skills_per_course
            ) + 1

            for position in range(
                1,
                skills_per_course
            ):

                current_skill = start + position

                previous_skill = current_skill - 1

                prerequisites.append((
                    f"PRE-{prerequisite_counter:06d}",
                    f"SKL-{current_skill:06d}",
                    f"SKL-{previous_skill:06d}",
                    0.70,
                    base_date.isoformat(),
                    None,
                    "ACTIVE"
                ))

                prerequisite_counter += 1

        conn.executemany(
            """
            INSERT INTO skill_prerequisites
            (
                prerequisite_id,
                skill_id,
                required_skill_id,
                minimum_mastery,
                effective_from,
                effective_to,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            prerequisites
        )

        # =================================================
        # 4. GENERATE CONTENT ITEMS
        # =================================================

        print("Generating content items...")

        content_items = []

        content_skill_mappings = []

        for i in range(1, num_content + 1):

            content_id = f"CNT-{i:06d}"

            skill_index = (
                (i - 1) % num_skills
            ) + 1

            course_index = (
                (skill_index - 1) // skills_per_course
            ) + 1

            skill_id = f"SKL-{skill_index:06d}"

            course_id = f"CRS-{course_index:06d}"

            content_format = CONTENT_FORMATS[
                (i - 1) % len(CONTENT_FORMATS)
            ]

            difficulty = rng.randint(1, 3)

            duration = rng.randint(5, 60)

            title = (
                f"Learning Activity {i:04d} "
                f"- {content_format}"
            )

            # IMPORTANT:
            # Order matches the SQL columns exactly.
            content_items.append((
                content_id,
                course_id,
                title,
                content_format,
                difficulty,
                duration,
                "PUBLISHED",
                base_date.isoformat()
            ))

            content_skill_mappings.append((
                f"MAP-{i:06d}",
                content_id,
                skill_id,
                1.0
            ))

        conn.executemany(
            """
            INSERT INTO content_items
            (
                content_id,
                course_id,
                title,
                format,
                difficulty,
                duration_minutes,
                status,
                published_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            content_items
        )

        # =================================================
        # 5. GENERATE CONTENT-SKILL RELATIONSHIPS
        # =================================================

        print("Generating content-skill mappings...")

        conn.executemany(
            """
            INSERT INTO content_skills
            (
                mapping_id,
                content_id,
                skill_id,
                weight
            )
            VALUES (?, ?, ?, ?)
            """,
            content_skill_mappings
        )

        # =================================================
        # 6. GENERATE LEARNERS
        # =================================================

        print("Generating learners...")

        learners = []

        for i in range(1, num_learners + 1):

            learner_id = f"LRN-{i:06d}"

            enrollment_date = (
                base_date + timedelta(
                    days=rng.randint(0, 100)
                )
            )

            learners.append((
                learner_id,
                f"Synthetic Learner {i:05d}",
                enrollment_date.isoformat(),
                "ACTIVE"
            ))

        conn.executemany(
            """
            INSERT INTO learners
            (
                learner_id,
                name,
                enrolled_at,
                status
            )
            VALUES (?, ?, ?, ?)
            """,
            learners
        )

        # =================================================
        # 7. VALIDATE FOREIGN KEYS
        # =================================================

        print("Validating foreign keys...")

        violations = conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if violations:
            raise RuntimeError(
                f"Foreign-key violations detected: "
                f"{len(violations)}"
            )

        # =================================================
        # 8. COMMIT DATA
        # =================================================

        conn.commit()

        print("\n" + "=" * 50)
        print("MASTER DATA GENERATION COMPLETE")
        print("=" * 50)

        tables = [
            "learners",
            "courses",
            "skills",
            "skill_prerequisites",
            "content_items",
            "content_skills",
        ]

        for table in tables:

            count = conn.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]

            print(f"{table:<25}: {count}")

        print("-" * 50)

        print("Foreign Key Violations: 0")
        print(f"Random Seed: {SEED}")
        print(f"Dataset Scale: {scale}")

        print("=" * 50)

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()


# =========================================================
# COMMAND LINE
# =========================================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="LearnPath AI Master Data Generator"
    )

    parser.add_argument(
        "--scale",
        choices=["starter", "full"],
        default="starter",
        help="Dataset size"
    )

    args = parser.parse_args()

    generate_master(args.scale)
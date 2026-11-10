
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS learners (
    learner_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    enrolled_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK(status IN ('ACTIVE','INACTIVE'))
);

CREATE TABLE IF NOT EXISTS courses (
    course_id TEXT PRIMARY KEY,
    title TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK(status IN ('DRAFT','ACTIVE','ARCHIVED'))
);

CREATE TABLE IF NOT EXISTS skills (
    skill_id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL,
    name TEXT NOT NULL,
    difficulty INTEGER NOT NULL
        CHECK(difficulty BETWEEN 1 AND 3),
    FOREIGN KEY(course_id) REFERENCES courses(course_id),
    UNIQUE(course_id, name)
);

CREATE TABLE IF NOT EXISTS skill_prerequisites (
    prerequisite_id TEXT PRIMARY KEY,
    skill_id TEXT NOT NULL,
    required_skill_id TEXT NOT NULL,
    minimum_mastery REAL NOT NULL DEFAULT 0.70
        CHECK(minimum_mastery BETWEEN 0 AND 1),
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK(status IN ('ACTIVE','INACTIVE')),
    CHECK(skill_id != required_skill_id),
    CHECK(effective_to IS NULL OR effective_to >= effective_from),
    FOREIGN KEY(skill_id) REFERENCES skills(skill_id),
    FOREIGN KEY(required_skill_id) REFERENCES skills(skill_id),
    UNIQUE(skill_id, required_skill_id)
);

CREATE TABLE IF NOT EXISTS content_items (
    content_id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL,
    title TEXT NOT NULL,
    format TEXT NOT NULL
        CHECK(format IN ('VIDEO','ARTICLE','QUIZ','EXERCISE')),
    difficulty INTEGER NOT NULL
        CHECK(difficulty BETWEEN 1 AND 3),
    duration_minutes INTEGER NOT NULL
        CHECK(duration_minutes > 0),
    status TEXT NOT NULL DEFAULT 'PUBLISHED'
        CHECK(status IN ('DRAFT','PUBLISHED','RETIRED')),
    published_at TEXT,
    FOREIGN KEY(course_id) REFERENCES courses(course_id)
);

CREATE TABLE IF NOT EXISTS content_skills (
    mapping_id TEXT PRIMARY KEY,
    content_id TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0
        CHECK(weight > 0 AND weight <= 1),
    FOREIGN KEY(content_id) REFERENCES content_items(content_id),
    FOREIGN KEY(skill_id) REFERENCES skills(skill_id),
    UNIQUE(content_id, skill_id)
);

CREATE TABLE IF NOT EXISTS learning_paths (
    path_id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL,
    course_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK(status IN ('ACTIVE','COMPLETED','CANCELLED')),
    FOREIGN KEY(learner_id) REFERENCES learners(learner_id),
    FOREIGN KEY(course_id) REFERENCES courses(course_id)
);

CREATE TABLE IF NOT EXISTS recommendations (
    recommendation_id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL,
    path_id TEXT NOT NULL,
    content_id TEXT NOT NULL,
    target_skill_id TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    mastery_at_decision REAL
        CHECK(mastery_at_decision BETWEEN 0 AND 1),
    reason_code TEXT NOT NULL,
    rationale TEXT NOT NULL,
    priority_rank INTEGER NOT NULL CHECK(priority_rank > 0),
    FOREIGN KEY(learner_id) REFERENCES learners(learner_id),
    FOREIGN KEY(path_id) REFERENCES learning_paths(path_id),
    FOREIGN KEY(content_id) REFERENCES content_items(content_id),
    FOREIGN KEY(target_skill_id) REFERENCES skills(skill_id)
);

CREATE TABLE IF NOT EXISTS attempts (
    attempt_id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL,
    content_id TEXT NOT NULL,
    recommendation_id TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL
        CHECK(status IN ('STARTED','COMPLETED','ABANDONED')),
    CHECK(completed_at IS NULL OR completed_at >= started_at),
    CHECK(status != 'COMPLETED' OR completed_at IS NOT NULL),
    FOREIGN KEY(learner_id) REFERENCES learners(learner_id),
    FOREIGN KEY(content_id) REFERENCES content_items(content_id),
    FOREIGN KEY(recommendation_id)
        REFERENCES recommendations(recommendation_id)
);

CREATE TABLE IF NOT EXISTS assessment_results (
    result_id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL UNIQUE,
    score REAL NOT NULL CHECK(score BETWEEN 0 AND 100),
    assessed_at TEXT NOT NULL,
    FOREIGN KEY(attempt_id) REFERENCES attempts(attempt_id)
);

CREATE TABLE IF NOT EXISTS mastery_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    learner_id TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    mastery_score REAL NOT NULL
        CHECK(mastery_score BETWEEN 0 AND 1),
    assessment_count INTEGER NOT NULL
        CHECK(assessment_count >= 0),
    calculation_method TEXT NOT NULL,
    calculated_at TEXT NOT NULL,
    FOREIGN KEY(learner_id) REFERENCES learners(learner_id),
    FOREIGN KEY(skill_id) REFERENCES skills(skill_id)
);

CREATE TABLE IF NOT EXISTS recommendation_events (
    event_id TEXT PRIMARY KEY,
    recommendation_id TEXT NOT NULL,
    event_type TEXT NOT NULL
        CHECK(event_type IN (
            'GENERATED','STARTED','COMPLETED','SKIPPED'
        )),
    occurred_at TEXT NOT NULL,
    FOREIGN KEY(recommendation_id)
        REFERENCES recommendations(recommendation_id)
);

CREATE TABLE IF NOT EXISTS learning_path_steps (
    step_id TEXT PRIMARY KEY,
    path_id TEXT NOT NULL,
    content_id TEXT NOT NULL,
    step_number INTEGER NOT NULL CHECK(step_number > 0),
    mastery_before REAL CHECK(mastery_before BETWEEN 0 AND 1),
    mastery_after REAL CHECK(mastery_after BETWEEN 0 AND 1),
    recorded_at TEXT NOT NULL,
    FOREIGN KEY(path_id) REFERENCES learning_paths(path_id),
    FOREIGN KEY(content_id) REFERENCES content_items(content_id),
    UNIQUE(path_id, step_number)
);

CREATE INDEX IF NOT EXISTS idx_attempt_learner
ON attempts(learner_id, completed_at);

CREATE INDEX IF NOT EXISTS idx_attempt_content
ON attempts(content_id);

CREATE INDEX IF NOT EXISTS idx_content_skill
ON content_skills(skill_id);

CREATE INDEX IF NOT EXISTS idx_skill_prerequisite
ON skill_prerequisites(skill_id);

CREATE INDEX IF NOT EXISTS idx_recommendation_learner
ON recommendations(learner_id, generated_at);

CREATE INDEX IF NOT EXISTS idx_mastery
ON mastery_snapshots(learner_id, skill_id, calculated_at);

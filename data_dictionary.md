# LearnPath AI — Data Dictionary

Generated from the current SQLite database schema. Contains the ten required business entities and three supporting history tables.

The **Validation** column distinguishes SQL constraints from rules that need application-level checks.
Expected ID patterns and ISO-8601 dates are conventions unless a database CHECK explicitly enforces them.

## learners

| Field | Type | Required | Allowed values | Units | Uniqueness | Default | Validation |
|---|---|---|---|---|---|---|---|
| learner_id | TEXT | Yes | LRN-000001 pattern | identifier | (learner_id) | — | SQL PRIMARY KEY; generator should enforce ID convention |
| name | TEXT | Yes | Text (non-empty expected) | text | No | — | SQL NOT NULL when required; non-empty text needs app validation |
| enrolled_at | TEXT | Yes | ISO-8601 date/time text (or NULL when optional) | timestamp | No | — | Date syntax not enforced by SQL; chronological rules require validation |
| status | TEXT | Yes | ACTIVE, INACTIVE | state/category | No | 'ACTIVE' | SQL CHECK restricts allowed values |

**Foreign-key relationships:**
- None

## courses

| Field | Type | Required | Allowed values | Units | Uniqueness | Default | Validation |
|---|---|---|---|---|---|---|---|
| course_id | TEXT | Yes | CRS-000001 pattern | identifier | (course_id) | — | SQL PRIMARY KEY; generator should enforce ID convention |
| title | TEXT | Yes | Text (non-empty expected) | text | (title) | — | SQL NOT NULL when required; non-empty text needs app validation |
| created_at | TEXT | Yes | ISO-8601 date/time text (or NULL when optional) | timestamp | No | — | Date syntax not enforced by SQL; chronological rules require validation |
| status | TEXT | Yes | DRAFT, ACTIVE, ARCHIVED | state/category | No | 'ACTIVE' | SQL CHECK restricts allowed values |

**Foreign-key relationships:**
- None

## skills

| Field | Type | Required | Allowed values | Units | Uniqueness | Default | Validation |
|---|---|---|---|---|---|---|---|
| skill_id | TEXT | Yes | SKL-000001 pattern | identifier | (skill_id) | — | SQL PRIMARY KEY; generator should enforce ID convention |
| course_id | TEXT | Yes | Existing courses.course_id | identifier | (course_id, name) | — | SQL FOREIGN KEY; consistency across courses checked separately |
| name | TEXT | Yes | Text (non-empty expected) | text | (course_id, name) | — | SQL NOT NULL when required; non-empty text needs app validation |
| difficulty | INTEGER | Yes | 1–3 | level | No | — | SQL CHECK: BETWEEN 1 AND 3 |

**Foreign-key relationships:**
- `course_id` → `courses.course_id`

## skill_prerequisites

| Field | Type | Required | Allowed values | Units | Uniqueness | Default | Validation |
|---|---|---|---|---|---|---|---|
| prerequisite_id | TEXT | Yes | Non-empty unique text key | identifier | (prerequisite_id) | — | SQL PRIMARY KEY; generator should enforce ID convention |
| skill_id | TEXT | Yes | Existing skills.skill_id | identifier | (skill_id, required_skill_id) | — | SQL FOREIGN KEY; consistency across courses checked separately; Cannot equal required_skill_id; enforced by SQL CHECK. |
| required_skill_id | TEXT | Yes | Existing skills.skill_id | identifier | (skill_id, required_skill_id) | — | SQL FOREIGN KEY; consistency across courses checked separately; Cannot equal skill_id; enforced by SQL CHECK. |
| minimum_mastery | REAL | Yes | 0–1 | fraction | No | 0.70 | SQL CHECK: BETWEEN 0 AND 1 |
| effective_from | TEXT | Yes | ISO-8601 date/time text (or NULL when optional) | timestamp | No | — | Date syntax not enforced by SQL; chronological rules require validation |
| effective_to | TEXT | No | ISO-8601 date/time text (or NULL when optional) | timestamp | No | — | Date syntax not enforced by SQL; chronological rules require validation; If supplied, must be >= effective_from (SQL CHECK). |
| status | TEXT | Yes | ACTIVE, INACTIVE | state/category | No | 'ACTIVE' | SQL CHECK restricts allowed values |

**Foreign-key relationships:**
- `required_skill_id` → `skills.skill_id`
- `skill_id` → `skills.skill_id`

## content_items

| Field | Type | Required | Allowed values | Units | Uniqueness | Default | Validation |
|---|---|---|---|---|---|---|---|
| content_id | TEXT | Yes | CNT-000001 pattern | identifier | (content_id) | — | SQL PRIMARY KEY; generator should enforce ID convention |
| course_id | TEXT | Yes | Existing courses.course_id | identifier | No | — | SQL FOREIGN KEY; consistency across courses checked separately |
| title | TEXT | Yes | Text (non-empty expected) | text | No | — | SQL NOT NULL when required; non-empty text needs app validation |
| format | TEXT | Yes | VIDEO, ARTICLE, QUIZ, EXERCISE | state/category | No | — | SQL CHECK restricts allowed values |
| difficulty | INTEGER | Yes | 1–3 | level | No | — | SQL CHECK: BETWEEN 1 AND 3 |
| duration_minutes | INTEGER | Yes | positive integer | minutes | No | — | SQL CHECK: > 0 |
| status | TEXT | Yes | DRAFT, PUBLISHED, RETIRED | state/category | No | 'PUBLISHED' | SQL CHECK restricts allowed values |
| published_at | TEXT | No | ISO-8601 date/time text (or NULL when optional) | timestamp | No | — | Date syntax not enforced by SQL; chronological rules require validation; Publishing lifecycle consistency requires application validation. |

**Foreign-key relationships:**
- `course_id` → `courses.course_id`

## content_skills

| Field | Type | Required | Allowed values | Units | Uniqueness | Default | Validation |
|---|---|---|---|---|---|---|---|
| mapping_id | TEXT | Yes | Non-empty unique text key | identifier | (mapping_id) | — | SQL PRIMARY KEY; generator should enforce ID convention |
| content_id | TEXT | Yes | Existing content_items.content_id | identifier | (content_id, skill_id) | — | SQL FOREIGN KEY; consistency across courses checked separately |
| skill_id | TEXT | Yes | Existing skills.skill_id | identifier | (content_id, skill_id) | — | SQL FOREIGN KEY; consistency across courses checked separately |
| weight | REAL | Yes | greater than 0, at most 1 | fraction | No | 1.0 | SQL CHECK: 0 < weight <= 1 |

**Foreign-key relationships:**
- `skill_id` → `skills.skill_id`
- `content_id` → `content_items.content_id`

## attempts

| Field | Type | Required | Allowed values | Units | Uniqueness | Default | Validation |
|---|---|---|---|---|---|---|---|
| attempt_id | TEXT | Yes | ATT-LRN-000001-000001 pattern | identifier | (attempt_id) | — | SQL PRIMARY KEY; generator should enforce ID convention |
| learner_id | TEXT | Yes | Existing learners.learner_id | identifier | No | — | SQL FOREIGN KEY; consistency across courses checked separately |
| content_id | TEXT | Yes | Existing content_items.content_id | identifier | No | — | SQL FOREIGN KEY; consistency across courses checked separately |
| recommendation_id | TEXT | No | Existing recommendations.recommendation_id | identifier | No | — | SQL FOREIGN KEY; consistency across courses checked separately |
| started_at | TEXT | Yes | ISO-8601 date/time text (or NULL when optional) | timestamp | No | — | Date syntax not enforced by SQL; chronological rules require validation |
| completed_at | TEXT | No | ISO-8601 date/time text (or NULL when optional) | timestamp | No | — | Date syntax not enforced by SQL; chronological rules require validation; If supplied, must be >= started_at. Required when status is COMPLETED (SQL CHECK). |
| status | TEXT | Yes | STARTED, COMPLETED, ABANDONED | state/category | No | — | SQL CHECK restricts allowed values |

**Foreign-key relationships:**
- `recommendation_id` → `recommendations.recommendation_id`
- `content_id` → `content_items.content_id`
- `learner_id` → `learners.learner_id`

## assessment_results

| Field | Type | Required | Allowed values | Units | Uniqueness | Default | Validation |
|---|---|---|---|---|---|---|---|
| result_id | TEXT | Yes | Non-empty unique text key | identifier | (result_id) | — | SQL PRIMARY KEY; generator should enforce ID convention |
| attempt_id | TEXT | Yes | Existing attempts.attempt_id | identifier | (attempt_id) | — | SQL FOREIGN KEY; consistency across courses checked separately; One assessment per attempt (SQL UNIQUE). |
| score | REAL | Yes | 0–100 | points | No | — | SQL CHECK: BETWEEN 0 AND 100 |
| assessed_at | TEXT | Yes | ISO-8601 date/time text (or NULL when optional) | timestamp | No | — | Date syntax not enforced by SQL; chronological rules require validation; Should follow attempt completion; checked by relationship validator, not SQL. |

**Foreign-key relationships:**
- `attempt_id` → `attempts.attempt_id`

## learning_paths

| Field | Type | Required | Allowed values | Units | Uniqueness | Default | Validation |
|---|---|---|---|---|---|---|---|
| path_id | TEXT | Yes | PATH-2026-000001 pattern | identifier | (path_id) | — | SQL PRIMARY KEY; generator should enforce ID convention |
| learner_id | TEXT | Yes | Existing learners.learner_id | identifier | No | — | SQL FOREIGN KEY; consistency across courses checked separately |
| course_id | TEXT | Yes | Existing courses.course_id | identifier | No | — | SQL FOREIGN KEY; consistency across courses checked separately |
| created_at | TEXT | Yes | ISO-8601 date/time text (or NULL when optional) | timestamp | No | — | Date syntax not enforced by SQL; chronological rules require validation |
| status | TEXT | Yes | ACTIVE, COMPLETED, CANCELLED | state/category | No | 'ACTIVE' | SQL CHECK restricts allowed values |

**Foreign-key relationships:**
- `course_id` → `courses.course_id`
- `learner_id` → `learners.learner_id`

## recommendations

| Field | Type | Required | Allowed values | Units | Uniqueness | Default | Validation |
|---|---|---|---|---|---|---|---|
| recommendation_id | TEXT | Yes | Non-empty unique text key | identifier | (recommendation_id) | — | SQL PRIMARY KEY; generator should enforce ID convention |
| learner_id | TEXT | Yes | Existing learners.learner_id | identifier | No | — | SQL FOREIGN KEY; consistency across courses checked separately |
| path_id | TEXT | Yes | Existing learning_paths.path_id | identifier | No | — | SQL FOREIGN KEY; consistency across courses checked separately |
| content_id | TEXT | Yes | Existing content_items.content_id | identifier | No | — | SQL FOREIGN KEY; consistency across courses checked separately |
| target_skill_id | TEXT | Yes | Existing skills.skill_id | identifier | No | — | SQL FOREIGN KEY; consistency across courses checked separately |
| generated_at | TEXT | Yes | ISO-8601 date/time text (or NULL when optional) | timestamp | No | — | Date syntax not enforced by SQL; chronological rules require validation |
| mastery_at_decision | REAL | No | 0–1 or NULL | fraction | No | — | SQL CHECK when not NULL |
| reason_code | TEXT | Yes | Text (non-empty expected) | text | No | — | SQL NOT NULL when required; non-empty text needs app validation; Explanation category; valid codes must be controlled by application logic. |
| rationale | TEXT | Yes | Text (non-empty expected) | text | No | — | SQL NOT NULL when required; non-empty text needs app validation |
| priority_rank | INTEGER | Yes | positive integer | rank | No | — | SQL CHECK: > 0 |

**Foreign-key relationships:**
- `target_skill_id` → `skills.skill_id`
- `content_id` → `content_items.content_id`
- `path_id` → `learning_paths.path_id`
- `learner_id` → `learners.learner_id`

## mastery_snapshots

| Field | Type | Required | Allowed values | Units | Uniqueness | Default | Validation |
|---|---|---|---|---|---|---|---|
| snapshot_id | TEXT | Yes | Non-empty unique text key | identifier | (snapshot_id) | — | SQL PRIMARY KEY; generator should enforce ID convention |
| learner_id | TEXT | Yes | Existing learners.learner_id | identifier | No | — | SQL FOREIGN KEY; consistency across courses checked separately |
| skill_id | TEXT | Yes | Existing skills.skill_id | identifier | No | — | SQL FOREIGN KEY; consistency across courses checked separately |
| mastery_score | REAL | Yes | 0–1 | fraction | No | — | SQL CHECK: BETWEEN 0 AND 1 |
| assessment_count | INTEGER | Yes | integer >= 0 | assessments | No | — | SQL CHECK: >= 0 |
| calculation_method | TEXT | Yes | Text (non-empty expected) | text | No | — | SQL NOT NULL when required; non-empty text needs app validation |
| calculated_at | TEXT | Yes | ISO-8601 date/time text (or NULL when optional) | timestamp | No | — | Date syntax not enforced by SQL; chronological rules require validation |

**Foreign-key relationships:**
- `skill_id` → `skills.skill_id`
- `learner_id` → `learners.learner_id`

## recommendation_events

| Field | Type | Required | Allowed values | Units | Uniqueness | Default | Validation |
|---|---|---|---|---|---|---|---|
| event_id | TEXT | Yes | Non-empty unique text key | identifier | (event_id) | — | SQL PRIMARY KEY; generator should enforce ID convention |
| recommendation_id | TEXT | Yes | Existing recommendations.recommendation_id | identifier | No | — | SQL FOREIGN KEY; consistency across courses checked separately |
| event_type | TEXT | Yes | GENERATED, STARTED, COMPLETED, SKIPPED | state/category | No | — | SQL CHECK restricts allowed values |
| occurred_at | TEXT | Yes | ISO-8601 date/time text (or NULL when optional) | timestamp | No | — | Date syntax not enforced by SQL; chronological rules require validation |

**Foreign-key relationships:**
- `recommendation_id` → `recommendations.recommendation_id`

## learning_path_steps

| Field | Type | Required | Allowed values | Units | Uniqueness | Default | Validation |
|---|---|---|---|---|---|---|---|
| step_id | TEXT | Yes | Non-empty unique text key | identifier | (step_id) | — | SQL PRIMARY KEY; generator should enforce ID convention |
| path_id | TEXT | Yes | Existing learning_paths.path_id | identifier | (path_id, step_number) | — | SQL FOREIGN KEY; consistency across courses checked separately |
| content_id | TEXT | Yes | Existing content_items.content_id | identifier | No | — | SQL FOREIGN KEY; consistency across courses checked separately |
| step_number | INTEGER | Yes | positive integer | position | (path_id, step_number) | — | SQL CHECK: > 0 |
| mastery_before | REAL | No | 0–1 or NULL | fraction | No | — | SQL CHECK when not NULL |
| mastery_after | REAL | No | 0–1 or NULL | fraction | No | — | SQL CHECK when not NULL |
| recorded_at | TEXT | Yes | ISO-8601 date/time text (or NULL when optional) | timestamp | No | — | Date syntax not enforced by SQL; chronological rules require validation |

**Foreign-key relationships:**
- `content_id` → `content_items.content_id`
- `path_id` → `learning_paths.path_id`

## Relationship cardinality and optionality

| Relationship | Cardinality | Implemented through | Optionality / notes |
|---|---|---|---|
| Course → Skill | 1:N | `skills.course_id` | Required |
| Course → ContentItem | 1:N | `content_items.course_id` | Required |
| Skill ↔ Skill (prerequisites) | N:M, self-referencing | `skill_prerequisites` | Active dates are optional at end |
| ContentItem ↔ Skill | N:M | `content_skills` | Mapping required to recommend for target skill |
| Learner → Attempt | 1:N | `attempts.learner_id` | Required |
| ContentItem → Attempt | 1:N | `attempts.content_id` | Required |
| Recommendation → Attempt | 1:N | `attempts.recommendation_id` | Optional on attempt |
| Attempt → AssessmentResult | 1:0..1 | `assessment_results.attempt_id` | Optional on attempt; unique assessment |
| Learner → LearningPath | 1:N | `learning_paths.learner_id` | Required |
| Course → LearningPath | 1:N | `learning_paths.course_id` | Required |
| LearningPath → Recommendation | 1:N | `recommendations.path_id` | Required |
| Learner → Recommendation | 1:N | `recommendations.learner_id` | Required |
| ContentItem → Recommendation | 1:N | `recommendations.content_id` | Required |
| Skill → Recommendation | 1:N | `recommendations.target_skill_id` | Required |
| Learner → MasterySnapshot | 1:N | `mastery_snapshots.learner_id` | Required |
| Skill → MasterySnapshot | 1:N | `mastery_snapshots.skill_id` | Required |
| Recommendation → RecommendationEvent | 1:N | `recommendation_events.recommendation_id` | Required |
| LearningPath → LearningPathStep | 1:N | `learning_path_steps.path_id` | Required |
| ContentItem → LearningPathStep | 1:N | `learning_path_steps.content_id` | Required |

## Effective dates and lifecycle

- `skill_prerequisites.effective_from` is required; `effective_to` is optional. The SQL schema verifies end >= start, but active-at-decision checks belong in recommendation logic.
- Learners: ACTIVE / INACTIVE. Courses: DRAFT / ACTIVE / ARCHIVED. Content: DRAFT / PUBLISHED / RETIRED.
- Learning paths: ACTIVE / COMPLETED / CANCELLED. Attempts: STARTED / COMPLETED / ABANDONED.
- Recommendation events: GENERATED / STARTED / COMPLETED / SKIPPED. Events are appended to preserve history.
- Status columns describe current state. The current schema does not enforce all allowed transition sequences or fully audit changes to status columns.

## Business-level invariants requiring validation

- A content-skill mapping must belong to the same course on both sides.
- Recommendation learner, learning path, content and skill must agree on learner and course.
- Prerequisite graph must be acyclic and the required mastery threshold must hold at recommendation time.
- Assessment results should correspond to completed attempts and occur at or after attempt completion.
- Mastery calculations must use assessment observations available no later than the calculation/decision time.
- IDs must follow the specified immutable conventions; SQLite TEXT PRIMARY KEY alone does not validate ID format.
- Path step numbering must advance and repeated no-progress paths should be flagged by a dedicated validator.
- Ground-truth labels belong in separate evaluation files, not in production input features.

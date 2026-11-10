import re
import sqlite3
from pathlib import Path

DATABASE = Path('data/learnpath.db')
OUTPUT = Path('data_dictionary.md')
TABLES = [
    'learners', 'courses', 'skills', 'skill_prerequisites', 'content_items',
    'content_skills', 'attempts', 'assessment_results', 'learning_paths',
    'recommendations', 'mastery_snapshots', 'recommendation_events',
    'learning_path_steps',
]

ENUMS = {
    ('learners', 'status'): 'ACTIVE, INACTIVE',
    ('courses', 'status'): 'DRAFT, ACTIVE, ARCHIVED',
    ('skill_prerequisites', 'status'): 'ACTIVE, INACTIVE',
    ('content_items', 'format'): 'VIDEO, ARTICLE, QUIZ, EXERCISE',
    ('content_items', 'status'): 'DRAFT, PUBLISHED, RETIRED',
    ('learning_paths', 'status'): 'ACTIVE, COMPLETED, CANCELLED',
    ('attempts', 'status'): 'STARTED, COMPLETED, ABANDONED',
    ('recommendation_events', 'event_type'): 'GENERATED, STARTED, COMPLETED, SKIPPED',
}

RANGES = {
    'difficulty': ('1–3', 'level', 'SQL CHECK: BETWEEN 1 AND 3'),
    'minimum_mastery': ('0–1', 'fraction', 'SQL CHECK: BETWEEN 0 AND 1'),
    'weight': ('greater than 0, at most 1', 'fraction', 'SQL CHECK: 0 < weight <= 1'),
    'score': ('0–100', 'points', 'SQL CHECK: BETWEEN 0 AND 100'),
    'mastery_score': ('0–1', 'fraction', 'SQL CHECK: BETWEEN 0 AND 1'),
    'mastery_at_decision': ('0–1 or NULL', 'fraction', 'SQL CHECK when not NULL'),
    'mastery_before': ('0–1 or NULL', 'fraction', 'SQL CHECK when not NULL'),
    'mastery_after': ('0–1 or NULL', 'fraction', 'SQL CHECK when not NULL'),
    'assessment_count': ('integer >= 0', 'assessments', 'SQL CHECK: >= 0'),
    'priority_rank': ('positive integer', 'rank', 'SQL CHECK: > 0'),
    'step_number': ('positive integer', 'position', 'SQL CHECK: > 0'),
    'duration_minutes': ('positive integer', 'minutes', 'SQL CHECK: > 0'),
}

ID_PATTERNS = {
    'learner_id': 'LRN-000001 pattern',
    'course_id': 'CRS-000001 pattern',
    'skill_id': 'SKL-000001 pattern',
    'content_id': 'CNT-000001 pattern',
    'attempt_id': 'ATT-LRN-000001-000001 pattern',
    'path_id': 'PATH-2026-000001 pattern',
}
EXTRA = {
    ('skill_prerequisites', 'skill_id'): 'Cannot equal required_skill_id; enforced by SQL CHECK.',
    ('skill_prerequisites', 'required_skill_id'): 'Cannot equal skill_id; enforced by SQL CHECK.',
    ('skill_prerequisites', 'effective_to'): 'If supplied, must be >= effective_from (SQL CHECK).',
    ('attempts', 'completed_at'): 'If supplied, must be >= started_at. Required when status is COMPLETED (SQL CHECK).',
    ('assessment_results', 'attempt_id'): 'One assessment per attempt (SQL UNIQUE).',
    ('recommendations', 'reason_code'): 'Explanation category; valid codes must be controlled by application logic.',
    ('content_items', 'published_at'): 'Publishing lifecycle consistency requires application validation.',
    ('assessment_results', 'assessed_at'): 'Should follow attempt completion; checked by relationship validator, not SQL.',
}

RELATIONSHIPS = [
    ('Course → Skill', '1:N', 'skills.course_id', 'Required'),
    ('Course → ContentItem', '1:N', 'content_items.course_id', 'Required'),
    ('Skill ↔ Skill (prerequisites)', 'N:M, self-referencing', 'skill_prerequisites', 'Active dates are optional at end'),
    ('ContentItem ↔ Skill', 'N:M', 'content_skills', 'Mapping required to recommend for target skill'),
    ('Learner → Attempt', '1:N', 'attempts.learner_id', 'Required'),
    ('ContentItem → Attempt', '1:N', 'attempts.content_id', 'Required'),
    ('Recommendation → Attempt', '1:N', 'attempts.recommendation_id', 'Optional on attempt'),
    ('Attempt → AssessmentResult', '1:0..1', 'assessment_results.attempt_id', 'Optional on attempt; unique assessment'),
    ('Learner → LearningPath', '1:N', 'learning_paths.learner_id', 'Required'),
    ('Course → LearningPath', '1:N', 'learning_paths.course_id', 'Required'),
    ('LearningPath → Recommendation', '1:N', 'recommendations.path_id', 'Required'),
    ('Learner → Recommendation', '1:N', 'recommendations.learner_id', 'Required'),
    ('ContentItem → Recommendation', '1:N', 'recommendations.content_id', 'Required'),
    ('Skill → Recommendation', '1:N', 'recommendations.target_skill_id', 'Required'),
    ('Learner → MasterySnapshot', '1:N', 'mastery_snapshots.learner_id', 'Required'),
    ('Skill → MasterySnapshot', '1:N', 'mastery_snapshots.skill_id', 'Required'),
    ('Recommendation → RecommendationEvent', '1:N', 'recommendation_events.recommendation_id', 'Required'),
    ('LearningPath → LearningPathStep', '1:N', 'learning_path_steps.path_id', 'Required'),
    ('ContentItem → LearningPathStep', '1:N', 'learning_path_steps.content_id', 'Required'),
]


def field_details(table, field, sql_type, is_pk, foreign_keys):
    if (table, field) in ENUMS:
        return ENUMS[(table, field)], 'state/category', 'SQL CHECK restricts allowed values'
    if field in RANGES:
        return RANGES[field]
    if field in foreign_keys:
        target = foreign_keys[field]
        return f'Existing {target}', 'identifier', 'SQL FOREIGN KEY; consistency across courses checked separately'
    if field.endswith('_id'):
        allowed = ID_PATTERNS.get(field, 'Non-empty unique text key')
        rule = 'SQL PRIMARY KEY; generator should enforce ID convention' if is_pk else 'Identifier consistency checked by application'
        return allowed, 'identifier', rule
    if field.endswith('_at') or field in ('effective_from', 'effective_to'):
        return 'ISO-8601 date/time text (or NULL when optional)', 'timestamp', 'Date syntax not enforced by SQL; chronological rules require validation'
    if field in ('name', 'title', 'rationale', 'calculation_method', 'reason_code'):
        return 'Text (non-empty expected)', 'text', 'SQL NOT NULL when required; non-empty text needs app validation'
    return f'{sql_type} value', '—', 'No additional field-level SQL CHECK'


def unique_labels(conn, table):
    result = {}
    for _, index_name, is_unique, *_ in conn.execute(f'PRAGMA index_list("{table}")'):
        if not is_unique:
            continue
        cols = [r[2] for r in conn.execute(f'PRAGMA index_info("{index_name}")')]
        for col in cols:
            result.setdefault(col, []).append('(' + ', '.join(cols) + ')')
    return result


def main():
    if not DATABASE.exists():
        raise SystemExit(f'Missing database: {DATABASE}')
    conn = sqlite3.connect(f'file:{DATABASE.as_posix()}?mode=ro', uri=True)
    existing = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    missing = [table for table in TABLES if table not in existing]
    if missing:
        raise SystemExit(f'Missing tables: {missing}')

    lines = [
        '# LearnPath AI — Data Dictionary', '',
        'Generated from the current SQLite database schema. Contains the ten required business entities and three supporting history tables.',
        '', 'The **Validation** column distinguishes SQL constraints from rules that need application-level checks.',
        'Expected ID patterns and ISO-8601 dates are conventions unless a database CHECK explicitly enforces them.', '',
    ]

    for table in TABLES:
        lines += [f'## {table}', '',
                  '| Field | Type | Required | Allowed values | Units | Uniqueness | Default | Validation |',
                  '|---|---|---|---|---|---|---|---|']
        unique = unique_labels(conn, table)
        foreign = {r[3]: f'{r[2]}.{r[4]}' for r in conn.execute(f'PRAGMA foreign_key_list("{table}")')}
        for col in conn.execute(f'PRAGMA table_info("{table}")'):
            _, name, sql_type, notnull, default, pk = col
            allowed, units, validation = field_details(table, name, sql_type, bool(pk), foreign)
            if (table, name) in EXTRA:
                validation += '; ' + EXTRA[(table, name)]
            required = 'Yes' if notnull or pk else 'No'
            uniqueness = '; '.join(unique.get(name, [])) or 'No'
            default = str(default) if default is not None else '—'
            cells = [name, sql_type, required, allowed, units, uniqueness, default, validation]
            lines.append('| ' + ' | '.join(str(cell).replace('|', '\\|') for cell in cells) + ' |')
        lines += ['', '**Foreign-key relationships:**']
        lines += [f'- `{field}` → `{target}`' for field, target in foreign.items()] or ['- None']
        lines.append('')

    lines += [
        '## Relationship cardinality and optionality', '',
        '| Relationship | Cardinality | Implemented through | Optionality / notes |',
        '|---|---|---|---|',
    ]
    lines += [f'| {a} | {b} | `{c}` | {d} |' for a, b, c, d in RELATIONSHIPS]
    lines += [
        '', '## Effective dates and lifecycle', '',
        '- `skill_prerequisites.effective_from` is required; `effective_to` is optional. The SQL schema verifies end >= start, but active-at-decision checks belong in recommendation logic.',
        '- Learners: ACTIVE / INACTIVE. Courses: DRAFT / ACTIVE / ARCHIVED. Content: DRAFT / PUBLISHED / RETIRED.',
        '- Learning paths: ACTIVE / COMPLETED / CANCELLED. Attempts: STARTED / COMPLETED / ABANDONED.',
        '- Recommendation events: GENERATED / STARTED / COMPLETED / SKIPPED. Events are appended to preserve history.',
        '- Status columns describe current state. The current schema does not enforce all allowed transition sequences or fully audit changes to status columns.',
        '', '## Business-level invariants requiring validation', '',
        '- A content-skill mapping must belong to the same course on both sides.',
        '- Recommendation learner, learning path, content and skill must agree on learner and course.',
        '- Prerequisite graph must be acyclic and the required mastery threshold must hold at recommendation time.',
        '- Assessment results should correspond to completed attempts and occur at or after attempt completion.',
        '- Mastery calculations must use assessment observations available no later than the calculation/decision time.',
        '- IDs must follow the specified immutable conventions; SQLite TEXT PRIMARY KEY alone does not validate ID format.',
        '- Path step numbering must advance and repeated no-progress paths should be flagged by a dedicated validator.',
        '- Ground-truth labels belong in separate evaluation files, not in production input features.',
        '',
    ]
    OUTPUT.write_text('\n'.join(lines), encoding='utf-8')
    conn.close()
    print(f'Created: {OUTPUT}')
    print(f'Tables documented: {len(TABLES)}')
    print('Required business entities: 10')
    print('Supplementary entities: 3')


if __name__ == '__main__':
    main()
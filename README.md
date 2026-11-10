# YottaFlex LearnPath AI

### Adaptive Learning Recommendation System

LearnPath AI is a personalized learning recommendation system developed for the **YottaFlex AI Forward Deployed Engineer Hackathon**.

Online learning platforms offer thousands of courses and activities, but choosing what to learn next can be difficult. LearnPath AI addresses this problem by analyzing a learner's assessment history, skill mastery, and prerequisites to recommend suitable learning activities.

The system also tracks completed activities and updates skill mastery as learners make progress.

## 1. Key Features

- **Personalized Recommendations:** Suggests learning activities based on individual skill levels.
- **Skill Mastery Tracking:** Calculates mastery using recent assessment performance.
- **Prerequisite Validation:** Checks whether learners are ready for advanced topics.
- **Explainable Recommendations:** Provides reason codes and explanations for recommended activities.
- **Learning Paths:** Maintains learning paths and recommendation history.
- **Activity Completion:** Records completed activities and assessment scores.
- **Progress Updates:** Recalculates mastery when new assessment results become available.
- **Interactive Dashboard:** Allows users to explore learners, recommendations, and progress.
- **Data Validation:** Includes automated integrity checks, temporal validation, and negative-case testing.
- **Reproducible Dataset:** Generates synthetic learning data using a fixed random seed.

## 2. Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python |
| Backend | FastAPI |
| Database | SQLite |
| Frontend | HTML, CSS, JavaScript |
| API Validation | Pydantic |
| Testing | Pytest |
| Data Processing | Python |
| Data Formats | CSV, JSON, SQL |
| Version Control | Git, GitHub |

The application uses SQLite to keep local setup simple. FastAPI provides the backend APIs and serves the dashboard.

## 3. Dataset Overview

The project uses a synthetic dataset generated with the fixed random seed `20261022`.

The baseline dataset contains 10,000 learners, 500 skills, 2,000 learning activities, and 500,000 assessment attempts.

### Latest Dataset Statistics

The following values represent the local demonstration database exported on **November 10, 2026**.

| Entity | Records |
|---|---:|
| Learners | 10,000 |
| Courses | 50 |
| Skills | 500 |
| Skill Prerequisites | 450 |
| Content Items | 2,000 |
| Content-Skill Mappings | 2,000 |
| Learning Attempts | 500,008 |
| Assessment Results | 500,008 |
| Mastery Snapshots | 179,492 |
| Learning Paths | 2 |
| Recommendations | 31 |
| Recommendation Events | 39 |
| Learning Path Steps | 8 |
| **Total** | **1,194,588** |

The additional attempts and related records were created while testing the recommendation and activity-completion workflow.

The database contains 13 related tables with foreign-key relationships.

The database structure and field definitions are documented in `schema.sql` and `data_dictionary.md`.

**All learner information is synthetic. No real student data is used.**

## 4. How the System Works

LearnPath AI connects assessment history with personalized learning recommendations.

### Skill Mastery Calculation

The system calculates skill mastery using a recency-weighted average of up to five recent assessment scores.

Recent results receive greater weight because they better reflect a learner's current performance.

Mastery scores range from `0.0` to `1.0` and are displayed as percentages in the dashboard.

The calculation also considers assessment timestamps to prevent future results from influencing historical recommendations.

### Recommendation Generation

The recommendation engine:

1. Retrieves the learner's assessment history.
2. Calculates mastery for relevant skills.
3. Identifies skills that need improvement.
4. Checks prerequisite requirements.
5. Finds suitable learning activities.
6. Ranks activities using mastery, difficulty, and duration.
7. Stores recommendations with explanations.

Recommendations include reason codes such as:

- `MASTERY_GAP`
- `LOW_MASTERY`
- `COLD_START_OR_NEW_SKILL`

These help explain why a particular activity was selected.

### Activity Completion

When a learner completes a recommended activity, the system records the assessment score, saves the attempt, updates learning-path progress, and recalculates mastery.

The learner can then receive new recommendations based on the updated assessment history.

**Workflow:**

```text
Learner
   |
   v
Assessment History
   |
   v
Skill Mastery Calculation
   |
   v
Prerequisite Checking
   |
   v
Personalized Recommendations
   |
   v
Learning Activity
   |
   v
Assessment Result
   |
   v
Updated Skill Mastery
```

## 5. Project Structure

```text
YottaFlex-LearnPath-AI/
|
|-- app/
|   |-- database.py
|   |-- main.py
|   |-- mastery.py
|   |-- recommender.py
|   `-- outcomes.py
|
|-- frontend/
|   `-- index.html
|
|-- dashboard/
|   `-- app.py
|
|-- generator/
|   |-- generate_master.py
|   |-- generate_attempts.py
|   |-- export_dataset.py
|   `-- export_sql_seed.py
|
|-- validation/
|   |-- validate_data.py
|   |-- validate_relationships.py
|   |-- validate_temporal_mastery.py
|   |-- validate_reproducibility.py
|   |-- validate_sql_restore.py
|   |-- negative_case_benchmark.py
|   `-- verify_exports.py
|
|-- evaluation/
|   |-- evaluate.py
|   |-- recommendations.py
|   `-- temporal_evaluation.py
|
|-- tests/
|-- exports/
|-- reports/
|
|-- schema.sql
|-- data_dictionary.md
|-- requirements.txt
|-- .gitignore
`-- README.md
```

The backend, dataset generation, validation, and evaluation components are separated to make the project easier to understand and maintain.

## 6. Installation and Setup

### Requirements

- Python 3.11 or later
- Git
- VS Code or another code editor

The project was developed using Python 3.14.3 on Windows.

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd YottaFlex-LearnPath-AI
```

Replace `<repository-url>` with the published GitHub repository URL.

### Step 2: Create a Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Step 3: Install Dependencies

```powershell
python -m pip install -r requirements.txt
```

### Step 4: Initialize the Database

```powershell
python -m app.database
```

### Step 5: Generate the Dataset

For the full dataset:

```powershell
python -m generator.generate_master --scale full
python -m generator.generate_attempts --scale full
python -m app.mastery
python -m app.recommender --learner LRN-000001
```

For a smaller dataset suitable for quick testing:

```powershell
python -m generator.generate_master --scale starter
python -m generator.generate_attempts --scale starter
python -m app.mastery
```

**Note:** Run the dataset generators against a fresh database. Running them again on an existing database may interfere with previously generated or recorded data.

### Step 6: Start the Application

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

Open the dashboard:

```text
http://127.0.0.1:8000/dashboard
```

FastAPI documentation:

```text
http://127.0.0.1:8000/docs
```

## 7. Dashboard and API

The dashboard provides a simple interface for exploring the recommendation workflow.

Users can select a learner, view skill mastery, generate recommendations, complete activities, and observe changes in mastery scores.

### Main API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Application health |
| GET | `/api/stats` | Dataset statistics |
| GET | `/api/learners` | List learners |
| GET | `/api/learners/{learner_id}` | Learner details |
| GET | `/api/learners/{learner_id}/mastery` | Current skill mastery |
| POST | `/api/learners/{learner_id}/recommend` | Generate recommendations |
| GET | `/api/learners/{learner_id}/recommendations` | Recommendation history |
| GET | `/api/learners/{learner_id}/paths` | Learning paths |
| GET | `/api/recommendations/{recommendation_id}/events` | Recommendation events |
| POST | `/api/recommendations/{recommendation_id}/complete` | Record activity completion |

The complete API documentation is available through FastAPI's interactive documentation page.

## 8. Testing and Validation

The project includes automated tests and independent validation scripts to check data integrity, recommendation behavior, temporal correctness, and reproducibility.

### Run Automated Tests

```powershell
python -m pytest -q
```

Latest verified result:

```text
15 passed, 1 warning
```

All 15 tests passed on November 10, 2026. The warning was related to a third-party test-client deprecation.

### Validation Results

| Validation | Result |
|---|---|
| Automated Tests | 15/15 PASS |
| Relationship Validation | 9/9 PASS |
| Negative-Case Benchmark | 10/10 PASS |
| Temporal Mastery Validation | 31/31 PASS |
| Starter Dataset Reproducibility | PASS |
| Full Dataset Reproducibility | PASS |
| SQL Restoration | 13/13 PASS |
| Foreign-Key Violations | 0 |
| Database Integrity | OK |

### Validation Commands

```powershell
python -m validation.validate_data
python -m validation.validate_relationships
python -m validation.negative_case_benchmark
python -m validation.validate_temporal_mastery
```

The negative-case benchmark includes five labelled negative cases and five control cases, with ground truth stored separately from the validation inputs.

### Reproducibility

Dataset reproducibility was verified for both starter and full scales.

```powershell
python -m validation.validate_reproducibility --scale starter
python -m validation.validate_reproducibility --scale full
```

The validation compares independently generated datasets using record counts and SHA-256 hashes.

Results are stored in the `reports/` directory.

## 9. Evaluation Results

The project includes recommendation checks and a temporal assessment-score evaluation.

### Recommendation Evaluation

```powershell
python -m evaluation.recommendations
```

An initial set of four recommendations passed the implemented checks for relevance, prerequisite compliance, course consistency, and traceability.

### Temporal Evaluation

```powershell
python -m evaluation.temporal_evaluation
```

The evaluation uses an 80/20 chronological split and a historical assessment-score prediction baseline.

| Metric | Result |
|---|---:|
| RMSE | 15.4866 |
| Predictions within 20 points | 79.78% |

These metrics measure assessment-score prediction rather than the overall effectiveness of the recommendation system.

Detailed results are available in `reports/temporal_evaluation.json`.

## 10. Dataset Exports

The project supports CSV, JSON, and SQL exports.

### CSV and JSON

```powershell
python -m generator.export_dataset
```

Verify exported files using:

```powershell
python -m validation.verify_exports
```

The export process creates dataset files, JSON samples, and a manifest containing record counts and SHA-256 checksums.

### SQL Seed Export

```powershell
python -m generator.export_sql_seed
```

The latest SQL export contains **1,194,588 records across 13 tables**.

SQL seed files are generated in:

```text
exports/sql/
```

### SQL Restoration Validation

```powershell
python -m validation.validate_sql_restore
```

Latest result:

```text
Tables checked: 13
Foreign-key violations: 0
Integrity: ok
Overall: PASS
```

### Large Dataset Files

The complete SQL seed is approximately **249.17 MiB**, which exceeds GitHub's normal 100 MB per-file limit.

Large generated files are therefore excluded from the Git repository through `.gitignore`.

These include the local SQLite database, large CSV exports, and the SQL seed.

The repository contains the generation scripts, smaller exports, JSON samples, manifests, and validation reports.

Reviewers can regenerate a fresh full-scale dataset locally using the documented commands.

The exact demonstration-state SQL seed is not included in Git and would need to be shared separately if required.

## 11. Limitations and Future Improvements

LearnPath AI was developed as a hackathon prototype, with an emphasis on building a working and explainable recommendation system.

Current limitations include:

- The dataset is synthetic rather than collected from real learners.
- Recommendations use rule-based ranking rather than a trained recommendation model.
- Recommendation evaluation covers a limited number of examples.
- The dashboard is designed for local demonstration rather than production deployment.
- The negative-case benchmark does not establish general anomaly-detection accuracy.

Future improvements could include evaluating recommendations on real educational datasets, expanding recommendation-quality benchmarks, introducing machine-learning-based ranking, and deploying the application with authentication and monitoring.

---

## Conclusion

LearnPath AI demonstrates how learner assessment history, skill mastery, prerequisites, and activity outcomes can work together to support personalized learning.

The project brings together a functional recommendation engine, an interactive dashboard, synthetic data generation, and automated validation in a single application.

The main objective was to build a system that is **explainable, reproducible, and easy to test**, while demonstrating the complete learning recommendation workflow.

**Developed for the YottaFlex AI Forward Deployed Engineer Hackathon.**
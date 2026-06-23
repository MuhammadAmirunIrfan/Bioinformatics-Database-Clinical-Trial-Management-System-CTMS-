# CTMS Mini Project — Clinical Trial Management System

SECB3213 Mini Project | Use Case 1: Clinical Trial Management System (CTMS)

## Prerequisites

- **MongoDB** (v6+) running on `localhost:27017`
- **Python 3.10+**
- Install dependencies:

```bash
pip install pymongo fastapi uvicorn streamlit requests plotly pandas
```

## Quick Start

### 1. Ingest Data (D2)

```bash
cd D2_ingestion
python ingest.py
```

This creates the `ctms_db` database with 4 collections, applies `$jsonSchema` validators,
loads all CSV data, verifies referential consistency, and prints document counts + samples.

### 2. Export Database Backup (D3)

Run immediately after ingestion, before any manual changes:

```bash
mongodump --db=ctms_db --archive=D3_backup/ctms_backup.tar.gz --gzip
```

### 3. Run Queries (D4)

```bash
cd D4_queries
python queries.py
```

Runs all 10 analytical requirement pipelines and prints results.
To save output for the PDF: `python queries.py > query_results.txt`

### 4. Start the API Server (D5)

```bash
cd D5_api
uvicorn app:app --reload --port 8000
```

Swagger UI available at: [http://localhost:8000/docs](http://localhost:8000/docs)

### 5. Launch the Portal (D6)

In a **separate terminal** (keep the API server running):

```bash
cd D6_portal
streamlit run portal.py
```

Portal opens at: [http://localhost:8501](http://localhost:8501)

## Project Structure

```
D1_schemas/          — $jsonSchema validators (.json)
D2_ingestion/        — Ingestion script + data + schemas
D3_backup/           — mongodump archive
D4_queries/          — Standalone query script + results
D5_api/              — FastAPI application
D6_portal/           — Streamlit portal
D7_report/           — Technical report (PDF)
D8_video/            — Demonstration video
AI_Declaration/      — AI conversation logs
README.md            — This file
```

## API Endpoints

| AR   | Endpoint                                                          | Method |
|------|-------------------------------------------------------------------|--------|
| AR-01| `/api/trials?status=...&phase=...&sponsor=...`                    | GET    |
| AR-02| `/api/trials/{trial_id}/patients?gender=...`                      | GET    |
| AR-03| `/api/patients?gender=...&ethnicity=...&site_id=...`              | GET    |
| AR-04| `/api/patients/{patient_id}/adverse-events?min_grade=...`         | GET    |
| AR-05| `/api/analytics/adverse-events/by-intervention-type`              | GET    |
| AR-06| `/api/analytics/enrolment-progress?sponsor=...&phase=...`         | GET    |
| AR-07| `/api/trials/{trial_id}/adverse-events/causality-severity-matrix` | GET    |
| AR-08| `/api/analytics/comorbidity-ae-burden?min_comorbidities=...`      | GET    |
| AR-09| `/api/interventions?target_gene=...&target_protein=...`           | GET    |
| AR-10| `/api/analytics/adverse-events/monthly-trend?trial_id=...`       | GET    |

## Portal Features

1. **Trial Browser** — Filter by status, phase, sponsor (AR-01)
2. **Patient Search** — Demographic/clinical search + by-trial view (AR-02, AR-03)
3. **AE Monitor** — Colour-coded severity table + causality-severity heatmap (AR-04, AR-07)
4. **Analytics** — AE by type, monthly trends, comorbidity burden, gene search (AR-05, AR-08, AR-09, AR-10)
5. **Enrolment Explorer** — Completion % dashboard with charts (AR-06)

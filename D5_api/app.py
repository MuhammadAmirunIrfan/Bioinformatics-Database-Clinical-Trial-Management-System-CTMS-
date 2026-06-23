"""
SECB3213 Mini Project — D5: FastAPI Implementation
Clinical Trial Management System (CTMS)

All 10 analytical requirements exposed as generalizable GET endpoints.
Follows the naming conventions from Section 5 of the brief:
- Lowercase hyphen-separated URLs
- Plural nouns for collections
- Path params for required identifiers
- Query params for optional filters + pagination
- Response envelope: { total, page, limit, data }
- Error handling: 404, 422, 500

Usage:
    uvicorn app:app --reload --port 8000
    Then open http://localhost:8000/docs for Swagger UI
"""

from fastapi import FastAPI, Query, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from typing import Optional
import math

# App Setup 

app = FastAPI(
    title="CTMS API",
    description="Clinical Trial Management System — RESTful API for Meridian Clinical Research Institute",
    version="1.0.0",
)

# Allow portal (Streamlit) to call the API from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# MongoDB connection
client = MongoClient("mongodb+srv://muhammadamirunirfan_db_user:5XVqN7CNFlW457h2@cluster0.nkmouka.mongodb.net/?appName=Cluster0")
db = client["ctms_db"]


#  Helper 

def paginate(data: list, page: int, limit: int) -> dict:
    """Apply pagination to a list of results and return the response envelope."""
    total = len(data)
    start = (page - 1) * limit
    end = start + limit
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "data": data[start:end],
    }


def paginate_cursor(collection, filter_dict: dict, projection: dict, page: int, limit: int, sort=None) -> dict:
    """Paginate a simple find() query using skip/limit for efficiency."""
    total = collection.count_documents(filter_dict)
    skip = (page - 1) * limit
    cursor = collection.find(filter_dict, projection).skip(skip).limit(limit)
    if sort:
        cursor = cursor.sort(sort)
    data = list(cursor)
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "data": data,
    }


#  AR-01: Filter trials by status and/or phase 

@app.get("/api/trials", tags=["Trials"])
def get_trials(
    status: Optional[str] = Query(None, description="Filter by trial status, e.g. Recruiting"),
    phase: Optional[str] = Query(None, description="Filter by trial phase, e.g. Phase II"),
    sponsor: Optional[str] = Query(None, description="Filter by sponsor name"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
):
    """
    AR-01: Retrieve a list of clinical trials filtered by status, phase, and/or sponsor.
    All filters are optional and can be combined.
    """
    query = {}
    if status:
        query["status"] = status
    if phase:
        query["phase"] = phase
    if sponsor:
        query["sponsor"] = {"$regex": sponsor, "$options": "i"}

    projection = {"_id": 0}
    return paginate_cursor(db.trials, query, projection, page, limit, sort=[("trial_id", 1)])


#  AR-02: Retrieve all patients for a specific trial 

@app.get("/api/trials/{trial_id}/patients", tags=["Trials"])
def get_trial_patients(
    trial_id: str = Path(..., description="Trial ID, e.g. NCT-20240001"),
    gender: Optional[str] = Query(None, description="Filter by gender"),
    ethnicity: Optional[str] = Query(None, description="Filter by ethnicity"),
    smoking_status: Optional[str] = Query(None, description="Filter by smoking status"),
    site_id: Optional[str] = Query(None, description="Filter by site"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """
    AR-02: Given a trial, retrieve demographic details of all enrolled patients.
    Results can be narrowed by patient attributes.
    """
    # Verify trial exists
    if not db.trials.find_one({"trial_id": trial_id}):
        raise HTTPException(status_code=404, detail=f"Trial {trial_id} not found")

    query = {"enrolled_trials": trial_id}
    if gender:
        query["gender"] = gender
    if ethnicity:
        query["ethnicity"] = ethnicity
    if smoking_status:
        query["smoking_status"] = smoking_status
    if site_id:
        query["site_id"] = site_id

    projection = {"_id": 0}
    return paginate_cursor(db.patients, query, projection, page, limit, sort=[("patient_id", 1)])


#  AR-03: Search patients by demographic or clinical criteria 

@app.get("/api/patients", tags=["Patients"])
def search_patients(
    gender: Optional[str] = Query(None, description="Filter by gender"),
    ethnicity: Optional[str] = Query(None, description="Filter by ethnicity"),
    site_id: Optional[str] = Query(None, description="Filter by research site"),
    smoking_status: Optional[str] = Query(None, description="Filter by smoking status"),
    blood_type: Optional[str] = Query(None, description="Filter by blood type"),
    diagnosis_code: Optional[str] = Query(None, description="Filter by ICD-10 code prefix, e.g. C34"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """
    AR-03: Search across the patient population using combinations of
    demographic and clinical attributes.
    """
    query = {}
    if gender:
        query["gender"] = gender
    if ethnicity:
        query["ethnicity"] = ethnicity
    if site_id:
        query["site_id"] = site_id
    if smoking_status:
        query["smoking_status"] = smoking_status
    if blood_type:
        query["blood_type"] = blood_type
    if diagnosis_code:
        # Prefix match on ICD-10 code (e.g. C34 matches C34.1, C34.9)
        query["diagnosis.icd10_code"] = {"$regex": f"^{diagnosis_code}", "$options": "i"}

    projection = {"_id": 0}
    return paginate_cursor(db.patients, query, projection, page, limit, sort=[("patient_id", 1)])


#  AR-04: Retrieve all adverse events for a patient 

@app.get("/api/patients/{patient_id}/adverse-events", tags=["Patients"])
def get_patient_adverse_events(
    patient_id: str = Path(..., description="Patient ID, e.g. PT-000001"),
    min_grade: Optional[int] = Query(None, ge=1, le=5, description="Minimum CTCAE grade filter"),
    causality: Optional[str] = Query(None, description="Filter by causality assessment"),
    trial_id: Optional[str] = Query(None, description="Filter by specific trial"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """
    AR-04: Given a patient, retrieve all adverse events across all trials,
    with optional filters by severity, causality, or trial.
    """
    if not db.patients.find_one({"patient_id": patient_id}):
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")

    query = {"patient_id": patient_id}
    if min_grade:
        query["ctcae_grade"] = {"$gte": min_grade}
    if causality:
        query["causality"] = causality
    if trial_id:
        query["trial_id"] = trial_id

    projection = {"_id": 0}
    return paginate_cursor(db.adverse_events, query, projection, page, limit, sort=[("onset_date", -1)])


#  AR-05: AE summary grouped by intervention type 

@app.get("/api/analytics/adverse-events/by-intervention-type", tags=["Analytics"])
def ae_summary_by_intervention_type():
    """
    AR-05: Aggregate adverse events grouped by intervention type,
    returning counts and proportion of serious events per type.

    Pipeline: Lookup intervention for each AE -> group by intervention type ->
    calculate total count and serious count -> compute serious proportion.
    """
    pipeline = [
        # Join AE to its intervention to get the intervention type
        {
            "$lookup": {
                "from": "interventions",
                "localField": "intervention_id",
                "foreignField": "intervention_id",
                "as": "intervention",
            }
        },
        {"$unwind": "$intervention"},

        # Group by intervention type
        {
            "$group": {
                "_id": "$intervention.type",
                "total_ae_count": {"$sum": 1},
                "serious_count": {
                    "$sum": {"$cond": ["$serious", 1, 0]}
                },
            }
        },

        # Calculate proportion and rename fields
        {
            "$project": {
                "_id": 0,
                "intervention_type": "$_id",
                "total_ae_count": 1,
                "serious_count": 1,
                "serious_proportion": {
                    "$round": [
                        {"$cond": [
                            {"$eq": ["$total_ae_count", 0]},
                            0,
                            {"$divide": ["$serious_count", "$total_ae_count"]},
                        ]},
                        4,
                    ]
                },
            }
        },

        {"$sort": {"total_ae_count": -1}},
    ]

    data = list(db.adverse_events.aggregate(pipeline))
    return {"total": len(data), "page": 1, "limit": len(data), "data": data}


#  AR-06: Enrolment progress across trials 

@app.get("/api/analytics/enrolment-progress", tags=["Analytics"])
def enrolment_progress(
    sponsor: Optional[str] = Query(None, description="Filter by sponsor"),
    phase: Optional[str] = Query(None, description="Filter by trial phase"),
    status: Optional[str] = Query(None, description="Filter by trial status"),
):
    """
    AR-06: Calculate enrolment completion as a percentage of target for each trial,
    with optional filters by sponsor, phase, or status.

    Pipeline: Match (optional filters) -> Project completion percentage.
    """
    match_stage = {}
    if sponsor:
        match_stage["sponsor"] = {"$regex": sponsor, "$options": "i"}
    if phase:
        match_stage["phase"] = phase
    if status:
        match_stage["status"] = status

    pipeline = []
    if match_stage:
        pipeline.append({"$match": match_stage})

    pipeline.extend([
        {
            "$project": {
                "_id": 0,
                "trial_id": 1,
                "short_title": 1,
                "phase": 1,
                "status": 1,
                "sponsor": 1,
                "enrolment_target": 1,
                "enrolled_count": 1,
                "completion_pct": {
                    "$round": [
                        {"$cond": [
                            {"$eq": ["$enrolment_target", 0]},
                            0,
                            {"$multiply": [
                                {"$divide": ["$enrolled_count", "$enrolment_target"]},
                                100,
                            ]},
                        ]},
                        2,
                    ]
                },
            }
        },
        {"$sort": {"completion_pct": -1}},
    ])

    data = list(db.trials.aggregate(pipeline))
    return {"total": len(data), "page": 1, "limit": len(data), "data": data}


#  AR-07: AE causality-severity matrix for a trial 

@app.get("/api/trials/{trial_id}/adverse-events/causality-severity-matrix", tags=["Trials"])
def ae_causality_severity_matrix(
    trial_id: str = Path(..., description="Trial ID, e.g. NCT-20240001"),
):
    """
    AR-07: For a given trial, produce a cross-tabulation of adverse events
    by causality rating and CTCAE grade.

    Pipeline: Match AEs for the trial -> Group by (causality, grade) -> Reshape
    into a matrix structure.
    """
    if not db.trials.find_one({"trial_id": trial_id}):
        raise HTTPException(status_code=404, detail=f"Trial {trial_id} not found")

    pipeline = [
        {"$match": {"trial_id": trial_id}},

        # Group by causality + grade combination
        {
            "$group": {
                "_id": {
                    "causality": "$causality",
                    "ctcae_grade": "$ctcae_grade",
                },
                "count": {"$sum": 1},
            }
        },

        # Reshape for readability
        {
            "$project": {
                "_id": 0,
                "causality": "$_id.causality",
                "ctcae_grade": "$_id.ctcae_grade",
                "count": 1,
            }
        },

        {"$sort": {"causality": 1, "ctcae_grade": 1}},
    ]

    data = list(db.adverse_events.aggregate(pipeline))
    return {"total": len(data), "page": 1, "limit": len(data), "data": data}


#  AR-08: Patient comorbidity and AE burden 

@app.get("/api/analytics/comorbidity-ae-burden", tags=["Analytics"])
def comorbidity_ae_burden(
    min_comorbidities: int = Query(1, ge=0, description="Minimum number of comorbidities threshold"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """
    AR-08: Identify patients whose comorbidity count exceeds a threshold
    and return their total and serious AE counts.

    Pipeline: Add comorbidity count -> Filter by threshold ->
    Lookup AEs -> Calculate total and serious counts.
    """
    pipeline = [
        # Calculate comorbidity count
        {
            "$addFields": {
                "comorbidity_count": {"$size": "$comorbidities"},
            }
        },

        # Filter patients above threshold
        {"$match": {"comorbidity_count": {"$gte": min_comorbidities}}},

        # Lookup all adverse events for each patient
        {
            "$lookup": {
                "from": "adverse_events",
                "localField": "patient_id",
                "foreignField": "patient_id",
                "as": "aes",
            }
        },

        # Calculate AE burden
        {
            "$project": {
                "_id": 0,
                "patient_id": 1,
                "name": 1,
                "comorbidity_count": 1,
                "comorbidities": 1,
                "total_ae_count": {"$size": "$aes"},
                "serious_ae_count": {
                    "$size": {
                        "$filter": {
                            "input": "$aes",
                            "as": "ae",
                            "cond": {"$eq": ["$$ae.serious", True]},
                        }
                    }
                },
            }
        },

        {"$sort": {"comorbidity_count": -1, "total_ae_count": -1}},
    ]

    data = list(db.patients.aggregate(pipeline))
    return paginate(data, page, limit)


#  AR-09: Interventions by gene or protein target 

@app.get("/api/interventions", tags=["Interventions"])
def search_interventions(
    target_gene: Optional[str] = Query(None, description="HGNC gene symbol, e.g. EGFR, BRCA1"),
    target_protein: Optional[str] = Query(None, description="Protein name substring, e.g. PD-1"),
    intervention_type: Optional[str] = Query(None, description="Filter by type, e.g. Drug, Biologic"),
    trial_id: Optional[str] = Query(None, description="Filter by trial"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    """
    AR-09: Retrieve interventions targeting a specified gene symbol or protein,
    including trial context and regulatory status.

    Also supports filtering by type and trial_id for general intervention browsing.
    """
    # Build the query — use $lookup to include trial context
    match_stage = {}
    if target_gene:
        match_stage["target_gene"] = {"$regex": target_gene, "$options": "i"}
    if target_protein:
        match_stage["target_protein"] = {"$regex": target_protein, "$options": "i"}
    if intervention_type:
        match_stage["type"] = intervention_type
    if trial_id:
        match_stage["trial_id"] = trial_id

    pipeline = []
    if match_stage:
        pipeline.append({"$match": match_stage})

    pipeline.extend([
        # Join to trials for context
        {
            "$lookup": {
                "from": "trials",
                "localField": "trial_id",
                "foreignField": "trial_id",
                "as": "trial",
            }
        },
        {"$unwind": "$trial"},

        {
            "$project": {
                "_id": 0,
                "intervention_id": 1,
                "name": 1,
                "type": 1,
                "mechanism": 1,
                "target_gene": 1,
                "target_protein": 1,
                "regulatory_status": 1,
                "dosage": 1,
                "duration_weeks": 1,
                "arm_label": 1,
                "trial_id": 1,
                "trial_title": "$trial.short_title",
                "trial_phase": "$trial.phase",
                "trial_status": "$trial.status",
            }
        },

        {"$sort": {"intervention_id": 1}},
    ])

    data = list(db.interventions.aggregate(pipeline))
    return paginate(data, page, limit)


#  AR-10: Monthly AE trend over time 

@app.get("/api/analytics/adverse-events/monthly-trend", tags=["Analytics"])
def ae_monthly_trend(
    trial_id: Optional[str] = Query(None, description="Scope to a specific trial"),
    intervention_type: Optional[str] = Query(None, description="Filter by intervention type, e.g. Drug"),
):
    """
    AR-10: Produce a time-series of adverse event counts grouped by year and month,
    with optional scoping to a specific trial or intervention type.

    Pipeline: Optional match -> Optional lookup for intervention type filter ->
    Group by year-month -> Sort chronologically.
    """
    pipeline = []

    # Optional trial filter (applied before lookup for efficiency)
    match_stage = {}
    if trial_id:
        match_stage["trial_id"] = trial_id

    if match_stage:
        pipeline.append({"$match": match_stage})

    # If filtering by intervention type, we need to lookup the intervention
    if intervention_type:
        pipeline.extend([
            {
                "$lookup": {
                    "from": "interventions",
                    "localField": "intervention_id",
                    "foreignField": "intervention_id",
                    "as": "intervention",
                }
            },
            {"$unwind": "$intervention"},
            {"$match": {"intervention.type": intervention_type}},
        ])

    pipeline.extend([
        # Group by year and month extracted from onset_date
        {
            "$group": {
                "_id": {
                    "year": {"$year": "$onset_date"},
                    "month": {"$month": "$onset_date"},
                },
                "ae_count": {"$sum": 1},
            }
        },

        # Clean up output
        {
            "$project": {
                "_id": 0,
                "year": "$_id.year",
                "month": "$_id.month",
                "ae_count": 1,
            }
        },

        {"$sort": {"year": 1, "month": 1}},
    ])

    data = list(db.adverse_events.aggregate(pipeline))
    return {"total": len(data), "page": 1, "limit": len(data), "data": data}


#  Root 

@app.get("/", tags=["Root"])
def root():
    """API health check and endpoint directory."""
    return {
        "message": "CTMS API is running",
        "docs": "/docs",
        "endpoints": [
            "GET /api/trials                                          — AR-01: Filter trials",
            "GET /api/trials/{trial_id}/patients                      — AR-02: Trial patients",
            "GET /api/patients                                        — AR-03: Search patients",
            "GET /api/patients/{patient_id}/adverse-events            — AR-04: Patient AEs",
            "GET /api/analytics/adverse-events/by-intervention-type   — AR-05: AE by type",
            "GET /api/analytics/enrolment-progress                    — AR-06: Enrolment %",
            "GET /api/trials/{trial_id}/adverse-events/causality-severity-matrix — AR-07: Matrix",
            "GET /api/analytics/comorbidity-ae-burden                 — AR-08: Comorbidity+AE",
            "GET /api/interventions                                   — AR-09: Gene/protein search",
            "GET /api/analytics/adverse-events/monthly-trend          — AR-10: Monthly trend",
        ],
    }

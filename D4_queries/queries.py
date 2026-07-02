import os
from pymongo import MongoClient
from pprint import pprint
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

client = MongoClient(os.environ["MONGO_URI"])
db = client[os.environ.get("DB_NAME", "ctms_db")]


def print_header(ar_num, title, description):
    """Print a formatted section header for each AR."""
    print("\n" + "=" * 75)
    print(f"  AR-{ar_num:02d}: {title}")
    print(f"  {description}")
    print("=" * 75)


def run_query(collection_name, pipeline, label="Results"):
    """Execute an aggregation pipeline and print results."""
    results = list(db[collection_name].aggregate(pipeline))
    print(f"\n{label} ({len(results)} documents):")
    print("-" * 50)
    for doc in results:
        pprint(doc, width=100)
    if not results:
        print("  (no results)")
    return results


# AR-01: Filter trials by status and/or phase

print_header(1, "Filter trials by status and/or phase",
             "Example: Retrieve all trials with status='Recruiting'")

pipeline_ar01 = [
    {"$match": {"status": "Recruiting"}},
    {"$project": {
        "_id": 0,
        "trial_id": 1,
        "short_title": 1,
        "phase": 1,
        "status": 1,
        "sponsor": 1,
    }},
    {"$sort": {"trial_id": 1}},
]

print("\nPipeline:")
pprint(pipeline_ar01, width=90)
run_query("trials", pipeline_ar01)


# AR-02: Retrieve all patients for a specific trial

print_header(2, "Retrieve all patients for a specific trial",
             "Example: All patients enrolled in NCT-20240001")

TRIAL_ID = "NCT-20240001"

pipeline_ar02 = [
    {"$match": {"enrolled_trials": TRIAL_ID}},
    {"$project": {
        "_id": 0,
        "patient_id": 1,
        "name": 1,
        "gender": 1,
        "ethnicity": 1,
        "site_id": 1,
        "diagnosis.icd10_code": 1,
        "smoking_status": 1,
    }},
    {"$sort": {"patient_id": 1}},
]

print(f"\nPipeline (trial_id = '{TRIAL_ID}'):")
pprint(pipeline_ar02, width=90)
run_query("patients", pipeline_ar02)


# AR-03: Search patients by demographic or clinical criteria

print_header(3, "Search patients by demographic or clinical criteria",
             "Example: Female patients at SITE-01 who have never smoked")

pipeline_ar03 = [
    {"$match": {
        "gender": "Female",
        "site_id": "SITE-01",
        "smoking_status": "Never",
    }},
    {"$project": {
        "_id": 0,
        "patient_id": 1,
        "name": 1,
        "gender": 1,
        "ethnicity": 1,
        "site_id": 1,
        "smoking_status": 1,
        "diagnosis.icd10_code": 1,
        "diagnosis.description": 1,
    }},
    {"$sort": {"patient_id": 1}},
]

print("\nPipeline:")
pprint(pipeline_ar03, width=90)
run_query("patients", pipeline_ar03)


# AR-04: Retrieve all adverse events for a patient

print_header(4, "Retrieve all adverse events for a patient",
             "Example: All AEs for patient PT-000001 with grade >= 3 (severe+)")

PATIENT_ID = "PT-000001"

pipeline_ar04 = [
    {"$match": {
        "patient_id": PATIENT_ID,
        "ctcae_grade": {"$gte": 3},
    }},
    {"$project": {
        "_id": 0,
        "ae_id": 1,
        "event_name": 1,
        "ctcae_grade": 1,
        "causality": 1,
        "outcome": 1,
        "trial_id": 1,
        "intervention_id": 1,
        "onset_date": 1,
    }},
    {"$sort": {"onset_date": -1}},
]

print(f"\nPipeline (patient_id = '{PATIENT_ID}', min_grade = 3):")
pprint(pipeline_ar04, width=90)
run_query("adverse_events", pipeline_ar04)


# AR-05: AE summary grouped by intervention type

print_header(5, "AE summary grouped by intervention type",
             "Aggregate AE counts and serious proportion per intervention type")

pipeline_ar05 = [
    # Lookup intervention to get the type
    {"$lookup": {
        "from": "interventions",
        "localField": "intervention_id",
        "foreignField": "intervention_id",
        "as": "intervention",
    }},
    {"$unwind": "$intervention"},

    # Group by intervention type
    {"$group": {
        "_id": "$intervention.type",
        "total_ae_count": {"$sum": 1},
        "serious_count": {"$sum": {"$cond": ["$serious", 1, 0]}},
    }},

    # Calculate serious proportion
    {"$project": {
        "_id": 0,
        "intervention_type": "$_id",
        "total_ae_count": 1,
        "serious_count": 1,
        "serious_proportion": {
            "$round": [
                {"$divide": ["$serious_count", "$total_ae_count"]},
                4,
            ]
        },
    }},

    {"$sort": {"total_ae_count": -1}},
]

print("\nPipeline:")
pprint(pipeline_ar05, width=90)
run_query("adverse_events", pipeline_ar05)


# AR-06: Enrolment progress across trials

print_header(6, "Enrolment progress across trials",
             "Completion percentage for all trials, sorted by progress")

pipeline_ar06 = [
    {"$project": {
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
                {"$multiply": [
                    {"$divide": ["$enrolled_count", "$enrolment_target"]},
                    100,
                ]},
                2,
            ]
        },
    }},
    {"$sort": {"completion_pct": -1}},
]

print("\nPipeline:")
pprint(pipeline_ar06, width=90)
run_query("trials", pipeline_ar06)


# AR-07: AE causality-severity matrix for a trial

print_header(7, "AE causality-severity matrix for a trial",
             f"Example: Cross-tabulation for trial NCT-20240001")

TRIAL_ID_07 = "NCT-20240001"

pipeline_ar07 = [
    {"$match": {"trial_id": TRIAL_ID_07}},

    # Group by causality + grade
    {"$group": {
        "_id": {
            "causality": "$causality",
            "ctcae_grade": "$ctcae_grade",
        },
        "count": {"$sum": 1},
    }},

    {"$project": {
        "_id": 0,
        "causality": "$_id.causality",
        "ctcae_grade": "$_id.ctcae_grade",
        "count": 1,
    }},

    {"$sort": {"causality": 1, "ctcae_grade": 1}},
]

print(f"\nPipeline (trial_id = '{TRIAL_ID_07}'):")
pprint(pipeline_ar07, width=90)
run_query("adverse_events", pipeline_ar07)


# AR-08: Patient comorbidity and AE burden

print_header(8, "Patient comorbidity and AE burden",
             "Example: Patients with 3+ comorbidities and their AE counts")

MIN_COMORBIDITIES = 3

pipeline_ar08 = [
    # Calculate comorbidity count
    {"$addFields": {
        "comorbidity_count": {"$size": "$comorbidities"},
    }},

    # Filter by threshold
    {"$match": {"comorbidity_count": {"$gte": MIN_COMORBIDITIES}}},

    # Lookup adverse events for each patient
    {"$lookup": {
        "from": "adverse_events",
        "localField": "patient_id",
        "foreignField": "patient_id",
        "as": "aes",
    }},

    # Calculate counts
    {"$project": {
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
    }},

    {"$sort": {"comorbidity_count": -1, "total_ae_count": -1}},
]

print(f"\nPipeline (min_comorbidities = {MIN_COMORBIDITIES}):")
pprint(pipeline_ar08, width=90)
run_query("patients", pipeline_ar08)


# AR-09: Interventions by gene or protein target

print_header(9, "Interventions by gene or protein target",
             "Example: All interventions targeting EGFR gene")

pipeline_ar09 = [
    {"$match": {"target_gene": {"$regex": "EGFR", "$options": "i"}}},

    # Join to trial for context
    {"$lookup": {
        "from": "trials",
        "localField": "trial_id",
        "foreignField": "trial_id",
        "as": "trial",
    }},
    {"$unwind": "$trial"},

    {"$project": {
        "_id": 0,
        "intervention_id": 1,
        "name": 1,
        "type": 1,
        "mechanism": 1,
        "target_gene": 1,
        "target_protein": 1,
        "regulatory_status": 1,
        "arm_label": 1,
        "trial_id": 1,
        "trial_title": "$trial.short_title",
        "trial_phase": "$trial.phase",
        "trial_status": "$trial.status",
    }},

    {"$sort": {"intervention_id": 1}},
]

print("\nPipeline (target_gene = 'EGFR'):")
pprint(pipeline_ar09, width=90)
run_query("interventions", pipeline_ar09)


# AR-10: Monthly AE trend over time

print_header(10, "Monthly AE trend over time",
             "Example: Monthly AE count for trial NCT-20240001")

TRIAL_ID_10 = "NCT-20240001"

pipeline_ar10 = [
    {"$match": {"trial_id": TRIAL_ID_10}},

    # Group by year-month from onset_date
    {"$group": {
        "_id": {
            "year": {"$year": "$onset_date"},
            "month": {"$month": "$onset_date"},
        },
        "ae_count": {"$sum": 1},
    }},

    {"$project": {
        "_id": 0,
        "year": "$_id.year",
        "month": "$_id.month",
        "ae_count": 1,
    }},

    {"$sort": {"year": 1, "month": 1}},
]

print(f"\nPipeline (trial_id = '{TRIAL_ID_10}'):")
pprint(pipeline_ar10, width=90)
run_query("adverse_events", pipeline_ar10)


print("\n" + "=" * 75)
print("  All 10 queries executed successfully.")
print("=" * 75)

client.close()

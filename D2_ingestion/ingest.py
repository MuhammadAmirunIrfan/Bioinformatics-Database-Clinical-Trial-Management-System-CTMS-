import csv
import json
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import CollectionInvalid

#  Configuration

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

MONGO_URI = os.environ["MONGO_URI"]
DB_NAME = os.environ.get("DB_NAME", "ctms_db")

# Paths — adjust if your folder structure differs
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
SCHEMA_DIR = os.path.join(BASE_DIR, "schemas")

CSV_FILES = {
    "patients": os.path.join(DATA_DIR, "ctms_patients.csv"),
    "trials": os.path.join(DATA_DIR, "ctms_trials.csv"),
    "interventions": os.path.join(DATA_DIR, "ctms_interventions.csv"),
    "adverse_events": os.path.join(DATA_DIR, "ctms_adverse_events.csv"),
}

SCHEMA_FILES = {
    "patients": os.path.join(SCHEMA_DIR, "patients.json"),
    "trials": os.path.join(SCHEMA_DIR, "trials.json"),
    "interventions": os.path.join(SCHEMA_DIR, "interventions.json"),
    "adverse_events": os.path.join(SCHEMA_DIR, "adverse_events.json"),
}


#  Helper Functions 

def parse_date(date_str):
    """Convert an ISO 8601 date string to a datetime object. Returns None if empty."""
    if not date_str or date_str.strip() == "":
        return None
    return datetime.strptime(date_str.strip(), "%Y-%m-%d")


def parse_float(val):
    """Convert string to float. Returns None if empty."""
    if not val or val.strip() == "":
        return None
    return float(val.strip())


def parse_int(val):
    """Convert string to int. Returns None if empty."""
    if not val or val.strip() == "":
        return None
    return int(val.strip())


def parse_bool(val):
    """Convert TRUE/FALSE string to Python bool."""
    return val.strip().upper() == "TRUE"


def split_pipe(val):
    """Split a pipe-delimited string into a list. Returns empty list if blank."""
    if not val or val.strip() == "":
        return []
    return [item.strip() for item in val.split("|")]


def read_csv(filepath):
    """Read a CSV file and return a list of dictionaries."""
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_schema(filepath):
    """Load a JSON schema file and return the $jsonSchema object."""
    with open(filepath, "r") as f:
        data = json.load(f)
    return data["$jsonSchema"]


#  Transformation Functions 

def transform_patient(row):
    """Transform a flat patient CSV row into a MongoDB document."""
    doc = {
        "patient_id": row["patient_id"].strip(),
        "name": row["name"].strip(),
        "date_of_birth": parse_date(row["date_of_birth"]),
        "gender": row["gender"].strip(),
        "ethnicity": row["ethnicity"].strip(),
        "blood_type": row["blood_type"].strip(),
        "bmi": parse_float(row["bmi"]),
        "smoking_status": row["smoking_status"].strip(),

        # Nested object — assembled from flat CSV columns
        "diagnosis": {
            "icd10_code": row["diagnosis_icd10"].strip(),
            "description": row["diagnosis_desc"].strip(),
            "diagnosed_on": parse_date(row["diagnosed_on"]),
        },

        # Pipe-delimited → array (can be empty)
        "comorbidities": split_pipe(row["comorbidities"]),

        "site_id": row["site_id"].strip(),

        # Pipe-delimited → array of trial_id references
        "enrolled_trials": split_pipe(row["enrolled_trials"]),

        "enrolment_date": parse_date(row["enrolment_date"]),

        # Nested object — assembled from flat CSV columns
        "contact_info": {
            "email": row["contact_email"].strip(),
            "phone": row["contact_phone"].strip(),
            "emergency_contact": row["emergency_contact"].strip(),
        },

        "created_at": parse_date(row["created_at"]),
    }
    return doc


def transform_trial(row, intervention_map):
    """
    Transform a flat trial CSV row into a MongoDB document.
    intervention_map: dict of trial_id -> [intervention_id, ...] built from interventions CSV.
    """
    # Parse arms from pipe-delimited "Arm A:Experimental|Arm B:Placebo Comparator"
    arms = []
    for arm_str in split_pipe(row["arms"]):
        parts = arm_str.split(":")
        arm_label = parts[0].strip()
        arm_type = parts[1].strip() if len(parts) > 1 else ""
        arms.append({
            "arm_label": arm_label,
            "arm_type": arm_type,
        })

    trial_id = row["trial_id"].strip()

    doc = {
        "trial_id": trial_id,
        "title": row["title"].strip(),
        "short_title": row["short_title"].strip(),
        "phase": row["phase"].strip(),
        "status": row["status"].strip(),
        "sponsor": row["sponsor"].strip(),

        # Pipe-delimited → array
        "conditions": split_pipe(row["conditions"]),

        # Derived from interventions CSV — not present in trials CSV
        "interventions": intervention_map.get(trial_id, []),

        "start_date": parse_date(row["start_date"]),
        "estimated_end_date": parse_date(row["estimated_end_date"]),
        "enrolment_target": parse_int(row["enrolment_target"]),
        "enrolled_count": parse_int(row["enrolled_count"]),
        "arms": arms,
        "primary_endpoint": row["primary_endpoint"].strip(),

        # Pipe-delimited → array
        "secondary_endpoints": split_pipe(row["secondary_endpoints"]),

        # Pipe-delimited → array
        "sites": split_pipe(row["sites"]),

        # Nested object — assembled from flat CSV columns
        "ethical_approval": {
            "approval_id": row["ethical_approval_id"].strip(),
            "committee": row["ethical_committee"].strip(),
            "approved_on": parse_date(row["ethical_approved_on"]),
        },

        "created_at": parse_date(row["created_at"]),
    }
    return doc


def transform_intervention(row):
    """Transform a flat intervention CSV row into a MongoDB document."""
    doc = {
        "intervention_id": row["intervention_id"].strip(),
        "trial_id": row["trial_id"].strip(),
        "arm_label": row["arm_label"].strip(),
        "name": row["name"].strip(),
        "type": row["type"].strip(),
        "mechanism": row["mechanism"].strip(),

        # Nested object — assembled from 4 flat CSV columns
        "dosage": {
            "amount": parse_float(row["dosage_amount"]),
            "unit": row["dosage_unit"].strip(),
            "frequency": row["dosage_frequency"].strip(),
            "route": row["dosage_route"].strip(),
        },

        "duration_weeks": parse_int(row["duration_weeks"]),

        # Null if empty (placebos have no molecular target)
        "target_gene": row["target_gene"].strip() if row["target_gene"].strip() else None,
        "target_protein": row["target_protein"].strip() if row["target_protein"].strip() else None,

        "regulatory_status": row["regulatory_status"].strip(),
        "created_at": parse_date(row["created_at"]),
    }
    return doc


def transform_adverse_event(row):
    """Transform a flat adverse event CSV row into a MongoDB document."""
    # Build lab_values object only if lab data is present
    lab_values = None
    if row["lab_test_name"].strip():
        lab_values = {
            "test_name": row["lab_test_name"].strip(),
            "value": parse_float(row["lab_value"]),
            "unit": row["lab_unit"].strip(),
            "reference_range": row["lab_reference_range"].strip(),
        }

    doc = {
        "ae_id": row["ae_id"].strip(),
        "patient_id": row["patient_id"].strip(),
        "trial_id": row["trial_id"].strip(),
        "intervention_id": row["intervention_id"].strip(),
        "event_name": row["event_name"].strip(),
        "system_organ_class": row["system_organ_class"].strip(),
        "ctcae_grade": parse_int(row["ctcae_grade"]),
        "onset_date": parse_date(row["onset_date"]),

        # Null if ongoing or fatal
        "resolution_date": parse_date(row["resolution_date"]),

        "outcome": row["outcome"].strip(),
        "serious": parse_bool(row["serious"]),
        "action_taken": row["action_taken"].strip(),
        "causality": row["causality"].strip(),
        "lab_values": lab_values,
        "reported_by": row["reported_by"].strip(),
        "created_at": parse_date(row["created_at"]),
    }
    return doc


#  Referential Consistency Checks 

def check_referential_consistency(patients, trials, interventions, adverse_events):
    """
    Verify all foreign ID references resolve to real documents.
    Prints warnings and returns True if all checks pass.
    """
    trial_ids = {t["trial_id"] for t in trials}
    patient_ids = {p["patient_id"] for p in patients}
    intervention_ids = {i["intervention_id"] for i in interventions}
    errors = []

    # Patients: enrolled_trials must reference existing trials
    for p in patients:
        for tid in p["enrolled_trials"]:
            if tid not in trial_ids:
                errors.append(f"Patient {p['patient_id']} references non-existent trial {tid}")

    # Interventions: trial_id must reference existing trial
    for i in interventions:
        if i["trial_id"] not in trial_ids:
            errors.append(f"Intervention {i['intervention_id']} references non-existent trial {i['trial_id']}")

    # Adverse events: all 3 mandatory references must resolve
    for ae in adverse_events:
        if ae["patient_id"] not in patient_ids:
            errors.append(f"AE {ae['ae_id']} references non-existent patient {ae['patient_id']}")
        if ae["trial_id"] not in trial_ids:
            errors.append(f"AE {ae['ae_id']} references non-existent trial {ae['trial_id']}")
        if ae["intervention_id"] not in intervention_ids:
            errors.append(f"AE {ae['ae_id']} references non-existent intervention {ae['intervention_id']}")

    if errors:
        print(f"\n[ERROR] {len(errors)} referential consistency issues found:")
        for e in errors[:10]:
            print(f"  - {e}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")
        return False
    else:
        print("\n[OK] All referential consistency checks passed.")
        return True


#  Collection Creation with Validators 

def create_collection_with_validator(db, name, schema):
    """
    Create a collection with a $jsonSchema validator.
    Drops existing collection first to ensure clean state.
    """
    # Drop if exists (clean re-run)
    if name in db.list_collection_names():
        db.drop_collection(name)
        print(f"  Dropped existing collection: {name}")

    db.create_collection(name, validator={"$jsonSchema": schema})
    print(f"  Created collection with validator: {name}")


#  Main Ingestion Logic 

def main():
    print("=" * 65)
    print("  CTMS Data Ingestion Script")
    print("=" * 65)

    # --- Step 1: Connect to MongoDB ---
    print("\n[1/7] Connecting to MongoDB...")
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    print(f"  Connected to database: {DB_NAME}")

    # --- Step 2: Read all CSV files ---
    print("\n[2/7] Reading CSV files...")
    raw_patients = read_csv(CSV_FILES["patients"])
    raw_trials = read_csv(CSV_FILES["trials"])
    raw_interventions = read_csv(CSV_FILES["interventions"])
    raw_adverse_events = read_csv(CSV_FILES["adverse_events"])
    print(f"  Patients CSV:        {len(raw_patients)} rows")
    print(f"  Trials CSV:          {len(raw_trials)} rows")
    print(f"  Interventions CSV:   {len(raw_interventions)} rows")
    print(f"  Adverse Events CSV:  {len(raw_adverse_events)} rows")

    # --- Step 3: Build intervention-to-trial mapping ---
    # The trials CSV has no 'interventions' column, so we derive it
    # by grouping intervention_ids by their trial_id.
    print("\n[3/7] Building intervention-to-trial mapping...")
    intervention_map = {}  # trial_id -> [intervention_id, ...]
    for row in raw_interventions:
        tid = row["trial_id"].strip()
        iid = row["intervention_id"].strip()
        intervention_map.setdefault(tid, []).append(iid)
    for tid, iids in intervention_map.items():
        print(f"  {tid}: {iids}")

    # --- Step 4: Transform all documents ---
    print("\n[4/7] Transforming CSV rows into MongoDB documents...")
    patients = [transform_patient(r) for r in raw_patients]
    trials = [transform_trial(r, intervention_map) for r in raw_trials]
    interventions = [transform_intervention(r) for r in raw_interventions]
    adverse_events = [transform_adverse_event(r) for r in raw_adverse_events]
    print(f"  Transformed: {len(patients)} patients, {len(trials)} trials, "
          f"{len(interventions)} interventions, {len(adverse_events)} adverse events")

    # --- Step 5: Referential consistency check ---
    print("\n[5/7] Checking referential consistency...")
    if not check_referential_consistency(patients, trials, interventions, adverse_events):
        print("\n[ABORT] Fix referential issues before ingesting.")
        sys.exit(1)

    # --- Step 6: Create collections with validators and insert ---
    print("\n[6/7] Creating collections and inserting documents...")

    schemas = {}
    for name in ["patients", "trials", "interventions", "adverse_events"]:
        schemas[name] = load_schema(SCHEMA_FILES[name])

    # Create collections
    for name in ["trials", "interventions", "patients", "adverse_events"]:
        create_collection_with_validator(db, name, schemas[name])

    # Insert in dependency order
    db.trials.insert_many(trials)
    print(f"  Inserted {len(trials)} trials")

    db.interventions.insert_many(interventions)
    print(f"  Inserted {len(interventions)} interventions")

    db.patients.insert_many(patients)
    print(f"  Inserted {len(patients)} patients")

    db.adverse_events.insert_many(adverse_events)
    print(f"  Inserted {len(adverse_events)} adverse events")

    # --- Step 7: Create indexes for query performance ---
    print("\n[7/7] Creating indexes...")
    # Unique indexes on primary identifiers
    db.patients.create_index("patient_id", unique=True)
    db.trials.create_index("trial_id", unique=True)
    db.interventions.create_index("intervention_id", unique=True)
    db.adverse_events.create_index("ae_id", unique=True)

    # Indexes to support analytical requirements
    db.patients.create_index("site_id")                            # AR-03: search by site
    db.patients.create_index("gender")                             # AR-03: search by gender
    db.patients.create_index("enrolled_trials")                    # AR-02: patients for a trial
    db.trials.create_index("status")                               # AR-01: filter by status
    db.trials.create_index("phase")                                # AR-01: filter by phase
    db.interventions.create_index("trial_id")                      # AR-05, AR-07: join to trial
    db.interventions.create_index("type")                          # AR-05: group by type
    db.interventions.create_index("target_gene")                   # AR-09: search by gene
    db.interventions.create_index("target_protein")                # AR-09: search by protein
    db.adverse_events.create_index("patient_id")                   # AR-04: AEs for a patient
    db.adverse_events.create_index("trial_id")                     # AR-07, AR-10: AEs for a trial
    db.adverse_events.create_index("intervention_id")              # AR-05: join to intervention
    db.adverse_events.create_index("onset_date")                   # AR-10: monthly trend
    db.adverse_events.create_index([("causality", 1), ("ctcae_grade", 1)])  # AR-07: matrix
    print("  Indexes created.")

    #  Summary & Sample Documents 

    print("\n" + "=" * 65)
    print("  INGESTION COMPLETE — Document Counts")
    print("=" * 65)
    for coll_name in ["patients", "trials", "interventions", "adverse_events"]:
        count = db[coll_name].count_documents({})
        print(f"  {coll_name:<20} {count:>5} documents")

    print("\n" + "=" * 65)
    print("  SAMPLE DOCUMENTS (1 per collection)")
    print("=" * 65)
    from pprint import pprint
    for coll_name in ["patients", "trials", "interventions", "adverse_events"]:
        print(f"\n--- {coll_name} ---")
        doc = db[coll_name].find_one({}, {"_id": 0})
        pprint(doc, width=100)

    print("\n[DONE] Database is ready.")
    client.close()


if __name__ == "__main__":
    main()

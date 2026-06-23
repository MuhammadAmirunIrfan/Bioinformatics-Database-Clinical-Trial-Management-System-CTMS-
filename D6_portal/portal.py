"""
SECB3213 Mini Project — D6: Data Portal (Streamlit)
Clinical Trial Management System (CTMS)

Read-only interactive portal consuming the FastAPI backend.
All data flows through the API — no direct MongoDB queries.

5 Required Features:
  1. Trial Browser with filters (status, phase, sponsor)
  2. Patient Search (demographic + clinical filters)
  3. AE/Drug Response Monitor with colour-coded severity
  4. Analytics Charts that update on filter change
  5. Enrolment Explorer dashboard

Prerequisites:
  - FastAPI server running: uvicorn app:app --port 8000
  - pip install streamlit requests plotly pandas

Usage:
  streamlit run portal.py
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

#  Configuration 

API_BASE = "http://localhost:8000/api"

st.set_page_config(
    page_title="CTMS Portal",
    page_icon="🏥",
    layout="wide",
)


#  API Helper 

def api_get(endpoint: str, params: dict = None) -> dict:
    """Call the FastAPI backend and return JSON response."""
    try:
        resp = requests.get(f"{API_BASE}/{endpoint}", params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to the API server. Make sure it is running: `uvicorn app:app --port 8000`")
        return {"total": 0, "data": []}
    except requests.exceptions.HTTPError as e:
        st.error(f"API Error: {e.response.status_code} — {e.response.text}")
        return {"total": 0, "data": []}


#  Colour-coding for CTCAE grades 

GRADE_COLOURS = {
    1: "#2ecc71",   # Green  — Mild
    2: "#f39c12",   # Orange — Moderate
    3: "#e67e22",   # Dark Orange — Severe
    4: "#e74c3c",   # Red — Life-threatening
    5: "#8e44ad",   # Purple — Fatal
}

GRADE_LABELS = {
    1: "Mild",
    2: "Moderate",
    3: "Severe",
    4: "Life-threatening",
    5: "Fatal",
}


def colour_grade(grade):
    """Return HTML-styled badge for a CTCAE grade."""
    colour = GRADE_COLOURS.get(grade, "#95a5a6")
    label = GRADE_LABELS.get(grade, str(grade))
    return f'<span style="background-color:{colour};color:white;padding:2px 8px;border-radius:4px;font-weight:bold;">Grade {grade} — {label}</span>'


#  Sidebar Navigation 

st.sidebar.title("🏥 CTMS Portal")
st.sidebar.markdown("Meridian Clinical Research Institute")

page = st.sidebar.radio("Navigate", [
    "1 · Trial Browser",
    "2 · Patient Search",
    "3 · AE Monitor",
    "4 · Analytics",
    "5 · Enrolment Explorer",
])


# FEATURE 1: Trial Browser with Filters

if page == "1 · Trial Browser":
    st.header("📋 Trial Browser")
    st.caption("AR-01 · `GET /api/trials` — Filter clinical trials by status, phase, and sponsor")

    col1, col2, col3 = st.columns(3)
    with col1:
        status_filter = st.selectbox("Status", [
            "", "Recruiting", "Active (not recruiting)", "Completed",
            "Terminated", "Suspended", "Withdrawn",
        ], index=0)
    with col2:
        phase_filter = st.selectbox("Phase", [
            "", "Phase I", "Phase II", "Phase III", "Phase IV", "Not Applicable",
        ], index=0)
    with col3:
        sponsor_filter = st.text_input("Sponsor (search)")

    params = {}
    if status_filter:
        params["status"] = status_filter
    if phase_filter:
        params["phase"] = phase_filter
    if sponsor_filter:
        params["sponsor"] = sponsor_filter
    params["limit"] = 100

    result = api_get("trials", params)
    data = result.get("data", [])

    st.metric("Matching Trials", result.get("total", 0))

    if data:
        df = pd.json_normalize(data)
        display_cols = ["trial_id", "short_title", "phase", "status", "sponsor",
                        "enrolled_count", "enrolment_target"]
        available = [c for c in display_cols if c in df.columns]
        st.dataframe(df[available], use_container_width=True, hide_index=True)
    else:
        st.info("No trials match the current filters.")


# FEATURE 2: Patient Search

elif page == "2 · Patient Search":
    st.header("🔍 Patient Search")
    st.caption("AR-02 & AR-03 · `GET /api/patients` / `GET /api/trials/{trial_id}/patients`")

    search_mode = st.radio("Search mode", ["General Search (AR-03)", "By Trial (AR-02)"], horizontal=True)

    if search_mode == "General Search (AR-03)":
        col1, col2, col3 = st.columns(3)
        with col1:
            gender = st.selectbox("Gender", ["", "Male", "Female", "Non-binary", "Prefer not to say"])
        with col2:
            ethnicity = st.selectbox("Ethnicity", [
                "", "Malay", "Chinese", "Indian", "Caucasian", "African", "Hispanic", "Other",
            ])
        with col3:
            site = st.selectbox("Site", ["", "SITE-01", "SITE-02", "SITE-03", "SITE-04", "SITE-05"])

        col4, col5 = st.columns(2)
        with col4:
            smoking = st.selectbox("Smoking Status", ["", "Never", "Former", "Current"])
        with col5:
            diag_code = st.text_input("Diagnosis ICD-10 prefix", placeholder="e.g. C34")

        params = {"limit": 100}
        if gender:
            params["gender"] = gender
        if ethnicity:
            params["ethnicity"] = ethnicity
        if site:
            params["site_id"] = site
        if smoking:
            params["smoking_status"] = smoking
        if diag_code:
            params["diagnosis_code"] = diag_code

        result = api_get("patients", params)

    else:
        trial_id_input = st.text_input("Trial ID", value="NCT-20240001")
        col1, col2 = st.columns(2)
        with col1:
            gender = st.selectbox("Gender", ["", "Male", "Female", "Non-binary", "Prefer not to say"])
        with col2:
            ethnicity = st.selectbox("Ethnicity", [
                "", "Malay", "Chinese", "Indian", "Caucasian", "African", "Hispanic", "Other",
            ])

        params = {"limit": 100}
        if gender:
            params["gender"] = gender
        if ethnicity:
            params["ethnicity"] = ethnicity

        result = api_get(f"trials/{trial_id_input}/patients", params)

    data = result.get("data", [])
    st.metric("Matching Patients", result.get("total", 0))

    if data:
        df = pd.json_normalize(data)
        display_cols = ["patient_id", "name", "gender", "ethnicity", "blood_type",
                        "site_id", "smoking_status", "diagnosis.icd10_code",
                        "diagnosis.description", "bmi"]
        available = [c for c in display_cols if c in df.columns]
        st.dataframe(df[available], use_container_width=True, hide_index=True)
    else:
        st.info("No patients match the current filters.")


# FEATURE 3: AE/Drug Response Monitor (colour-coded severity)

elif page == "3 · AE Monitor":
    st.header("⚠️ Adverse Event Monitor")
    st.caption("AR-04 & AR-07 · Colour-coded by CTCAE grade")

    tab1, tab2 = st.tabs(["Patient AE History (AR-04)", "Causality-Severity Matrix (AR-07)"])

    # --- Tab 1: Patient AE History ---
    with tab1:
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            patient_id = st.text_input("Patient ID", value="PT-000001", key="ae_pid")
        with col2:
            min_grade = st.selectbox("Min CTCAE Grade", [None, 1, 2, 3, 4, 5], index=0,
                                     format_func=lambda x: "All" if x is None else f"≥ {x}")
        with col3:
            causality_filter = st.selectbox("Causality", [
                "", "Unrelated", "Unlikely", "Possible", "Probable", "Definite",
            ])

        params = {"limit": 100}
        if min_grade:
            params["min_grade"] = min_grade
        if causality_filter:
            params["causality"] = causality_filter

        result = api_get(f"patients/{patient_id}/adverse-events", params)
        data = result.get("data", [])

        st.metric("Adverse Events Found", result.get("total", 0))

        if data:
            df = pd.json_normalize(data)

            # Colour-coded grade column
            if "ctcae_grade" in df.columns:
                df["severity"] = df["ctcae_grade"].apply(colour_grade)

            display_cols = ["ae_id", "event_name", "severity", "causality",
                            "outcome", "action_taken", "trial_id", "intervention_id", "onset_date"]
            available = [c for c in display_cols if c in df.columns]

            st.markdown(df[available].to_html(escape=False, index=False), unsafe_allow_html=True)
        else:
            st.info("No adverse events found for the current filters.")

    # --- Tab 2: Causality-Severity Matrix ---
    with tab2:
        trial_id_matrix = st.text_input("Trial ID", value="NCT-20240001", key="matrix_tid")

        result = api_get(f"trials/{trial_id_matrix}/adverse-events/causality-severity-matrix")
        data = result.get("data", [])

        if data:
            df = pd.DataFrame(data)
            # Pivot into a matrix: rows = causality, columns = grade
            pivot = df.pivot_table(
                index="causality", columns="ctcae_grade",
                values="count", aggfunc="sum", fill_value=0,
            )
            pivot.columns = [f"Grade {g}" for g in pivot.columns]

            st.dataframe(pivot, use_container_width=True)

            # Heatmap visualisation
            fig = px.imshow(
                pivot.values,
                labels=dict(x="CTCAE Grade", y="Causality", color="Count"),
                x=pivot.columns.tolist(),
                y=pivot.index.tolist(),
                color_continuous_scale="YlOrRd",
                text_auto=True,
                aspect="auto",
            )
            fig.update_layout(title=f"AE Causality × Severity — {trial_id_matrix}")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No adverse events found for this trial.")


# FEATURE 4: Analytics Charts (update on filter change)

elif page == "4 · Analytics":
    st.header("📊 Analytics Dashboard")
    st.caption("AR-05, AR-08, AR-09, AR-10 — Charts update dynamically on filter change")

    tab1, tab2, tab3, tab4 = st.tabs([
        "AE by Intervention Type (AR-05)",
        "Monthly AE Trend (AR-10)",
        "Comorbidity & AE Burden (AR-08)",
        "Gene/Protein Search (AR-09)",
    ])

    # --- Tab 1: AE by intervention type ---
    with tab1:
        result = api_get("analytics/adverse-events/by-intervention-type")
        data = result.get("data", [])

        if data:
            df = pd.DataFrame(data)
            col1, col2 = st.columns(2)

            with col1:
                fig = px.bar(
                    df, x="intervention_type", y="total_ae_count",
                    color="intervention_type",
                    title="Total AE Count by Intervention Type",
                    labels={"total_ae_count": "AE Count", "intervention_type": "Type"},
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                fig2 = px.bar(
                    df, x="intervention_type", y="serious_proportion",
                    color="intervention_type",
                    title="Serious AE Proportion by Intervention Type",
                    labels={"serious_proportion": "Serious Ratio", "intervention_type": "Type"},
                )
                fig2.update_layout(yaxis_tickformat=".0%")
                st.plotly_chart(fig2, use_container_width=True)

            st.dataframe(df, use_container_width=True, hide_index=True)

    # --- Tab 2: Monthly AE trend ---
    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            trend_trial = st.text_input("Trial ID (optional)", key="trend_trial")
        with col2:
            trend_type = st.selectbox("Intervention Type (optional)", [
                "", "Drug", "Biologic", "Placebo", "Procedure", "Device",
            ], key="trend_type")

        params = {}
        if trend_trial:
            params["trial_id"] = trend_trial
        if trend_type:
            params["intervention_type"] = trend_type

        result = api_get("analytics/adverse-events/monthly-trend", params)
        data = result.get("data", [])

        if data:
            df = pd.DataFrame(data)
            df["date"] = pd.to_datetime(df["year"].astype(str) + "-" + df["month"].astype(str) + "-01")
            df = df.sort_values("date")

            fig = px.line(
                df, x="date", y="ae_count",
                markers=True,
                title="Monthly Adverse Event Trend",
                labels={"ae_count": "AE Count", "date": "Month"},
            )
            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(df[["year", "month", "ae_count"]], use_container_width=True, hide_index=True)
        else:
            st.info("No data for the selected filters.")

    # --- Tab 3: Comorbidity & AE Burden ---
    with tab3:
        min_comorbidities = st.slider("Minimum Comorbidities", 0, 5, 2, key="comorbidity_slider")

        result = api_get("analytics/comorbidity-ae-burden", {"min_comorbidities": min_comorbidities, "limit": 100})
        data = result.get("data", [])

        if data:
            df = pd.DataFrame(data)

            fig = px.scatter(
                df, x="comorbidity_count", y="total_ae_count",
                size="serious_ae_count", hover_name="patient_id",
                color="serious_ae_count",
                color_continuous_scale="YlOrRd",
                title=f"Comorbidity Count vs AE Burden (≥{min_comorbidities} comorbidities)",
                labels={
                    "comorbidity_count": "Comorbidities",
                    "total_ae_count": "Total AEs",
                    "serious_ae_count": "Serious AEs",
                },
            )
            st.plotly_chart(fig, use_container_width=True)

            display_cols = ["patient_id", "name", "comorbidity_count", "total_ae_count", "serious_ae_count"]
            st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
        else:
            st.info("No patients match the comorbidity threshold.")

    # --- Tab 4: Gene/Protein search ---
    with tab4:
        col1, col2 = st.columns(2)
        with col1:
            gene_query = st.text_input("Gene Symbol", placeholder="e.g. EGFR, PD-L1, VEGFR")
        with col2:
            protein_query = st.text_input("Protein Name", placeholder="e.g. PD-1")

        params = {"limit": 100}
        if gene_query:
            params["target_gene"] = gene_query
        if protein_query:
            params["target_protein"] = protein_query

        if gene_query or protein_query:
            result = api_get("interventions", params)
            data = result.get("data", [])

            st.metric("Matching Interventions", result.get("total", 0))

            if data:
                df = pd.json_normalize(data)
                display_cols = ["intervention_id", "name", "type", "mechanism",
                                "target_gene", "target_protein", "regulatory_status",
                                "trial_id", "trial_title", "trial_phase"]
                available = [c for c in display_cols if c in df.columns]
                st.dataframe(df[available], use_container_width=True, hide_index=True)
            else:
                st.info("No interventions found for the specified target.")
        else:
            st.info("Enter a gene symbol or protein name to search.")


# FEATURE 5: Enrolment Explorer Dashboard

elif page == "5 · Enrolment Explorer":
    st.header("📈 Enrolment Explorer")
    st.caption("AR-06 · `GET /api/analytics/enrolment-progress` — Enrolment completion dashboard")

    col1, col2, col3 = st.columns(3)
    with col1:
        enrol_sponsor = st.text_input("Sponsor (search)", key="enrol_sponsor")
    with col2:
        enrol_phase = st.selectbox("Phase", [
            "", "Phase I", "Phase II", "Phase III", "Phase IV", "Not Applicable",
        ], key="enrol_phase")
    with col3:
        enrol_status = st.selectbox("Status", [
            "", "Recruiting", "Active (not recruiting)", "Completed",
            "Terminated", "Suspended",
        ], key="enrol_status")

    params = {}
    if enrol_sponsor:
        params["sponsor"] = enrol_sponsor
    if enrol_phase:
        params["phase"] = enrol_phase
    if enrol_status:
        params["status"] = enrol_status

    result = api_get("analytics/enrolment-progress", params)
    data = result.get("data", [])

    if data:
        df = pd.DataFrame(data)

        # Summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Trials", len(df))
        with col2:
            avg_pct = df["completion_pct"].mean()
            st.metric("Avg Completion", f"{avg_pct:.1f}%")
        with col3:
            fully_enrolled = len(df[df["completion_pct"] >= 100])
            st.metric("Fully Enrolled", fully_enrolled)

        # Bar chart of completion by trial
        fig = px.bar(
            df.sort_values("completion_pct", ascending=True),
            x="completion_pct", y="short_title",
            orientation="h",
            color="completion_pct",
            color_continuous_scale="RdYlGn",
            range_color=[0, 100],
            title="Enrolment Completion by Trial",
            labels={"completion_pct": "Completion %", "short_title": "Trial"},
        )
        fig.add_vline(x=100, line_dash="dash", line_color="green", annotation_text="Target")
        fig.update_layout(height=max(400, len(df) * 50))
        st.plotly_chart(fig, use_container_width=True)

        # Detailed table
        display_cols = ["trial_id", "short_title", "phase", "status", "sponsor",
                        "enrolled_count", "enrolment_target", "completion_pct"]
        available = [c for c in display_cols if c in df.columns]
        st.dataframe(df[available], use_container_width=True, hide_index=True)
    else:
        st.info("No trials match the current filters.")


#  Footer 
st.sidebar.markdown("---")
st.sidebar.caption("CTMS Portal v1.0 · SECB3213 Mini Project")
st.sidebar.caption("Data served via FastAPI · `localhost:8000/docs`")

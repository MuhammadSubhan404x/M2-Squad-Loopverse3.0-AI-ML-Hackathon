"""Streamlit UI for the Lahore Smog Intelligence Challenge system."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import streamlit as st

from solution import HAZARDOUS_PM25, ask, forecast

ROOT = Path(__file__).resolve().parent


@st.cache_data
def covered_areas() -> list[str]:
    with (ROOT / "weather" / "sensor_metadata.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        return [row["area"] for row in csv.DictReader(handle)]


@st.cache_data
def supported_dates() -> list[date]:
    with (ROOT / "holdout" / "holdout_inputs.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        return sorted(
            {date.fromisoformat(row["target_date"]) for row in csv.DictReader(handle)}
        )


st.set_page_config(
    page_title="Lahore Smog Intelligence",
    page_icon="🌫️",
    layout="wide",
)

st.title("Lahore Smog Intelligence")
st.caption("Forecast PM2.5 and ask a grounded, citation-aware smog advisory assistant.")

with st.sidebar:
    st.header("System status")
    st.metric("Hazardous threshold", f"{HAZARDOUS_PM25:.0f} µg/m³")
    st.caption("Forecasts are limited to the 15 covered Lahore areas and 10 supported dates.")
    st.divider()
    st.markdown("**Pipeline**")
    st.markdown("`Question → FAISS retrieval → forecast tool → grounded answer`")

forecast_tab, assistant_tab = st.tabs(["Forecast lookup", "Advisory assistant"])

with forecast_tab:
    st.subheader("Forecast lookup")
    areas = covered_areas()
    dates = supported_dates()
    col1, col2 = st.columns(2)
    with col1:
        area = st.selectbox("Covered area", areas)
    with col2:
        target = st.selectbox(
            "Supported target date",
            dates,
            format_func=lambda value: value.isoformat(),
        )
    if st.button("Get forecast", type="primary"):
        with st.spinner("Loading forecast..."):
            result = forecast(area, target.isoformat())
        if result["status"] == "unavailable":
            st.warning("This location/date is outside the supported forecast scope.")
        else:
            pm25 = float(result["pm25"])
            metric_col, alarm_col = st.columns(2)
            metric_col.metric("Predicted PM2.5", f"{pm25:.2f} µg/m³")
            if result["hazardous"]:
                alarm_col.error("HAZARDOUS — limit outdoor exposure")
            else:
                alarm_col.success("Below hazardous threshold")
            st.json(result)

with assistant_tab:
    st.subheader("Grounded advisory assistant")
    question = st.text_area(
        "Ask a smog, health, policy, or forecast question",
        placeholder="What is the forecast for Gulberg on 2026-10-29?",
        height=100,
    )
    if st.button("Ask assistant", type="primary") and question.strip():
        try:
            with st.spinner("Retrieving evidence and checking the forecast tool..."):
                result = ask(question.strip())
        except RuntimeError as error:
            st.error(str(error))
            st.info("Set OPENAI_API_KEY and run build_faiss_index.py before asking questions.")
        else:
            st.markdown("### Answer")
            st.write(result["answer"])
            col1, col2 = st.columns(2)
            col1.write(f"**Question ID:** `{result['question_id']}`")
            col2.write(f"**Forecast called:** `{result['forecast_called']}`")
            st.markdown("### Sources used")
            if result["sources"]:
                for source in result["sources"]:
                    st.code(source)
            else:
                st.caption("No document sources were used.")

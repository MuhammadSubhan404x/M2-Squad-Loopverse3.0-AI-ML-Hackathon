"""Streamlit UI for the Lahore Smog Intelligence Challenge system."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import streamlit as st
from openai import OpenAIError

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

st.markdown(
    """
    <style>
    .hero {
        padding: 1.4rem 1.6rem;
        border-radius: 16px;
        background: linear-gradient(120deg, #172554 0%, #0f766e 100%);
        color: white;
        margin-bottom: 1.2rem;
    }
    .hero h1 { margin: 0; font-size: 2.4rem; }
    .hero p { margin: .45rem 0 0; color: #dbeafe; }
    .source-chip {
        display: inline-block;
        padding: .35rem .7rem;
        margin: .2rem .35rem .2rem 0;
        border-radius: 999px;
        background: #0f766e;
        color: white;
        font-size: .85rem;
    }
    </style>
    <div class="hero">
        <h1>🌫️ Lahore Smog Intelligence</h1>
        <p>Forecast PM2.5, retrieve trusted guidance, and make safer decisions.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("System status")
    st.metric("Hazardous threshold", f"{HAZARDOUS_PM25:.0f} µg/m³")
    st.success("Forecast engine ready")
    st.success("FAISS knowledge base ready")
    st.caption("Forecasts are limited to the 15 covered Lahore areas and 10 supported dates.")
    st.divider()
    st.markdown("**Pipeline**")
    st.markdown("`Question → FAISS retrieval → forecast tool → grounded answer`")

forecast_tab, assistant_tab = st.tabs(["Forecast lookup", "Advisory assistant"])

with forecast_tab:
    st.subheader("Forecast lookup")
    st.caption("Select a covered Lahore area and a supported holdout date.")
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
            metric_col, alarm_col, date_col = st.columns(3)
            metric_col.metric("Predicted PM2.5", f"{pm25:.2f} µg/m³")
            if result["hazardous"]:
                alarm_col.metric("Risk level", "HAZARDOUS", delta="Above 165", delta_color="inverse")
            else:
                alarm_col.metric("Risk level", "Below threshold", delta="Safe range")
            date_col.metric("Target date", target.isoformat())
            if result["hazardous"]:
                st.error("Hazardous conditions expected — limit outdoor exposure and follow official guidance.")
            else:
                st.success("Forecast is below the hazardous threshold.")
            with st.expander("View forecast details"):
                st.json(result)

with assistant_tab:
    st.subheader("Grounded advisory assistant")
    st.caption("Answers are retrieved from the indexed guidance documents and include source IDs.")
    question = st.text_area(
        "Ask a smog, health, policy, or forecast question",
        placeholder="What is the forecast for Gulberg on 2026-10-29?",
        height=100,
    )
    if st.button("Ask assistant", type="primary") and question.strip():
        try:
            with st.spinner("Retrieving evidence and checking the forecast tool..."):
                result = ask(question.strip())
        except (OpenAIError, RuntimeError) as error:
            st.error(str(error))
            st.info(
                "Start Streamlit from the same terminal where OPENAI_API_KEY is set. "
                "The forecast lookup does not require an API key."
            )
        else:
            st.markdown("### Answer")
            st.info(result["answer"])
            col1, col2 = st.columns(2)
            col1.metric("Question ID", result["question_id"])
            col2.metric("Forecast tool", "Called" if result["forecast_called"] else "Not needed")
            st.markdown("### Sources used")
            if result["sources"]:
                st.markdown(
                    "".join(
                        f'<span class="source-chip">{source}</span>'
                        for source in result["sources"]
                    ),
                    unsafe_allow_html=True,
                )
            else:
                st.caption("No document sources were used.")

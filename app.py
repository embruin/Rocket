from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO

import pandas as pd
import streamlit as st

from forecasting import (
    build_daily_forecast,
    flag_unknown_transactions,
    load_bank_csv,
    load_schedule_csv,
    recurring_schedule,
    weekly_summary,
)

st.set_page_config(page_title="Construction Cash Forecast", layout="wide")

st.title("Construction Cash Forecasting MVP")
st.caption("Prototype for a contractor: bank activity, AR/AP schedules, recurring obligations, and 13-week cash visibility.")

with st.sidebar:
    st.header("Forecast Settings")
    beginning_cash = st.number_input("Beginning cash balance", value=50000.00, step=1000.00, format="%.2f")
    start_date = st.date_input("Forecast start date", value=date.today())
    weeks = st.slider("Forecast length in weeks", min_value=4, max_value=26, value=13)
    include_probability = st.checkbox("Probability-weight AR/AP items", value=True)
    low_cash_threshold = st.number_input("Low cash warning threshold", value=10000.00, step=1000.00, format="%.2f")

st.subheader("1. Upload source data")
col1, col2, col3 = st.columns(3)
with col1:
    bank_file = st.file_uploader("Bank transactions CSV", type=["csv"])
with col2:
    ar_file = st.file_uploader("AR schedule / aging CSV", type=["csv"])
with col3:
    ap_file = st.file_uploader("AP schedule / aging CSV", type=["csv"])

bank_df = pd.DataFrame()
ar_df = pd.DataFrame()
ap_df = pd.DataFrame()

try:
    if bank_file:
        bank_df = load_bank_csv(bank_file)
    if ar_file:
        ar_df = load_schedule_csv(ar_file, "AR")
    if ap_file:
        ap_df = load_schedule_csv(ap_file, "AP")
except Exception as exc:
    st.error(str(exc))
    st.stop()

st.subheader("2. Add recurring cash items")
with st.form("recurring_form"):
    r_col1, r_col2, r_col3, r_col4 = st.columns(4)
    with r_col1:
        recurring_description = st.text_input("Description", value="Payroll")
    with r_col2:
        recurring_amount = st.number_input("Amount", value=-15000.00, step=500.00, format="%.2f")
    with r_col3:
        recurring_frequency = st.selectbox("Frequency", ["Weekly", "Biweekly", "Monthly"], index=1)
    with r_col4:
        add_recurring = st.form_submit_button("Add / refresh recurring item")

recurring_df = recurring_schedule(
    recurring_description,
    recurring_amount,
    start_date,
    start_date + timedelta(days=(weeks * 7) - 1),
    recurring_frequency,
)

st.subheader("3. Known transaction keywords")
default_keywords = "payroll, rent, insurance, loan, fuel, supplier, materials, customer, deposit, tax"
known_keywords_text = st.text_area(
    "Comma-separated keywords used to identify expected transactions",
    value=default_keywords,
)
known_keywords = [k.strip() for k in known_keywords_text.split(",")]

st.subheader("4. Forecast results")
daily = build_daily_forecast(
    beginning_cash=beginning_cash,
    start_date=start_date,
    weeks=weeks,
    ar_df=ar_df,
    ap_df=ap_df,
    recurring_df=recurring_df,
    include_probability=include_probability,
)
weekly = weekly_summary(daily)
unknown = flag_unknown_transactions(bank_df, known_keywords)

metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
metric_col1.metric("Projected ending cash", f"${daily['projected_cash'].iloc[-1]:,.0f}")
metric_col2.metric("Lowest projected cash", f"${daily['projected_cash'].min():,.0f}")
metric_col3.metric("Total forecast inflows", f"${daily['cash_in'].sum():,.0f}")
metric_col4.metric("Total forecast outflows", f"${daily['cash_out'].sum():,.0f}")

if daily["projected_cash"].min() < low_cash_threshold:
    first_low = daily[daily["projected_cash"] < low_cash_threshold].iloc[0]
    st.warning(f"Projected cash falls below threshold on {first_low['date']}: ${first_low['projected_cash']:,.0f}")

st.line_chart(daily.set_index("date")[["projected_cash"]])

left, right = st.columns(2)
with left:
    st.markdown("### Weekly forecast")
    st.dataframe(weekly, use_container_width=True)
with right:
    st.markdown("### Unknown / unaccounted-for bank transactions")
    st.dataframe(unknown, use_container_width=True)

with st.expander("Daily forecast detail"):
    st.dataframe(daily, use_container_width=True)

with st.expander("Uploaded data preview"):
    st.markdown("#### Bank transactions")
    st.dataframe(bank_df, use_container_width=True)
    st.markdown("#### AR")
    st.dataframe(ar_df, use_container_width=True)
    st.markdown("#### AP")
    st.dataframe(ap_df, use_container_width=True)
    st.markdown("#### Recurring")
    st.dataframe(recurring_df, use_container_width=True)

output = BytesIO()
with pd.ExcelWriter(output, engine="openpyxl") as writer:
    weekly.to_excel(writer, sheet_name="Weekly Forecast", index=False)
    daily.to_excel(writer, sheet_name="Daily Forecast", index=False)
    unknown.to_excel(writer, sheet_name="Unknown Transactions", index=False)
    bank_df.to_excel(writer, sheet_name="Bank Transactions", index=False)
    ar_df.to_excel(writer, sheet_name="AR", index=False)
    ap_df.to_excel(writer, sheet_name="AP", index=False)

st.download_button(
    label="Download forecast workbook",
    data=output.getvalue(),
    file_name="construction_cash_forecast.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

st.markdown("---")
st.markdown("""
**Expected CSV formats**

Bank transactions: `date, description, amount, category, status`  
AR/AP schedules: `name, due_date, amount, probability`

Use positive amounts in AR/AP files. The app treats AR as inflows and AP/recurring items as outflows.
""")

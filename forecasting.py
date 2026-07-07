from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable

import pandas as pd


BANK_REQUIRED = {"date", "description", "amount"}
AR_AP_REQUIRED = {"name", "due_date", "amount"}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df


def load_bank_csv(file) -> pd.DataFrame:
    df = _normalize_columns(pd.read_csv(file))
    missing = BANK_REQUIRED - set(df.columns)
    if missing:
        raise ValueError(f"Bank CSV is missing columns: {', '.join(sorted(missing))}")
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    df["description"] = df["description"].astype(str)
    if "category" not in df.columns:
        df["category"] = "Uncategorized"
    if "status" not in df.columns:
        df["status"] = "posted"
    return df[["date", "description", "amount", "category", "status"]]


def load_schedule_csv(file, kind: str) -> pd.DataFrame:
    df = _normalize_columns(pd.read_csv(file))
    missing = AR_AP_REQUIRED - set(df.columns)
    if missing:
        raise ValueError(f"{kind} CSV is missing columns: {', '.join(sorted(missing))}")
    df["due_date"] = pd.to_datetime(df["due_date"]).dt.date
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    df["name"] = df["name"].astype(str)
    if "probability" not in df.columns:
        df["probability"] = 1.0
    df["probability"] = pd.to_numeric(df["probability"], errors="coerce").fillna(1.0).clip(0, 1)
    df["type"] = kind
    return df[["name", "due_date", "amount", "probability", "type"]]


def recurring_schedule(
    description: str,
    amount: float,
    start_date: date,
    end_date: date,
    frequency: str,
) -> pd.DataFrame:
    if not description or amount == 0:
        return pd.DataFrame(columns=["name", "due_date", "amount", "probability", "type"])

    frequency = frequency.lower()
    if frequency == "weekly":
        rule = "W-MON"
    elif frequency == "biweekly":
        # Build manually because pandas frequency aliases can be unintuitive for users.
        dates = []
        current = start_date
        while current <= end_date:
            dates.append(current)
            current += timedelta(days=14)
        return pd.DataFrame({
            "name": description,
            "due_date": dates,
            "amount": amount,
            "probability": 1.0,
            "type": "Recurring",
        })
    elif frequency == "monthly":
        rule = "MS"
    else:
        raise ValueError("frequency must be Weekly, Biweekly, or Monthly")

    dates = pd.date_range(start=start_date, end=end_date, freq=rule).date
    return pd.DataFrame({
        "name": description,
        "due_date": dates,
        "amount": amount,
        "probability": 1.0,
        "type": "Recurring",
    })


def build_daily_forecast(
    beginning_cash: float,
    start_date: date,
    weeks: int,
    ar_df: pd.DataFrame | None,
    ap_df: pd.DataFrame | None,
    recurring_df: pd.DataFrame | None,
    include_probability: bool = True,
) -> pd.DataFrame:
    end_date = start_date + timedelta(days=(weeks * 7) - 1)
    forecast = pd.DataFrame({"date": pd.date_range(start_date, end_date).date})
    forecast["cash_in"] = 0.0
    forecast["cash_out"] = 0.0

    schedules = []
    for df in [ar_df, ap_df, recurring_df]:
        if df is not None and not df.empty:
            schedules.append(df.copy())

    if schedules:
        schedule = pd.concat(schedules, ignore_index=True)
        schedule["weighted_amount"] = schedule["amount"] * (schedule["probability"] if include_probability else 1.0)
        grouped = schedule.groupby(["due_date", "type"], as_index=False)["weighted_amount"].sum()

        for _, row in grouped.iterrows():
            mask = forecast["date"] == row["due_date"]
            if row["type"] == "AR":
                forecast.loc[mask, "cash_in"] += max(row["weighted_amount"], 0)
            else:
                forecast.loc[mask, "cash_out"] += abs(row["weighted_amount"])

    forecast["net_cash_flow"] = forecast["cash_in"] - forecast["cash_out"]
    forecast["projected_cash"] = beginning_cash + forecast["net_cash_flow"].cumsum()
    forecast["week_start"] = pd.to_datetime(forecast["date"]).dt.to_period("W-MON").apply(lambda r: r.start_time.date())
    return forecast


def weekly_summary(daily_forecast: pd.DataFrame) -> pd.DataFrame:
    weekly = daily_forecast.groupby("week_start", as_index=False).agg(
        cash_in=("cash_in", "sum"),
        cash_out=("cash_out", "sum"),
        net_cash_flow=("net_cash_flow", "sum"),
        ending_cash=("projected_cash", "last"),
        minimum_cash=("projected_cash", "min"),
    )
    return weekly


def flag_unknown_transactions(bank_df: pd.DataFrame, known_keywords: Iterable[str]) -> pd.DataFrame:
    if bank_df is None or bank_df.empty:
        return pd.DataFrame(columns=["date", "description", "amount", "category", "status", "reason"])

    keywords = [k.lower().strip() for k in known_keywords if k and str(k).strip()]
    df = bank_df.copy()
    df["description_lower"] = df["description"].str.lower()
    df["reason"] = ""

    if keywords:
        known_mask = df["description_lower"].apply(lambda text: any(k in text for k in keywords))
    else:
        known_mask = pd.Series(False, index=df.index)

    uncategorized_mask = df["category"].str.lower().isin(["uncategorized", "unknown", "", "nan"])
    unknown = df[(~known_mask) | uncategorized_mask].copy()
    unknown.loc[~known_mask, "reason"] = "No known keyword match"
    unknown.loc[uncategorized_mask, "reason"] = unknown.loc[uncategorized_mask, "reason"].replace("", "Uncategorized")
    return unknown.drop(columns=["description_lower"])

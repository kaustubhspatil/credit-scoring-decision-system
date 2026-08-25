"""
Sentinel fixes, unit conversions, and missingness reporting.

The Home Credit tables hide missing values behind sentinels and encode
durations as negative day counts. Everything here is idempotent and applied
identically to every split.
"""

import numpy as np
import pandas as pd

DAYS_EMPLOYED_SENTINEL = 365243  # ~1000 years "employed" = pensioner/unemployed flag


def fix_sentinels(df):
    """
    Replace known sentinel values with NaN and keep an indicator column,
    so the information ("this applicant is not currently employed") survives
    while the fake magnitude (1000 years) does not.
    """
    out = df.copy()

    # DAYS_EMPLOYED = 365243 marks pensioners/unemployed, not 1000-year tenure
    sent = out["DAYS_EMPLOYED"] == DAYS_EMPLOYED_SENTINEL
    out["FLAG_NOT_EMPLOYED"] = sent.astype("int8")
    out.loc[sent, "DAYS_EMPLOYED"] = np.nan

    # CODE_GENDER has 4 'XNA' rows - too few to model as a category
    if "CODE_GENDER" in out.columns:
        out.loc[out["CODE_GENDER"] == "XNA", "CODE_GENDER"] = np.nan

    # ORGANIZATION_TYPE uses the string 'XNA' as its missing marker
    if "ORGANIZATION_TYPE" in out.columns:
        out.loc[out["ORGANIZATION_TYPE"] == "XNA", "ORGANIZATION_TYPE"] = np.nan

    return out


def add_readable_units(df):
    """DAYS_* columns are negative day counts from application date; add
    positive year versions for the columns humans actually reason about."""
    out = df.copy()
    out["AGE_YEARS"] = (-out["DAYS_BIRTH"] / 365.25).astype("float32")
    out["EMPLOYED_YEARS"] = (-out["DAYS_EMPLOYED"] / 365.25).astype("float32")
    out["REGISTRATION_YEARS"] = (-out["DAYS_REGISTRATION"] / 365.25).astype("float32")
    return out


def missing_summary(df, top=25):
    """Columns ranked by missing share, with dtype - the EDA missingness table."""
    miss = df.isna().mean().sort_values(ascending=False)
    miss = miss[miss > 0]
    return pd.DataFrame({
        "missing_share": miss,
        "dtype": df.dtypes[miss.index].astype(str),
    }).head(top)

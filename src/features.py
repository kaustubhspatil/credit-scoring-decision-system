"""
Domain feature engineering: financial ratios, bureau aggregation, encoding.

Every feature has an economic rationale (the Five Cs of credit):
  Character - bureau history aggregates (overdue, defaults, credit age)
  Capacity  - debt-to-income, annuity-to-income
  Capital   - own car / realty flags (already in the data)
  Collateral- credit-to-goods ratio
  Conditions- external scores, regional ratings (already in the data)
"""

import numpy as np
import pandas as pd


def add_ratio_features(df):
    """Capacity and collateral ratios computed from the application table."""
    out = df.copy()
    eps = 1e-8
    income = out["AMT_INCOME_TOTAL"].clip(lower=1)

    out["DTI"] = out["AMT_ANNUITY"] / (income + eps)                # debt service / income
    out["CREDIT_TO_INCOME"] = out["AMT_CREDIT"] / (income + eps)    # leverage
    out["CREDIT_TO_GOODS"] = out["AMT_CREDIT"] / (out["AMT_GOODS_PRICE"] + eps)
    out["ANNUITY_TO_CREDIT"] = out["AMT_ANNUITY"] / (out["AMT_CREDIT"] + eps)
    out["INCOME_PER_PERSON"] = income / (out["CNT_FAM_MEMBERS"].fillna(1).clip(lower=1))
    out["EMPLOYED_SHARE_OF_LIFE"] = out["EMPLOYED_YEARS"] / (out["AGE_YEARS"] + eps)

    # the three external scores are the strongest single predictors;
    # their mean and count-of-present capture level and coverage
    ext = out[["EXT_SOURCE_1", "EXT_SOURCE_2", "EXT_SOURCE_3"]]
    out["EXT_SOURCE_MEAN"] = ext.mean(axis=1)
    out["EXT_SOURCE_MIN"] = ext.min(axis=1)
    out["EXT_SOURCE_COUNT"] = ext.notna().sum(axis=1).astype("int8")

    # document count: how much paperwork the applicant provided
    doc_cols = [c for c in out.columns if c.startswith("FLAG_DOCUMENT_")]
    out["DOCUMENT_COUNT"] = out[doc_cols].sum(axis=1).astype("int8")
    return out


def aggregate_bureau(bureau):
    """
    Collapse 1.7M bureau records into one row per applicant (SK_ID_CURR):
    the Character evidence. Every aggregate uses only information that was
    already on the bureau report at application time.
    """
    b = bureau.copy()
    b["IS_ACTIVE"] = (b["CREDIT_ACTIVE"] == "Active").astype("int8")
    b["IS_CLOSED"] = (b["CREDIT_ACTIVE"] == "Closed").astype("int8")
    b["HAS_OVERDUE"] = (b["CREDIT_DAY_OVERDUE"] > 0).astype("int8")
    # utilization on active credit lines: debt / limit-or-principal
    denom = b[["AMT_CREDIT_SUM_LIMIT", "AMT_CREDIT_SUM"]].max(axis=1)
    b["UTILIZATION"] = (b["AMT_CREDIT_SUM_DEBT"] / denom.replace(0, np.nan)).clip(0, 2)

    agg = b.groupby("SK_ID_CURR").agg(
        BURO_COUNT=("SK_ID_BUREAU", "count"),
        BURO_ACTIVE_COUNT=("IS_ACTIVE", "sum"),
        BURO_CLOSED_COUNT=("IS_CLOSED", "sum"),
        BURO_OVERDUE_COUNT=("HAS_OVERDUE", "sum"),
        BURO_DAYS_OVERDUE_MAX=("CREDIT_DAY_OVERDUE", "max"),
        BURO_AMT_OVERDUE_MAX=("AMT_CREDIT_MAX_OVERDUE", "max"),
        BURO_AMT_OVERDUE_SUM=("AMT_CREDIT_SUM_OVERDUE", "sum"),
        BURO_DEBT_SUM=("AMT_CREDIT_SUM_DEBT", "sum"),
        BURO_CREDIT_SUM=("AMT_CREDIT_SUM", "sum"),
        BURO_UTILIZATION_MEAN=("UTILIZATION", "mean"),
        BURO_PROLONG_SUM=("CNT_CREDIT_PROLONG", "sum"),
        BURO_OLDEST_YEARS=("DAYS_CREDIT", lambda s: -s.min() / 365.25),
        BURO_NEWEST_YEARS=("DAYS_CREDIT", lambda s: -s.max() / 365.25),
        BURO_TYPES=("CREDIT_TYPE", "nunique"),
    ).astype("float32")

    agg["BURO_OVERDUE_SHARE"] = (agg["BURO_OVERDUE_COUNT"] /
                                 agg["BURO_COUNT"].replace(0, np.nan))
    agg["BURO_DEBT_TO_CREDIT"] = (agg["BURO_DEBT_SUM"] /
                                  agg["BURO_CREDIT_SUM"].replace(0, np.nan))
    return agg.reset_index()


def merge_bureau(app, bureau_agg):
    """Left-join bureau aggregates; applicants with no bureau file get
    count 0 and NaN for the ratio features (a real signal: thin file)."""
    out = app.merge(bureau_agg, on="SK_ID_CURR", how="left")
    out["HAS_BUREAU_FILE"] = out["BURO_COUNT"].notna().astype("int8")
    out["BURO_COUNT"] = out["BURO_COUNT"].fillna(0)
    return out

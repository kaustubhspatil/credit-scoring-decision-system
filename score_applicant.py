"""
Live scoring demo - Day 10 presentation.

Scores a loan applicant end-to-end with the deployed pipeline and prints the
decision exactly as the underwriting system would issue it: the probability of
default, the approve/decline call at the approved cut-off, and - when declined -
the four principal reasons required by FCAC / ECOA adverse-action rules,
derived from that applicant's own SHAP decomposition.

The gender-free pipeline is loaded by default (the version recommended for
deployment in reports/backtest_report.md).

Usage:
    python score_applicant.py                  # score a representative declined applicant
    python score_applicant.py --row 42         # score a specific test-set row
    python score_applicant.py --riskiest       # the highest-risk applicant in the test set
    python score_applicant.py --waterfall      # also save the SHAP waterfall plot
"""

import argparse

import joblib
import numpy as np
import pandas as pd

from src import config

THRESHOLD = 0.07   # approved decline cut-off (profit-maximizing; see notebook 04)

REASON_MAP = {
    "EXT_SOURCE": "Low external credit bureau score",
    "AGE_YEARS": "Limited length of credit and personal history",
    "DAYS_BIRTH": "Limited length of credit and personal history",
    "EMPLOYED": "Short or unstable employment history",
    "DTI": "High debt payment relative to income",
    "ANNUITY": "High payment burden on requested credit",
    "CREDIT_TO_GOODS": "Requested credit high relative to purchase value",
    "CREDIT_TO_INCOME": "Requested credit high relative to income",
    "AMT_OVERDUE": "Amounts past due on existing credit obligations",
    "DAYS_OVERDUE": "Length of time payments have been past due",
    "BURO_OVERDUE": "Past-due payments on existing credit obligations",
    "BURO_UTILIZATION": "High utilization of existing credit lines",
    "BURO_DEBT": "High outstanding debt at other lenders",
    "BURO_ACTIVE": "Number of active credit obligations at other lenders",
    "BURO_COUNT": "Number of existing credit obligations",
    "BURO_OLDEST": "Limited length of credit history",
    "BURO_NEWEST": "Recently opened credit obligations",
    "BURO_PROLONG": "Extensions taken on existing credit",
    "BURO_TYPES": "Mix of existing credit types",
    "HAS_BUREAU": "Limited credit bureau history",
    "AMT_INCOME": "Income level relative to requested credit",
    "OWN_CAR_AGE": "Limited asset profile",
    "REGION": "Regional risk factors",           # covers RATING and POPULATION_RELATIVE
    "CITY": "Regional risk factors",
    "DOCUMENT": "Incomplete application documentation",
    "PHONE": "Recent changes to contact information",
    "BUILDING": "Incomplete housing information",
    "OCCUPATION": "Occupation category risk factors",
    "ORGANIZATION": "Employer category risk factors",
    "NAME_EDUCATION": "Education category risk factors",
    "NAME_FAMILY": "Household composition risk factors",
    "NAME_HOUSING": "Housing situation risk factors",
    "NAME_INCOME": "Income source risk factors",
    "NAME_CONTRACT": "Requested product type",
    "CNT_CHILDREN": "Household composition risk factors",
    "CNT_FAM": "Household composition risk factors",
    "GOODS_PRICE": "Requested credit high relative to purchase value",
    "PEER_GROUP": "Risk profile relative to comparable applicants",
    "SOCIAL_CIRCLE": "Credit performance within the applicant's reported network",
    "FLAG_OWN": "Limited asset profile",
    "REALTY": "Limited asset profile",
    "AMT_REQ_CREDIT_BUREAU": "Frequency of recent credit inquiries",
    "AMT_CREDIT": "Amount of credit requested",
    "BURO_CLOSED": "History of closed credit obligations",
    "BURO_CREDIT_SUM": "Total credit extended by other lenders",
    "DAYS_ID_PUBLISH": "Recent changes to identity documents",
    "DAYS_REGISTRATION": "Length of time at current registration",
    "DAYS_LAST_PHONE": "Recent changes to contact information",
    # the 47-column building/housing block all resolves to one consumer phrase
    "APARTMENTS": "Incomplete housing information",
    "BASEMENTAREA": "Incomplete housing information",
    "COMMONAREA": "Incomplete housing information",
    "ELEVATORS": "Incomplete housing information",
    "ENTRANCES": "Incomplete housing information",
    "FLOORS": "Incomplete housing information",
    "LANDAREA": "Incomplete housing information",
    "LIVINGAPARTMENTS": "Incomplete housing information",
    "LIVINGAREA": "Incomplete housing information",
    "NONLIVING": "Incomplete housing information",
    "YEARS_BEGIN": "Incomplete housing information",
    "YEARS_BUILD": "Incomplete housing information",
    "TOTALAREA": "Incomplete housing information",
    "WALLSMATERIAL": "Incomplete housing information",
    "HOUSETYPE": "Incomplete housing information",
    "EMERGENCYSTATE": "Incomplete housing information",
    "FONDKAPREMONT": "Incomplete housing information",
    "OBS_": "Credit performance within the applicant's reported network",
    "DEF_": "Credit performance within the applicant's reported network",
    "WEEKDAY": "Application submission characteristics",
    "HOUR_APPR": "Application submission characteristics",
    "TYPE_SUITE": "Application submission characteristics",
    "REG_": "Consistency of address information provided",
    "LIVE_": "Consistency of address information provided",
    "MOBIL": "Contact information provided",
    "EMAIL": "Contact information provided",
    "EMPLOY_PHONE": "Contact information provided",
    "WORK_PHONE": "Contact information provided",
    "CONT_MOBILE": "Contact information provided",
    "INCOME_PER_PERSON": "Income relative to household size",
    "REGISTRATION_YEARS": "Length of time at current registration",
}

# Consumer-facing fallback. A raw column name must NEVER reach an adverse-action
# notice, so the default is a lawful generic phrase rather than the feature name.
GENERIC_REASON = "Other credit risk factors present in the application"


def plain_reason(feature_name):
    """Translate a model feature name into consumer-facing language."""
    for key, text in REASON_MAP.items():
        if key in feature_name.upper():
            return text
    return GENERIC_REASON


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--row", type=int, default=None, help="test-set row index to score")
    ap.add_argument("--riskiest", action="store_true", help="score the highest-risk applicant")
    ap.add_argument("--waterfall", action="store_true", help="save the SHAP waterfall plot")
    args = ap.parse_args()

    # ── Load the deployed pipeline (gender-free version) and the sealed test set ──
    model_path = config.MODELS_DIR / "credit_scoring_pipeline_nogender.pkl"
    if not model_path.exists():
        model_path = config.MODELS_DIR / "credit_scoring_pipeline.pkl"
    clf = joblib.load(model_path)

    test = pd.read_parquet(config.PROCESSED_DIR / "test_features.parquet")
    drop = [c for c in ("TARGET", "SK_ID_CURR") if c in test.columns]
    X = test.drop(columns=drop)
    X = X[[c for c in X.columns if c in clf.feature_names_in_]] \
        if hasattr(clf, "feature_names_in_") else X

    pd_all = clf.predict_proba(X)[:, 1]

    # ── Pick the applicant to demo ──
    if args.row is not None:
        i = args.row
    elif args.riskiest:
        i = int(np.argmax(pd_all))
    else:
        # a representative declined applicant: just above the cut-off
        declined = np.where(pd_all >= THRESHOLD)[0]
        i = int(declined[np.argmin(np.abs(pd_all[declined] - 0.15))])

    row = test.iloc[i]
    prob = float(pd_all[i])
    decision = "DECLINE" if prob >= THRESHOLD else "APPROVE"

    print()
    print("=" * 70)
    print("  CONSUMER CREDIT - AUTOMATED UNDERWRITING DECISION")
    print(f"  Model: {model_path.name}  |  cut-off: PD >= {THRESHOLD:.0%}")
    print("=" * 70)
    print(f"\n  Applicant ID:          {int(row.get('SK_ID_CURR', i)):,}")
    print(f"  Requested credit:      {row.get('AMT_CREDIT', float('nan')):,.0f}")
    print(f"  Reported income:       {row.get('AMT_INCOME_TOTAL', float('nan')):,.0f}")
    emp = row.get("EMPLOYED_YEARS", float("nan"))
    emp_txt = ("not currently employed (pensioner/unemployed)"
               if pd.isna(emp) else f"{emp:.1f} yrs employed")
    print(f"  Age / employment:      {row.get('AGE_YEARS', float('nan')):.0f} yrs / {emp_txt}")
    print(f"  Bureau records:        {row.get('BURO_COUNT', 0):.0f}")
    print()
    print(f"  PROBABILITY OF DEFAULT:  {prob:.1%}   "
          f"(portfolio average {test['TARGET'].mean():.1%})")
    print(f"  DECISION:                {decision}")
    print(f"  Actual outcome in data:  {'DEFAULTED' if row['TARGET'] == 1 else 'repaid'}"
          "   <- hindsight only, not an input")

    # ── Adverse-action reasons from this applicant's own SHAP values ──
    if decision == "DECLINE":
        import shap

        # the saved pipeline is prep -> clf; SHAP explains the estimator, so we
        # transform the row through prep first and carry the expanded names over
        estimator = clf.named_steps["clf"]
        prep = clf.named_steps["prep"]
        Xt = prep.transform(X.iloc[[i]])
        try:
            feat_names = list(prep.get_feature_names_out())
        except Exception:
            feat_names = [f"f{j}" for j in range(Xt.shape[1])]

        explainer = shap.TreeExplainer(estimator)
        sv = explainer(Xt)
        sv.feature_names = feat_names

        names = feat_names
        vals = sv.values[0]
        order = np.argsort(-vals)

        reasons, seen = [], set()
        for j in order:
            if vals[j] <= 0:
                break
            r = plain_reason(str(names[j]))
            if r not in seen:
                reasons.append(r)
                seen.add(r)
            if len(reasons) == 4:
                break

        print("\n  PRINCIPAL REASONS FOR ADVERSE ACTION")
        print("  (required by FCAC / ECOA - generated from this applicant's own")
        print("   SHAP contributions, not a generic template)\n")
        for n, r in enumerate(reasons, 1):
            print(f"    {n}. {r}")

        if args.waterfall:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            shap.plots.waterfall(sv[0], max_display=12, show=False)
            out = config.FIGURES_DIR / "demo_waterfall.png"
            plt.tight_layout()
            plt.savefig(out, dpi=150, bbox_inches="tight")
            plt.close()
            print(f"\n  SHAP waterfall saved -> {out}")
    else:
        print("\n  No adverse-action notice required (application approved).")

    print("\n" + "-" * 70)
    print("  Every number above is reproducible: the pipeline carries its own")
    print("  imputation, encoding and scaling, so raw application data goes in")
    print("  and a decision plus its legally-required explanation comes out.")
    print("-" * 70 + "\n")


if __name__ == "__main__":
    main()

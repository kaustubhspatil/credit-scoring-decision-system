# Credit Scoring Model — Module 1 Capstone

**Can we predict, at application time, which consumer loans will go bad — and what is that prediction worth in dollars?**

Built on the Home Credit dataset: 307,511 real loan applications (8.07% default rate) plus
1.7M credit-bureau records from other lenders. The capstone delivers a production-style
scoring pipeline (one serialized artifact: preprocessing + model), a profit-maximizing
decline policy with the trade-offs quantified in dollars, SHAP-based adverse-action
reasons, PSI monitoring that has actually been fired on a simulated recession cohort, and
a fairness audit that finds, measures, and fixes a protected-attribute defect.

## Repository layout

```
capstone/
├── data/
│   ├── application_train.csv     ← 307,511 applications x 122 columns
│   ├── bureau.csv                ← 1,716,428 bureau records (joins on SK_ID_CURR)
│   └── processed/                ← clean splits, feature matrices, predictions (built by nb 02–04)
├── notebooks/
│   ├── 01_eda.ipynb              ← target imbalance, the sentinel hunt, who defaults
│   ├── 02_preprocessing.ipynb    ← sentinel audit, missingness strategy, stratified splits
│   ├── 03_feature_engineering.ipynb ← Five-Cs ratios, bureau aggregation, K-Means peer groups
│   ├── 04_modeling.ipynb         ← scorecard vs forest vs boosting, tuning, profit threshold
│   └── 05_explainability.ipynb   ← SHAP, adverse action, PSI, segments, fairness
├── src/                          ← all reusable code (cleaning, features, evaluation…)
├── models/
│   ├── credit_scoring_pipeline.pkl          ← champion (preprocessing + model, one artifact)
│   ├── credit_scoring_pipeline_nogender.pkl ← recommended: protected attribute removed
│   ├── logistic_baseline.pkl and peer_group_clusterer.pkl
├── reports/                      ← executive summary, model documentation, stability report
│   └── figures/                  ← every chart, publication-ready PNG
└── README.md
```

## Reproduce end-to-end

Python 3.11+, no GPU needed:

```bash
pip install numpy pandas matplotlib scikit-learn joblib pyarrow scipy shap jupyter nbformat nbconvert ipykernel
cd capstone
jupyter notebook    # run notebooks 01 → 05 top to bottom
```

Or headless:

```bash
cd capstone/notebooks
for nb in 01_eda 02_preprocessing 03_feature_engineering 04_modeling 05_explainability; do
    python -m nbconvert --to notebook --execute --inplace $nb.ipynb
done
```

**Live scoring demo** (the Day-10 presentation walkthrough) — scores an applicant
end to end and prints the decision plus its adverse-action reasons:

```bash
python score_applicant.py --riskiest --waterfall
```

Approximate runtimes on a modern laptop: 01 ≈ 4 min, 02 ≈ 2 min, 03 ≈ 5 min,
04 ≈ 25 min (model training + randomized search), 05 ≈ 8 min.

## Design decisions that matter

- **Split first, fit second.** Stratified 70/15/15; the test split is sealed until its
  single opening in notebook 04 §6. All fitted transforms (imputers, encoders, the
  clusterer, models) live inside sklearn Pipelines, so CV re-fits them per fold and
  leakage is structurally impossible.
- **Sentinels are fixed, not ignored:** `DAYS_EMPLOYED = 365243` (18% of rows — the
  pensioners) becomes NaN + `FLAG_NOT_EMPLOYED`; a systematic audit confirms no other
  column hides one.
- **Missingness is treated as signal** (per-cause strategy: block flag for the
  building-info columns, explicit "Missing" category for categoricals) — the EDA proves
  absence predicts default.
- **No class weighting, on purpose:** calibrated PDs are required downstream (dollar
  math, adverse action), and weighting distorts them; the asymmetric costs are handled
  where they belong — in the decline threshold, chosen on a profit curve over real
  exposure amounts.
- **Honest fairness handling:** the model is retrained without `CODE_GENDER`, the cost
  is quantified, and the gender-free pipeline is the deployment recommendation.

## Deliverables

- [`reports/executive_summary.md`](reports/executive_summary.md) — one page, dollars first
- [`reports/model_documentation.md`](reports/model_documentation.md) — OSFI E-23-style validation pack
- [`reports/backtest_report.md`](reports/backtest_report.md) — out-of-sample performance by segment, PSI stability, fairness audit
- `reports/figures/` — all charts at 150 dpi

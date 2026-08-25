# Model Documentation — Consumer Credit Scoring Model

**Model:** Histogram Gradient Boosting classifier (gender-free variant recommended)
**Prepared for:** Model Validation / Review Committee (OSFI E-23 framework)
**Prepared by:** Kaustubh Patil
**Date:** 20 August 2026
**Status:** Recommended for deployment with conditions (see Executive Summary)

---

## 1. Model Purpose

Supports the underwriting decision (approve / decline / refer) for consumer credit
applications by estimating each applicant's probability of payment difficulties
(`TARGET = 1`: late > threshold days on at least one installment). Output is a calibrated
PD consumed by (a) the decline policy at threshold PD ≥ 0.07, (b) adverse-action reason
generation, and (c) portfolio monitoring.

## 2. Methodology

| Item | Specification |
|---|---|
| Algorithm | `HistGradientBoostingClassifier` (scikit-learn); tuned by randomized search (10 candidates × 3-fold stratified CV on train only): learning rate 0.05, 63 leaf nodes, min 20 samples/leaf, L2 = 10, 400 iterations, early stopping |
| Inputs | 153 features: 137 numeric + 16 categorical (one-hot, unseen-level-safe). Families: application characteristics; engineered capacity/collateral ratios (DTI, credit-to-income, credit-to-goods…); external scores and combinations; 17 bureau aggregates (overdue, utilization, credit age) from 1.7M records; K-Means peer group; missingness indicators |
| Preprocessing | Single sklearn `Pipeline`: median imputation (numeric), constant-"Missing" imputation + one-hot (categorical). Fitted inside the pipeline → refit per CV fold, leakage structurally impossible |
| Data | 307,511 applications; stratified 70/15/15 (215,257 / 46,127 / 46,127); default rate 8.07% in every split; test sealed until final evaluation |
| Sentinels | `DAYS_EMPLOYED = 365243` (18% of rows) → NaN + indicator; systematic audit of all columns found no others |
| Class balance | **No class weighting** — deliberate, to preserve calibration (PDs are consumed as probabilities); asymmetric costs handled at the decision threshold |
| Reproducibility | Seed 42 end-to-end; artifacts: `credit_scoring_pipeline.pkl` (champion), `credit_scoring_pipeline_nogender.pkl` (deployment candidate), `peer_group_clusterer.pkl` |

## 3. Performance

**Discrimination (sealed test, n = 46,127):**

| Metric | Champion | Logistic baseline | Champion (validation) |
|---|---|---|---|
| AUROC | **0.774** | 0.757 | 0.773 |
| Gini | 0.547 | 0.514 | 0.545 |
| KS | 0.416 | 0.382 | 0.405 |
| PR-AUC (base rate 8.07%) | 0.262 | 0.244 | 0.263 |

**Stability of the estimate:** 5-fold CV on train 0.768 ± 0.005, validation 0.773,
test 0.774 — three independent readings agree within half a point. Train AUROC is 0.832;
the ~6-point train gap is memorization headroom typical of boosted trees and is why the
train score is never quoted as performance.

**Calibration:** predicted vs observed default rates track by decile
(`figures/mod_calibration.png`); Brier 0.067. The top decile concentrates roughly a
third of all defaults.

**Business outcome at the production threshold (PD ≥ 0.07, test book):** approval rate
63.2%; default recall 74.5%; prevented losses $972.0M vs foregone profit $393.3M →
net +$578.7M against approve-everything (assumptions: LGD 65%, lifetime margin 5%,
exposure = requested credit).

## 4. Baseline Comparison

The logistic scorecard on identical inputs trails by 1.7 AUROC points on test.
The gap is the value of nonlinear interactions (bureau × capacity × external scores).
The scorecard remains the fallback model and the interpretability reference.

## 5. Limitations and Known Failure Modes

1. **No temporal validation.** The dataset carries no application dates, so splits are
   random, not out-of-time. PSI monitoring (below) is the compensating control until
   dated cohorts allow a proper out-of-time test.
2. **Approved-population bias.** Training data contains only funded loans; the model has
   never seen the behavior of applicants the old process declined (reject-inference is
   in the iteration plan).
3. **Macro blindness.** No cycle variables; a recession shifts PDs upward en masse.
   The simulated-recession PSI test (notebook 05) demonstrates the alarm fires.
4. **Thin files.** Applicants without bureau history (14%) are the weakest segment.
5. **Proxy discrimination risk.** Gender was removed (cost: ~0 AUROC), but correlated
   pathways (occupation, family status) require the quarterly fairness re-audit.

## 6. Monitoring Plan

| Monitor | Cadence | Threshold | Action |
|---|---|---|---|
| Score PSI vs frozen train reference | Monthly | > 0.10 monitor · > 0.25 | Investigate / revalidate |
| Feature PSI (top 15 features) | Monthly | > 0.25 on any | Investigate data pipeline & population |
| Realized default rate by score decile | Quarterly | Observed > predicted × 1.25 in 2+ deciles | Recalibrate |
| Segment AUROC (peer groups, income types) | Quarterly | Any segment < overall − 0.05 | Segment review |
| Adverse-impact ratios (gender, age bands) | Quarterly | AIR < 0.80 | Compliance escalation |
| Retraining | Monthly champion/challenger | Challenger beats champion 2 consecutive months | Promote |

## 7. Data Quality Assessment

Source tables complete on the join key (`SK_ID_CURR`); 85.7% of applicants have bureau
files (absence itself used as a feature, not imputed away). Missingness is handled by
declared strategy per cause (block flags, explicit "Missing" levels, indicators).
Known quirks — the employment sentinel, `XNA` markers — are fixed in `src/cleaning.py`
with an audit cell that re-checks every new data drop.

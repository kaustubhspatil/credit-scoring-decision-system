# Backtest & Stability Report — Credit Scoring Model

**Scope:** performance by segment, population stability, and disparate-impact analysis
of the champion model on the sealed test set (46,127 applications).
**Prepared by:** Kaustubh Patil · 20 August 2026

> The dataset carries no application dates, so period-over-period analysis is
> impossible; this report covers the two compensating controls — segment stability and
> distributional stability (PSI) — plus the fairness audit. Out-of-time validation is
> the first item on the roadmap once dated cohorts exist.

---

## 1. Performance by Segment

AUROC re-computed inside each major segment of the test set (all segments n ≥ 1,500);
chart: `figures/exp_segment_auroc.png`. Overall test AUROC: **0.774**.

- Every income-type, education, and peer-group segment ranks risk within a few points
  of the overall line — no segment falls off a cliff.
- The **thin-file peer group** (no/limited bureau history; the riskiest cluster at 10.2%
  default) is the weakest segment, as expected with the least Character evidence.
  Recommendation: manual-review lane rather than model-only decisions for thin files.
- Default-rate levels vary ~2.5× across segments (age and income type dominate); the
  model's *ranking* quality is what stays uniform.

## 2. Population Stability (PSI)

Reference = frozen training distribution. Thresholds: **< 0.10** stable ·
**0.10–0.25** monitor · **> 0.25** investigate.

| Comparison | PSI | Status |
|---|---|---|
| Score: train vs test (random-split control) | 0.0002 | stable ✔ |
| Score: train vs **simulated severe recession** (incomes −25%, external scores −20%) | **0.337** | **INVESTIGATE — alarm fires ✔** |
| EXT_SOURCE_MEAN, AMT_INCOME_TOTAL, DTI, AGE_YEARS, BURO_COUNT (train vs test) | ≤ 0.001 | stable ✔ |

Both controls behave: near-zero on identically-distributed splits (negative control),
loud alarm on the stressed cohort (positive control). A milder shock (incomes −15%,
scores −10%) measured PSI 0.09 — just under the monitor line — which calibrates how much
drift the alarm tolerates. **Production cadence:** monthly, score-level and top-15
features, against the frozen training reference.

## 3. Fairness / Disparate Impact

Adverse-impact ratio (AIR) = segment approval rate ÷ highest segment's approval rate,
at the production threshold (PD ≥ 0.07). Four-fifths screen: AIR < 0.80 flags review.

| Group | Approval rate ratio (AIR) | Four-fifths screen |
|---|---|---|
| Gender: F (reference) | 1.00 | — |
| Gender: M | **0.75** | **flagged** |
| Age 50+ (reference) | 1.00 | — |
| Age 35–50 | 0.83 | passes |
| Age 20–35 | **0.62** | **flagged** |

**Findings and disposition:**

1. **Gender — defect, fixed.** `CODE_GENDER` was a model input; prohibited basis
   regardless of accuracy. The champion was retrained without it: test AUROC 0.7731 vs
   0.7736 — the fix costs **0.0006 AUROC**, i.e. nothing.
   `credit_scoring_pipeline_nogender.pkl` is the deployment artifact. Residual
   gender-correlated pathways (occupation, family status) are covered by the quarterly
   re-audit below.
2. **Age — risk-justified, documented.** Younger applicants genuinely default more
   (12.3% for 20–25 vs 4.9% for 60+ in the raw data); the model's age effect is
   monotone and matches observed risk, and the *elderly are favored*, not disadvantaged
   — the configuration age-permitting frameworks (e.g. ECOA) allow. Business-necessity
   justification is recorded here; the AIR is monitored quarterly.
3. **Ongoing control:** quarterly fairness re-audit on the gender-free model — AIR by
   gender, age band, and family status; SHAP dependence checks on candidate proxy
   features; escalation to compliance if any AIR crosses 0.80 without a documented
   risk justification.

## 4. Monitoring Summary (operational)

| Monitor | Cadence | Trigger | Action |
|---|---|---|---|
| Score PSI vs frozen reference | Monthly | > 0.10 / > 0.25 | Monitor / investigate |
| Top-15 feature PSI | Monthly | > 0.25 any | Data-pipeline + population review |
| Decile calibration (observed vs predicted) | Quarterly | observed > 1.25× predicted, 2+ deciles | Recalibrate |
| Segment AUROC | Quarterly | any segment < overall − 0.05 | Segment review |
| AIR (gender, age, family status) | Quarterly | < 0.80 unjustified | Compliance escalation |
| Champion/challenger retrain | Monthly | challenger wins 2 consecutive months | Promote |

# Executive Summary: Credit Scoring Model

**Prepared by:** Kaustubh Patil
**Date:** 20 August 2026
**Audience:** Senior leadership, Head of Risk, Model Validation

---

## The Business Problem

Every approved loan is a bet that the applicant repays. On our book, 8.07% of them do
not — and each default costs roughly 13× what a wrongly-declined good customer costs
(65% of exposure lost vs a 5% lifetime margin foregone). The current process needs a
consistent, evidence-based way to price that bet at application time.

## What We Built

A machine-learning scoring model trained on **307,511 historical applications** enriched
with **1.7M credit-bureau records** from other lenders. The model reads 153 signals —
repayment history elsewhere, debt-service capacity, external scores, application
characteristics — and produces a calibrated probability of default for each applicant.
It was developed on 70% of the data, tuned on 15%, and judged once on a sealed 15%
test set of 46,127 applications it had never influenced.

## Key Results (sealed test set)

| Metric | Champion (Gradient Boosting) | Scorecard baseline (Logistic) |
|---|---|---|
| AUROC | **0.774** | 0.757 |
| Gini | **0.547** | 0.514 |
| KS statistic | **0.416** | 0.382 |
| Probabilities calibrated? | Yes — predicted ≈ observed by decile | Yes |

*Figure: `figures/mod_roc_curves.png` — the champion's ROC curve vs the scorecard.*

**In business terms:** ranked by model score, the riskiest 10% of applicants contain
roughly a third of all eventual defaults.

## The Dollar Case

At the profit-maximizing decline threshold (predicted PD ≥ 7%), on the 46,127-application
test book, with each applicant's actual requested credit as exposure:

| Outcome | Value |
|---|---|
| Approval rate | **63.2%** |
| Eventual defaults caught before approval | **2,773 — 74.5% of all defaults** |
| Prevented default losses | **$972.0M** |
| Profit foregone on 14,204 declined good customers | −$393.3M |
| **Net benefit vs approving everyone** | **+$578.7M** |

(Amounts in portfolio currency units; assumptions — 65% loss-given-default, 5% lifetime
margin — are stated in the model documentation and the threshold is a dial leadership
can move: the full approval-rate/benefit trade-off curve is `figures/mod_profit_curve.png`.)

## Risk Analysis — When the Model Fails

- **It cannot see shocks.** The model prices applicant risk under conditions like the
  training period; a macro downturn shifts everyone's risk in ways it will underestimate.
  Mitigation: PSI drift monitoring (demonstrated live on a simulated recession cohort —
  the alarm fires) plus monthly retraining.
- **Thin-file applicants are its weakest segment** — least history, widest uncertainty.
  Segment AUROC is monitored; a manual-review lane for thin files is recommended.
- **Compliance defect found and fixed:** the initial model used gender as an input. We
  retrained without it, verified the accuracy cost is negligible, and recommend the
  gender-free pipeline for deployment (details in the stability report).

## Recommendation — DEPLOY (the gender-free pipeline), with conditions

The model beats the scorecard baseline decisively, its probabilities are honest, the
dollar case is large and robust to the threshold choice, and the monitoring framework
is built and demonstrated. Conditions: (1) deploy the gender-free pipeline only;
(2) adverse-action reason codes (built, notebook 05) accompany every decline;
(3) monthly PSI monitoring with the thresholds in the model documentation;
(4) quarterly fairness re-audit including proxy pathways.

## Next Steps (If Given 4 More Weeks)

1. Add the remaining Home Credit relationship tables (previous applications,
   installments, credit-card balances) — the largest known accuracy headroom
2. Out-of-time validation once dated application cohorts are available
3. Reject-inference study to correct for the approved-only training population
4. Champion/challenger harness for the monthly retraining cycle

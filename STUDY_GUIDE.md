# Study Guide — Capstone 1: The Credit Scoring Project
### A complete plain-language walkthrough: what it is, how it was built, what we found, and what went wrong along the way

---

## 1. The big picture — what is this project?

Imagine you work at a bank. Every day, thousands of people apply for loans. Some of them will pay the money back. Some won't. **Your job is to guess — at the moment of application, before giving out any money — who is who.**

That guess is worth a lot. In our data, about **8 out of every 100 approved loans go bad**. When a loan goes bad, the bank loses about 65% of the money it lent. When the bank wrongly rejects a good customer, it only loses the small profit it would have made (~5% of the loan). So **a missed bad loan costs about 13 times more than a wrongly-rejected good one**. This asymmetry drives everything in the project.

We built a machine-learning model that reads a loan application (plus the applicant's history at other banks) and outputs a **probability of default** — a number like "this person has a 12% chance of not paying." Then we picked a cutoff: everyone above it gets declined. Finally, we calculated what the whole system is worth in money.

**The end result:** a model that catches 74.5% of bad loans before they're funded, while still approving 63% of applicants — worth about **$578 million in net benefit** on a test set of 46,127 applications, compared to just approving everyone.

---

## 2. The data — what did we work with?

Two files:

1. **`application_train.csv`** — 307,511 loan applications, 122 columns each. Things like: income, loan amount, monthly payment, age, job, education, family, housing, plus three mysterious "external scores" (credit scores from outside agencies — these turned out to be gold).
2. **`bureau.csv`** — 1.7 million records of these same people's *previous loans at other banks*. Did they pay on time? How much do they still owe? How many credit cards do they juggle?

Each application has a label: `TARGET = 1` means the person had serious payment trouble; `TARGET = 0` means they paid fine. The model learns from 307,511 past examples with known outcomes, so it can predict the outcome for new applicants.

**The "Five Cs of credit"** — the classic banker's checklist — gave us the map for which features matter:
- **Character** (did they repay others before?) → the bureau file
- **Capacity** (can they afford the payment?) → income vs. payment ratios
- **Capital** (what do they own?) → car, house flags
- **Collateral** (is the loan covered by what it buys?) → loan vs. purchase price
- **Conditions** (the environment) → external scores, region ratings

---

## 3. Notebook by notebook — what we did and why

### Notebook 01 — Exploration (looking before touching)

Before building anything, we studied the data. Four big discoveries:

**Discovery 1 — Default is rare, so "accuracy" is a trap.** A lazy model that approves *everyone* would be "92% accurate" (because 92% repay) and completely useless. So we banned accuracy as a metric and used **AUROC** instead — a score from 0.5 (coin flip) to 1.0 (perfect) that measures how well the model *ranks* risky people above safe people.

**Discovery 2 — The data lies.** The column "days employed" had a bizarre spike: 55,374 people (18% of everyone!) supposedly employed for **1,000 years**. That's a *sentinel value* — a fake number someone typed in to mean "not employed." Digging deeper: almost all these people are pensioners. And here's the twist — pensioners actually default *less* (5.4% vs 8.7%). If we'd left the fake number in, the model would have learned nonsense; if we'd deleted these rows, we'd have lost a genuinely useful signal. The fix: replace the fake number with "unknown" and add a simple yes/no flag "is not employed."

**Discovery 3 — What's *missing* is itself a clue.** About half the applicants have no building information, and many have no external score #1. People *missing* an external score default noticeably more often (makes sense — no score usually means little credit history). So instead of just filling holes, we kept little flags saying "this was missing."

**Discovery 4 — Who defaults?** Young people (12.3% for ages 20–25 vs 4.9% for 60+), people with past-due loans at other banks (about double the risk), and people with low external scores. One surprise: the classic **debt-to-income ratio was weak on its own** — because the payment amount in our data was already set by the bank's old underwriting, which had partially "flattened" the ratio. A good lesson: features can be secretly pre-filtered by the process that generated the data.

### Notebook 02 — Cleaning (fixing the lies, safely)

Three principles, applied strictly:

1. **Audit everything.** We wrote a scan that checks *every* numeric column for suspicious value-spikes like the 1,000-year employee. Result: that was the only one. But now the scan exists forever — any future data drop gets checked automatically.
2. **Split before you fit.** We cut the data 70% train / 15% validation / 15% test, keeping the 8.07% default rate identical in each piece ("stratified"). The test slice was **sealed** — never touched until the very end. Why? Because any decision influenced by the test data (even accidentally) makes the final score a lie.
3. **No leakage.** Every "learned" step — filling missing values with medians, encoding categories, scaling — must learn its numbers from the *training* data only. We even proved the point with a table: the median values differ slightly between splits, so using full-data medians would smuggle future information into the past. Our trick to make this bulletproof: put all these steps *inside* the model pipeline, so they automatically refit on the right data every time.

### Notebook 03 — Feature engineering (turning raw data into signals)

Raw columns are like ingredients; features are the cooked meal.

- **Ratios** (the Capacity story): payment ÷ income, loan ÷ income, loan ÷ purchase price, income per family member. Each one has a lending logic behind it.
- **Bureau aggregation** (the Character story): we squashed 1.7 million rows of "previous loans elsewhere" into 17 numbers per person — how many active loans, ever overdue?, how maxed-out are their credit lines, how old is their credit history. This is the "did they repay others?" evidence.
- **A reality check:** we scored every engineered feature *alone* as a mini-model. The external-score average alone hits AUROC 0.715 — nothing else comes close. Honest conclusion: the external scores are the backbone; everything else adds small increments on top.
- **Peer groups (unsupervised learning):** we let K-Means clustering group applicants into three financial "tribes" — with no knowledge of who defaulted. The riskiest tribe (thin credit files, ~31k people) defaults at 10.2% vs 7.5% for the safest. The cluster label became a feature, and the business got a segmentation it can name.

### Notebook 04 — Modeling (the competition)

Three models fought on identical inputs:

| Model | Plain-language description | Test AUROC |
|---|---|---|
| Logistic regression | The classic "scorecard" — adds up weighted points. Simple, interpretable. | 0.757 |
| Random Forest | Hundreds of decision trees voting. Handles curves and interactions. | ~0.758 |
| **Gradient Boosting (tuned)** | Trees built one after another, each fixing the previous ones' mistakes. The modern standard for table data. | **0.774** |

The boosting model won by 1.7 points — that's the value of *nonlinear interactions* (e.g., "high utilization matters much more when the external score is also low").

Key decisions, and their logic:

- **Tuning without cheating:** we tried 10 random settings of the boosting model's knobs, judged by 3-fold cross-validation *inside the training data only*. The validation and test sets never influenced the choice.
- **The overfit check:** the model scores 0.832 on its own training data but 0.773–0.774 everywhere else. That gap is memorization — normal for boosted trees. What matters: cross-validation (0.768), validation (0.773), and the sealed test (0.774) all *agree*. Three independent thermometers reading the same temperature = trust the reading.
- **No class weighting — a deliberate refusal.** A popular trick for rare-event problems is to over-weight the rare class. We refused, because it inflates the predicted probabilities, and we *need* those probabilities to be honest ("calibrated") for the money math and the decline explanations. We checked calibration decile by decile: when the model says 20%, about 20% actually default. 
- **The money slide:** we swept every possible decline cutoff and computed, at each one: prevented losses (bad loans declined × 65% loss) minus foregone profit (good loans declined × 5% margin). The curve peaks at **cutoff = 7% predicted risk**: approve 63%, catch 74.5% of defaults, net **+$578.7M** on the test book. Crucially, the cutoff is a *dial for leadership*, not a statistical constant — want a higher approval rate? Move the dial and read off the cost.

### Notebook 05 — Explainability, monitoring, and fairness (the regulator's questions)

A model this good still can't be deployed unless three questions have answers:

**"Why was I declined?"** — The law (consumer-protection rules like FCAC/ECOA) requires specific reasons for every decline. We used **SHAP** — a method that splits each individual prediction into per-feature contributions that add up exactly to the final score. Take the top 4 risk-increasing contributions, translate them through a phrase dictionary, and you get an automatic notice like:
> 1. Number of active credit obligations at other lenders
> 2. High utilization of existing credit lines
> 3. Requested credit high relative to purchase value
> 4. High payment burden on requested credit

**"How will you know when it breaks?"** — Models rot silently as the world changes. The standard tripwire is **PSI** (Population Stability Index) — a number measuring how much a distribution has drifted from a frozen reference (below 0.10 = fine, 0.10–0.25 = watch, above 0.25 = investigate). We tested the alarm both ways: on our identical-by-construction splits it reads ~0.000 (correctly silent), and on a simulated severe recession (incomes −25%, credit scores −20%) it reads **0.337 — alarm fires**. A monitoring plan you've actually test-fired beats one that's just a promise.

**"Is it fair?"** — Here we found a genuine defect: **gender was one of the model's inputs**, which is prohibited in credit decisions regardless of accuracy. We measured the damage (at our cutoff, men's approval rate was only 75% of women's; the four-fifths rule flags anything below 80%), then **retrained the identical model without gender**. The cost of the fix: **0.0006 AUROC — essentially nothing**. Ship the gender-free version. Age effects remained (young applicants approved less) — but that's *risk-justified* (young people genuinely default 2.5× more) and legally defensible, so it stays, documented and monitored.

---

## 4. The challenges — what actually went wrong (and how we fixed it)

These are worth remembering; they're the most instructive part.

1. **The 1,000-year employee.** The single biggest data trap. Left alone, it would have poisoned every model. Fix: NaN + a flag, plus a systematic audit for other sentinels (found none).
2. **The K-Means outlier hijack.** Our first clustering used standard scaling — and a handful of applicants with absurd incomes (117 *million* vs a typical 147k) dominated the math. Result: garbage "clusters" of 1–2 people showing fake 0% and 100% default rates. Fix: rank-based (quantile) normalization, which makes outliers ordinary. Lesson: **always look at cluster sizes** — a beautiful chart can hide a degenerate cluster.
3. **The DTI overstatement.** Our first write-up claimed debt-to-income was a strong monotone predictor. The data said: barely (7.1% → 8.8% across deciles). We rewrote the claim to match reality and explained *why* it was weak (the ratio was pre-flattened by old underwriting). Lesson: write conclusions *after* looking at numbers, not before.
4. **The recession alarm that didn't fire.** Our first simulated recession (incomes −15%) produced PSI 0.09 — *just below* the alarm line, contradicting our claim that "the alarm fires." We strengthened the scenario to a severe recession (−25%) → PSI 0.337, and kept the mild scenario in the text as a calibration point for how much drift the alarm tolerates. Lesson: test your claims literally.
5. **A raw feature name in a customer letter.** An adverse-action reason came out as "Risk factors related to BURO_ACTIVE_COUNT" — machine-speak leaking into a consumer notice. The same bug resurfaced twice more in the live demo script (`REGION_POPULATION_RELATIVE`, then `BURO_AMT_OVERDUE_SUM`), which forced the proper fix: all **279 model features** now map to consumer language, with a lawful generic phrase as the fallback instead of the column name. Lesson: the last inch of an explainability system is *language*, and spot-checking a few examples hides the gaps — enumerate every feature.
6. **The overfit gap needed honest words.** The train-vs-validation gap was ~6 AUROC points, not the "point or two" our draft predicted. We rewrote it: the gap is real memorization headroom; the *agreement* between CV, validation, and test is the evidence that matters.

---

## 5. What we found — the takeaways in one place

- **External credit scores dominate** — one averaged score alone gets you 80% of the way; the model's job is the last 20% of increments.
- **History with other lenders (Character) is the strongest evidence you can build yourself** — past delinquency roughly doubles risk.
- **Nonlinearity is worth ~1.7 AUROC points** over a linear scorecard on this data.
- **A model's value is set by the decision rule, not the AUROC** — the profit curve turned 0.774 into $578.7M, and the threshold is a business dial.
- **Honest probabilities beat inflated ones** — refusing class weighting is what made the money math and the explanations possible.
- **Fairness auditing is not optional decoration** — we found a prohibited input, priced its removal at ~zero, and shipped the clean version. That's the difference between a school project and a deployable model.
- **Final verdict: DEPLOY** — with conditions (gender-free pipeline, reasons on every decline, monthly PSI, quarterly fairness re-audit, manual review for thin files).

---

## 6. Mini-glossary (the words, in plain terms)

| Term | Plain meaning |
|---|---|
| **AUROC** | "If I pick one random defaulter and one random good customer, how often does the model rank the defaulter as riskier?" 0.5 = guessing, 1.0 = perfect. Ours: 0.774. |
| **Gini** | Just AUROC rescaled: 2×AUROC − 1. |
| **KS statistic** | The biggest gap between "% of bads caught" and "% of goods wrongly flagged" across all cutoffs. |
| **Calibration** | When the model says "20% risk," do ~20% actually default? Ours: yes. |
| **Stratified split** | Cutting data so each piece keeps the same 8% default rate. |
| **Leakage** | Any way information from validation/test sneaks into training. The cardinal sin; our pipelines make it structurally impossible. |
| **Sentinel value** | A fake number (like 365243 days) used to mean "missing/special." |
| **SHAP** | A method that fairly splits one prediction into per-feature contributions that sum exactly to the output. |
| **PSI** | A drift alarm: how different is today's population from the training population? |
| **Adverse action** | The legally required "here's why you were declined" notice. |
| **AIR / four-fifths rule** | Compare group approval rates; below 80% of the best group = potential discrimination flag. |
| **LGD** | Loss given default — the share of the loan lost when someone defaults (we assumed 65%). |

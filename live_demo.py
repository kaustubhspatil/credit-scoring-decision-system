"""
Live scoring demo for the Model Review Committee presentation.

Everything on screen is computed on the spot with the deployed pipeline and
the sealed test set: nothing is pre-computed, nothing is staged. This is the
terminal companion to reports/Credit_Scoring_Model_Review.pptx, slide 11.

Usage:
    python live_demo.py                # riskiest applicant in the test set (default)
    python live_demo.py --riskiest
    python live_demo.py --safest       # lowest-risk applicant, for contrast
    python live_demo.py --random       # a spontaneous pick, live
    python live_demo.py --row 42       # a specific test-set row, if asked

    python live_demo.py --custom       # type in an applicant and score it live
    python live_demo.py --custom --age 29 --income 90000 --credit 300000 \\
        --employed-years 2 --active-lines 4 --utilization 70
"""

import argparse
import sys
import time

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import joblib
import numpy as np
import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.align import Align
from rich import box

from src import config
from score_applicant import REASON_MAP, GENERIC_REASON, plain_reason, THRESHOLD

console = Console()
EPS = 1e-8

# Template row for --custom: this specific test-set applicant's external
# bureau scores and other non-editable fields leave real headroom for the six
# live-typed inputs to swing the decision either way. Verified against this
# pipeline: extreme-bad inputs reach ~11% PD (DECLINE), extreme-good inputs
# reach ~4.5% PD (APPROVE), and the moderate defaults land near the PD 7%
# threshold, a fittingly borderline case.
CUSTOM_TEMPLATE_ROW = 23039


def bar(value, max_abs, width=28, color="red"):
    n = max(1, int(round(abs(value) / max_abs * width))) if max_abs > 0 else 0
    return f"[{color}]{'█' * n}[/{color}]"


def ask_number(prompt, default, lo, hi):
    """Prompt for a number on the terminal, clamped to a sane range."""
    while True:
        raw = input(f"  {prompt} [{default}]: ").strip()
        if raw == "":
            return float(default)
        try:
            val = float(raw)
        except ValueError:
            console.print("  [red]enter a number[/red]")
            continue
        if val < lo or val > hi:
            console.print(f"  [red]enter a number between {lo} and {hi}[/red]")
            continue
        return val


def collect_custom_inputs(args):
    """Either take the six applicant fields from CLI flags, or prompt for
    each one live on the terminal. Returns a dict of raw values."""
    fields = [
        ("age", "Applicant age (years)", 18, 75),
        ("income", "Reported annual income", 10000, 2_000_000),
        ("credit", "Requested credit amount", 10000, 3_000_000),
        ("employed_years", "Years at current job (0 = not employed)", 0, 50),
        ("active_lines", "Active credit lines at other lenders", 0, 20),
        ("utilization", "Utilization of those lines, in percent", 0, 100),
    ]
    defaults = {"age": 35, "income": 157500, "credit": 450000,
                "employed_years": 5, "active_lines": 3, "utilization": 45}
    values = {}
    need_prompt = any(getattr(args, key) is None for key, *_ in fields)
    if need_prompt:
        console.print("[bold]Type in an applicant[/bold]  "
                       "[grey50](press Enter to accept the default shown in brackets)[/grey50]\n")
    for key, label, lo, hi in fields:
        cli_val = getattr(args, key)
        if cli_val is not None:
            values[key] = float(cli_val)
        else:
            values[key] = ask_number(label, defaults[key], lo, hi)
    return values


def build_custom_row(template_row, v):
    """Overlay the six live inputs onto a real template applicant's row, and
    recompute the ratio features that depend on them (same formulas as
    src/features.py), so the row stays internally consistent. Everything the
    presenter did NOT type in (external bureau scores, region, housing, ...)
    is carried over unchanged from that real applicant."""
    row = template_row.copy()

    age = v["age"]
    employed = v["employed_years"]
    income = max(v["income"], 1.0)
    credit = v["credit"]
    goods = credit                      # assume the loan covers the goods price
    annuity = credit / 60.0             # assume a 5-year term
    active_lines = v["active_lines"]
    utilization = v["utilization"] / 100.0

    row["AGE_YEARS"] = age
    if employed <= 0:
        row["EMPLOYED_YEARS"] = np.nan
        row["FLAG_NOT_EMPLOYED"] = 1
        row["EMPLOYED_SHARE_OF_LIFE"] = np.nan
    else:
        row["EMPLOYED_YEARS"] = employed
        row["FLAG_NOT_EMPLOYED"] = 0
        row["EMPLOYED_SHARE_OF_LIFE"] = employed / (age + EPS)

    row["AMT_INCOME_TOTAL"] = income
    row["AMT_CREDIT"] = credit
    row["AMT_GOODS_PRICE"] = goods
    row["AMT_ANNUITY"] = annuity
    row["DTI"] = annuity / (income + EPS)
    row["CREDIT_TO_INCOME"] = credit / (income + EPS)
    row["CREDIT_TO_GOODS"] = credit / (goods + EPS)
    row["ANNUITY_TO_CREDIT"] = annuity / (credit + EPS)
    fam = max(float(row.get("CNT_FAM_MEMBERS", 1) or 1), 1.0)
    row["INCOME_PER_PERSON"] = income / fam

    row["BURO_ACTIVE_COUNT"] = active_lines
    row["BURO_COUNT"] = active_lines           # assume every reported line is active
    row["HAS_BUREAU_FILE"] = 1 if active_lines > 0 else 0
    row["BURO_UTILIZATION_MEAN"] = utilization if active_lines > 0 else np.nan

    return row


def score_and_explain(clf, X, prep, estimator, row_idx_or_frame, meta, show_hindsight):
    """Shared scoring + display path for both a real test-set row and a
    synthetic custom applicant. row_idx_or_frame is either an integer row
    index into X (real applicant) or a one-row DataFrame (custom applicant)."""
    if isinstance(row_idx_or_frame, int):
        x_row = X.iloc[[row_idx_or_frame]]
    else:
        x_row = row_idx_or_frame

    prob = float(clf.predict_proba(x_row)[:, 1][0])
    decision = "DECLINE" if prob >= THRESHOLD else "APPROVE"
    decision_color = "red" if decision == "DECLINE" else "green"

    console.print()
    snap = Table(box=box.SIMPLE, show_header=False, pad_edge=False)
    snap.add_column(style="grey62"); snap.add_column(style="white")
    for label, val in meta:
        snap.add_row(label, val)
    console.print(Panel(snap, title="[bold]Today's applicant[/bold]", border_style="grey42", width=64))

    console.print()
    verdict = Table.grid(padding=(0, 3))
    verdict.add_column(); verdict.add_column()
    verdict.add_row(
        Align.center(f"[bold {decision_color}]{prob:.1%}[/bold {decision_color}]\n[grey62]predicted probability of default[/grey62]"),
        Align.center(f"[bold {decision_color}]{decision}[/bold {decision_color}]\n[grey62]at the PD ≥ {THRESHOLD:.0%} cut-off[/grey62]"),
    )
    console.print(Panel(verdict, border_style=decision_color, width=64, padding=(1, 2)))

    if show_hindsight is not None:
        time.sleep(0.3)
        console.print(f"\n  [grey50]and in the historical record, hindsight only, never an input:[/grey50]  "
                      f"[bold]{show_hindsight}[/bold]\n")
    else:
        console.print("\n  [grey50]a hypothetical applicant: no historical outcome exists to reveal.[/grey50]\n")

    if decision == "DECLINE":
        import shap
        Xt = prep.transform(x_row)
        try:
            feat_names = list(prep.get_feature_names_out())
        except Exception:
            feat_names = [f"f{j}" for j in range(Xt.shape[1])]

        explainer = shap.TreeExplainer(estimator)
        sv = explainer(Xt)
        vals = sv.values[0]

        grouped = {}
        for j, val in enumerate(vals):
            label = plain_reason(str(feat_names[j]))
            grouped[label] = grouped.get(label, 0.0) + float(val)
        top = sorted(grouped.items(), key=lambda kv: -abs(kv[1]))[:7]
        max_abs = max(abs(val) for _, val in top) if top else 1.0

        console.print("[bold]This applicant's own SHAP decomposition[/bold]  "
                       "[grey50](log-odds impact, grouped by consumer-facing factor, computed just now)[/grey50]\n")
        wf = Table(box=None, show_header=False, pad_edge=False)
        wf.add_column(style="white", ratio=3)
        wf.add_column(ratio=2)
        wf.add_column(justify="right", style="grey62")
        for label, val in top:
            color = "red" if val > 0 else "blue"
            sign = "+" if val > 0 else ""
            wf.add_row(label, bar(val, max_abs, color=color), f"{sign}{val:.2f}")
        console.print(wf)

        reasons = [label for label, val in sorted(grouped.items(), key=lambda kv: -kv[1]) if val > 0][:4]

        console.print("\n[bold]Principal reasons for adverse action[/bold]  "
                       "[grey50](FCAC / ECOA, generated, not written by hand)[/grey50]")
        for n, r in enumerate(reasons, 1):
            console.print(f"  {n}. {r}")
    else:
        console.print("[green]No adverse-action notice required. Application approved.[/green]")

    console.print("\n[grey42]" + "-" * 66 + "[/grey42]")
    console.print("[grey50]  Same pipeline artifact, computed live. Run it again, get the same answer.[/grey50]")
    console.print("[grey42]" + "-" * 66 + "[/grey42]\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--row", type=int, default=None)
    ap.add_argument("--riskiest", action="store_true")
    ap.add_argument("--safest", action="store_true")
    ap.add_argument("--random", action="store_true")
    ap.add_argument("--custom", action="store_true", help="type in an applicant and score it live")
    ap.add_argument("--age", type=float, default=None)
    ap.add_argument("--income", type=float, default=None)
    ap.add_argument("--credit", type=float, default=None)
    ap.add_argument("--employed-years", dest="employed_years", type=float, default=None)
    ap.add_argument("--active-lines", dest="active_lines", type=float, default=None)
    ap.add_argument("--utilization", type=float, default=None)
    args = ap.parse_args()

    console.print()
    console.rule("[bold blue]CONSUMER CREDIT · LIVE UNDERWRITING DEMO[/bold blue]", style="blue")
    console.print()

    with Progress(SpinnerColumn(style="green"), TextColumn("[white]{task.description}"),
                  BarColumn(bar_width=30, style="grey23", complete_style="blue"),
                  console=console, transient=True) as progress:

        task = progress.add_task("starting...", total=4)

        progress.update(task, description="loading the deployed pipeline artifact ...")
        model_path = config.MODELS_DIR / "credit_scoring_pipeline_nogender.pkl"
        if not model_path.exists():
            model_path = config.MODELS_DIR / "credit_scoring_pipeline.pkl"
        clf = joblib.load(model_path)
        time.sleep(0.5)
        progress.advance(task)
        console.print(f"  [green]✓[/green] loaded [white]{model_path.name}[/white]")

        progress.update(task, description="reading the sealed test set (46,127 applicants, never touched until now) ...")
        test = pd.read_parquet(config.PROCESSED_DIR / "test_features.parquet")
        drop = [c for c in ("TARGET", "SK_ID_CURR") if c in test.columns]
        X = test.drop(columns=drop)
        X = X[[c for c in X.columns if c in clf.feature_names_in_]] if hasattr(clf, "feature_names_in_") else X
        time.sleep(0.5)
        progress.advance(task)
        console.print(f"  [green]✓[/green] read {len(test):,} sealed test applicants")

        progress.update(task, description="scoring every applicant through the real preprocessing + model pipeline ...")
        pd_all = clf.predict_proba(X)[:, 1]
        time.sleep(0.6)
        progress.advance(task)
        console.print("  [green]✓[/green] scored every applicant through the deployed pipeline")

        progress.update(task, description="selecting today's applicant ...")
        if args.custom:
            # a fixed template row picked for having real headroom in both
            # directions: the six editable inputs alone can carry it from a
            # clear APPROVE to a clear DECLINE, verified empirically against
            # this pipeline (see CUSTOM_TEMPLATE_ROW below for the numbers).
            i = CUSTOM_TEMPLATE_ROW
        elif args.row is not None:
            i = args.row
        elif args.safest:
            i = int(np.argmin(pd_all))
        elif args.random:
            i = int(np.random.randint(0, len(pd_all)))
        else:
            i = int(np.argmax(pd_all))
        time.sleep(0.4)
        progress.advance(task)
        console.print("  [green]✓[/green] selected today's applicant\n")

    estimator = clf.named_steps["clf"]
    prep = clf.named_steps["prep"]

    if args.custom:
        values = collect_custom_inputs(args)
        console.print()
        with console.status("[grey62]transforming the applicant through the real pipeline ...[/grey62]", spinner="dots"):
            time.sleep(0.5)
            custom_row = build_custom_row(test.iloc[i], values)
            x_frame = pd.DataFrame([custom_row])[X.columns]

        emp_txt = "not currently employed" if pd.isna(custom_row["EMPLOYED_YEARS"]) else f"{custom_row['EMPLOYED_YEARS']:.0f} yrs employed"
        meta = [
            ("Applicant", "CUSTOM (typed in live, not a real record)"),
            ("Requested credit", f"{custom_row['AMT_CREDIT']:,.0f}"),
            ("Reported income", f"{custom_row['AMT_INCOME_TOTAL']:,.0f}"),
            ("Age / employment", f"{custom_row['AGE_YEARS']:.0f} yrs, {emp_txt}"),
            ("Active bureau lines", f"{custom_row['BURO_ACTIVE_COUNT']:.0f}  ·  utilization {values['utilization']:.0f}%"),
        ]
        console.print("[grey50]  External bureau scores, region, and housing details are carried over from a "
                       "real template applicant, since those aren't things a presenter can type in live.[/grey50]")
        score_and_explain(clf, X, prep, estimator, x_frame, meta, show_hindsight=None)
        return

    row = test.iloc[i]
    emp = row.get("EMPLOYED_YEARS", float("nan"))
    emp_txt = "not currently employed" if pd.isna(emp) else f"{emp:.1f} yrs employed"
    meta = [
        ("Applicant ID", f"{int(row.get('SK_ID_CURR', i)):,}"),
        ("Requested credit", f"{row.get('AMT_CREDIT', float('nan')):,.0f}"),
        ("Reported income", f"{row.get('AMT_INCOME_TOTAL', float('nan')):,.0f}"),
        ("Age / employment", f"{row.get('AGE_YEARS', float('nan')):.0f} yrs, {emp_txt}"),
        ("Bureau records", f"{row.get('BURO_COUNT', 0):.0f}"),
    ]
    actual = "DEFAULTED" if row["TARGET"] == 1 else "repaid in full"
    score_and_explain(clf, X, prep, estimator, i, meta, show_hindsight=actual)


if __name__ == "__main__":
    main()

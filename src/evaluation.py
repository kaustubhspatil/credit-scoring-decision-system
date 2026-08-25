"""Credit-model evaluation: discrimination, calibration, stability, dollars."""

import numpy as np
import pandas as pd
from sklearn.metrics import (average_precision_score, brier_score_loss,
                             roc_auc_score, roc_curve)


def credit_metrics(y_true, y_prob):
    """The metrics a validation team asks for first."""
    auroc = roc_auc_score(y_true, y_prob)
    fpr, tpr, _ = roc_curve(y_true, y_prob)
    return {
        "auroc": float(auroc),
        "gini": float(2 * auroc - 1),
        "ks": float(np.max(tpr - fpr)),
        "pr_auc": float(average_precision_score(y_true, y_prob)),
        "brier": float(brier_score_loss(y_true, y_prob)),
        "default_rate": float(np.mean(y_true)),
    }


def decile_table(y_true, y_prob, n=10):
    """
    Rank applicants by predicted risk, split into deciles, and compare
    predicted vs observed default rates - the standard calibration exhibit.
    """
    df = pd.DataFrame({"y": y_true, "p": y_prob})
    df["decile"] = pd.qcut(df["p"].rank(method="first"), n, labels=False)
    out = df.groupby("decile").agg(
        applicants=("y", "size"),
        predicted_rate=("p", "mean"),
        observed_rate=("y", "mean"),
        defaults=("y", "sum"),
    )
    out["cum_default_share"] = out["defaults"][::-1].cumsum()[::-1] / out["defaults"].sum()
    return out


def psi(expected, actual, bins=10):
    """
    Population Stability Index between two samples of one feature/score.
    Rule of thumb: < 0.10 stable, 0.10-0.25 monitor, > 0.25 shifted.
    """
    expected = pd.Series(expected).dropna()
    actual = pd.Series(actual).dropna()
    edges = np.unique(np.percentile(expected, np.linspace(0, 100, bins + 1)))
    if len(edges) < 3:   # near-constant feature
        return 0.0
    e = np.histogram(expected, bins=edges)[0] / len(expected)
    a = np.histogram(actual, bins=edges)[0] / len(actual)
    e, a = np.clip(e, 1e-6, None), np.clip(a, 1e-6, None)
    return float(np.sum((a - e) * np.log(a / e)))


def profit_curve(y_true, y_prob, exposure, lgd, profit_rate, grid=None):
    """
    Expected portfolio profit as a function of the decline threshold.

    For each threshold t: decline everyone with predicted risk >= t.
      - Declining a bad applicant SAVES exposure * lgd
      - Declining a good applicant COSTS exposure * profit_rate
    Returns a DataFrame over the threshold grid with approval rate,
    prevented losses, lost revenue, and net benefit vs approving everyone.
    """
    grid = grid if grid is not None else np.round(np.arange(0.02, 0.60, 0.01), 3)
    df = pd.DataFrame({"y": np.asarray(y_true), "p": np.asarray(y_prob),
                       "exp": np.asarray(exposure, dtype=float)})
    rows = []
    for t in grid:
        declined = df["p"] >= t
        prevented = (df.loc[declined & (df["y"] == 1), "exp"] * lgd).sum()
        lost = (df.loc[declined & (df["y"] == 0), "exp"] * profit_rate).sum()
        rows.append({
            "threshold": t,
            "approval_rate": float(1 - declined.mean()),
            "decline_rate": float(declined.mean()),
            "defaults_caught": int(df.loc[declined, "y"].sum()),
            "default_recall": float(df.loc[declined, "y"].sum() / max(df["y"].sum(), 1)),
            "good_declined": int((declined & (df["y"] == 0)).sum()),
            "prevented_losses": float(prevented),
            "lost_revenue": float(lost),
            "net_benefit": float(prevented - lost),
        })
    return pd.DataFrame(rows)

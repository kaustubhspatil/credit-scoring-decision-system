"""Project-wide configuration: paths, seed, splits, business assumptions."""

from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = ROOT / "models"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

SEED = 42

# ── Splits ───────────────────────────────────────────────────────────────
# The dataset has no application dates, so a temporal split is impossible.
# We use a stratified 70/15/15 split (train / validation / test) and treat
# the test set as sealed until final evaluation. Stability over "time" is
# approximated by PSI between the splits and by segment analysis.
VAL_FRACTION = 0.15
TEST_FRACTION = 0.15

# ── Business assumptions (used to convert model quality into dollars) ────
# Stated explicitly so a reviewer can challenge each one. Amounts are in the
# dataset's (anonymized) currency units; we report them as dollars.
LGD = 0.65                  # loss given default: share of exposure lost when a loan defaults
PROFIT_RATE = 0.05          # lifetime profit on a good loan, as a share of credit amount
# Average exposure and profit are computed from the data itself in notebook 04.


def set_seed(seed: int = SEED):
    import random

    import numpy as np

    random.seed(seed)
    np.random.seed(seed)

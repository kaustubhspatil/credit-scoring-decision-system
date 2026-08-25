"""
The project's visual identity.

Every chart in the capstone goes through this module so the whole submission
reads as one system: a validated categorical palette (colorblind-safe in the
order given - never cycle it), one sequential hue for magnitude, a blue<->red
diverging pair for polarity, and reserved status colors for good/bad states.

Rules baked in here (do not fight them in the notebooks):
  - categorical hues are assigned in SLOT ORDER, never cycled or shuffled
  - one axis per chart - two measures of different scale get two panels
  - text wears ink colors, never a series color
  - grids are hairline and recessive; spines are mostly gone
"""

import matplotlib as mpl
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

# ── Ink & surfaces (light mode - notebooks and PDF reports) ──────────────
SURFACE = "#fcfcfb"     # chart surface
PAGE = "#f9f9f7"        # page plane
INK = "#0b0b0b"         # primary text
INK_2 = "#52514e"       # secondary text
MUTED = "#898781"       # axis labels, ticks
GRID = "#e1e0d9"        # hairline gridlines
BASELINE = "#c3c2b7"    # axis baseline

# ── Categorical palette (validated order - assign by slot, never cycle) ──
BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
YELLOW = "#eda100"
MAGENTA = "#e87ba4"
GREEN = "#008300"
VIOLET = "#4a3aa7"
RED = "#e34948"
SERIES = [BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED]

# ── Status colors (reserved for state, never used as "series 4") ─────────
GOOD = "#0ca30c"
WARNING = "#fab219"
SERIOUS = "#ec835a"
CRITICAL = "#d03b3b"

# ── Sequential (one hue, light->dark) and diverging (blue<->red) ─────────
_BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
CMAP_SEQ = LinearSegmentedColormap.from_list("jarvis_blues", _BLUE_RAMP)
CMAP_DIV = LinearSegmentedColormap.from_list(
    "jarvis_div", ["#0d366b", "#3987e5", "#cde2fb", "#f0efec", "#f6c4c4", "#e34948", "#8f1d1d"]
)


def apply_style():
    """Set the global matplotlib style for the whole project."""
    mpl.rcParams.update({
        "figure.facecolor": SURFACE,
        "figure.dpi": 110,
        "figure.figsize": (11, 5),
        "savefig.facecolor": SURFACE,
        "savefig.bbox": "tight",
        "savefig.dpi": 150,
        "axes.facecolor": SURFACE,
        "axes.edgecolor": BASELINE,
        "axes.linewidth": 0.8,
        "axes.grid": True,
        "axes.axisbelow": True,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlecolor": INK,
        "axes.titlelocation": "left",
        "axes.titlepad": 12,
        "axes.labelsize": 10,
        "axes.labelcolor": INK_2,
        "axes.prop_cycle": mpl.cycler(color=SERIES),
        "grid.color": GRID,
        "grid.linewidth": 0.7,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "lines.linewidth": 1.8,
        "lines.solid_capstyle": "round",
        "legend.frameon": False,
        "legend.fontsize": 9,
        "legend.labelcolor": INK_2,
        "font.family": "sans-serif",
        "font.sans-serif": ["Segoe UI", "Arial", "DejaVu Sans"],
        "text.color": INK,
    })


def subtitle(ax, text, y=1.02):
    """Secondary-ink subtitle under a bold title (title is left-aligned)."""
    ax.set_title(ax.get_title(loc="left"), pad=26)  # lift the title clear of the subtitle
    ax.text(0, y, text, transform=ax.transAxes, fontsize=9.5,
            color=INK_2, va="bottom", ha="left")


def direct_label(ax, x, y, text, color, dx=6, fontsize=9, weight="bold"):
    """Label a line at its endpoint instead of relying on a legend lookup."""
    ax.annotate(text, xy=(x, y), xytext=(dx, 0), textcoords="offset points",
                fontsize=fontsize, color=color, fontweight=weight, va="center")


def fmt_pct(ax, axis="y", decimals=0):
    """Format an axis as percentages."""
    which = ax.yaxis if axis == "y" else ax.xaxis
    which.set_major_formatter(mpl.ticker.PercentFormatter(xmax=1, decimals=decimals))


def fmt_dollars(ax, axis="y"):
    """Format an axis as $ with thousands separators (compact for millions)."""
    def _fmt(v, _):
        if abs(v) >= 1e6:
            return f"${v / 1e6:,.1f}M"
        if abs(v) >= 1e3:
            return f"${v / 1e3:,.0f}K"
        return f"${v:,.0f}"
    which = ax.yaxis if axis == "y" else ax.xaxis
    which.set_major_formatter(mpl.ticker.FuncFormatter(_fmt))


def year_axis(ax):
    """Clean year ticks for multi-year time series."""
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))


def save_figure(fig, name, figures_dir=None):
    """Save a figure into reports/figures/ and return the path."""
    from . import config

    out_dir = figures_dir or config.FIGURES_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.png"
    fig.savefig(path)
    return path


# ── Composite charts used across notebooks ───────────────────────────────

def plot_equity_with_drawdown(equity, benchmark=None, title="Equity curve",
                              strategy_label="Strategy", benchmark_label="Buy & hold SPY"):
    """
    The capstone's signature figure: portfolio value on top, drawdown below.
    `equity` and `benchmark` are pd.Series of portfolio dollar value indexed by date.
    """
    fig, (ax, axd) = plt.subplots(
        2, 1, figsize=(11, 6.5), sharex=True,
        gridspec_kw={"height_ratios": [3, 1], "hspace": 0.08},
    )

    ax.plot(equity.index, equity.values, color=BLUE, lw=2, zorder=3)
    direct_label(ax, equity.index[-1], equity.iloc[-1], strategy_label, BLUE)
    if benchmark is not None:
        ax.plot(benchmark.index, benchmark.values, color=MUTED, lw=1.4,
                ls=(0, (4, 2)), zorder=2)
        direct_label(ax, benchmark.index[-1], benchmark.iloc[-1],
                     benchmark_label, MUTED, weight="normal")
    ax.set_title(title)
    fmt_dollars(ax)
    ax.margins(x=0.01)

    dd = equity / equity.cummax() - 1.0
    axd.fill_between(dd.index, dd.values, 0, color=CRITICAL, alpha=0.35, lw=0)
    axd.plot(dd.index, dd.values, color=CRITICAL, lw=1)
    axd.set_ylabel("Drawdown", fontsize=9)
    fmt_pct(axd)
    axd.margins(x=0.01)

    trough = dd.idxmin()
    axd.annotate(f"{dd.min():.0%}", xy=(trough, dd.min()),
                 xytext=(8, -2), textcoords="offset points",
                 fontsize=9, color=CRITICAL, fontweight="bold", va="top")
    return fig, (ax, axd)


def plot_monthly_heatmap(monthly_returns, title="Monthly returns", ax=None, vmax=None):
    """
    Year x month heatmap of returns. `monthly_returns` is a pd.Series indexed
    by month-end dates. Diverging color: red = down, blue = up, gray = flat.
    """
    df = monthly_returns.to_frame("ret")
    df["year"] = df.index.year
    df["month"] = df.index.month
    grid = df.pivot_table(index="year", columns="month", values="ret")

    if ax is None:
        _, ax = plt.subplots(figsize=(11, 0.42 * len(grid) + 1.4))
    lim = vmax or np.nanmax(np.abs(grid.values))
    im = ax.imshow(grid.values, cmap=CMAP_DIV.reversed(), vmin=-lim, vmax=lim, aspect="auto")

    ax.set_xticks(range(12))
    ax.set_xticklabels(["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
    ax.set_yticks(range(len(grid)))
    ax.set_yticklabels(grid.index)
    ax.set_title(title)
    ax.grid(False)

    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            v = grid.values[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v * 100:+.1f}", ha="center", va="center",
                        fontsize=7.5, color=INK if abs(v) < lim * 0.6 else "white")
    return ax.figure, ax

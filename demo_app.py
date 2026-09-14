"""
JARVIS Underwriting Desk: the live decisioning platform for Stark Financial.

A local web app that scores a real applicant with the real trained pipeline,
prices the decision in money, explains it with SHAP, writes it up in plain
English, and records it to a session audit trail.

The governance architecture, which is the point of the whole thing:

    the MODEL decides          real trained pipeline, deterministic
    SHAP explains              exact, additive, auditable
    the LLM only narrates      never changes a decision, and is optional

AI narration goes through OpenRouter. Set a key and it writes the paragraph;
omit the key, lose the network, or hit a provider error and it silently falls
back to a deterministic template. The decision, the money, the reason codes
and the audit record are byte-identical either way, so the demo cannot break
in front of an audience.

Configuration (all optional):
    api_key.txt          paste an OpenRouter key on the first non-comment line
    OPENROUTER_API_KEY   same thing via the environment, takes priority
    OPENROUTER_MODEL     defaults to anthropic/claude-sonnet-4.5

Without a key the app uses its own deterministic wording and behaves
identically: same decision, same money, same reason codes.

Run:
    python demo_app.py       ->  http://127.0.0.1:5000
"""

import os
import sys
import json
import time
import uuid
import datetime as dt

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import joblib
import numpy as np
import pandas as pd
import requests
from flask import Flask, request, jsonify, Response

from src import config
from score_applicant import plain_reason, THRESHOLD
from live_demo import build_custom_row, CUSTOM_TEMPLATE_ROW

LGD = config.LGD                        # 0.65 share of exposure lost on default
MARGIN = config.PROFIT_RATE             # 0.05 lifetime profit on a good loan
BREAK_EVEN = MARGIN / (MARGIN + LGD)    # 7.14%: where a loan stops making money

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5")
HTTP_TIMEOUT = 12  # seconds: bounded so a bad network cannot stall the demo

app = Flask(__name__)
STATE = {}
AUDIT = []          # in-memory session audit trail, newest first


# ------------------------------------------------------------------ startup --
def boot():
    t0 = time.time()
    model_path = config.MODELS_DIR / "credit_scoring_pipeline_nogender.pkl"
    if not model_path.exists():
        model_path = config.MODELS_DIR / "credit_scoring_pipeline.pkl"
    clf = joblib.load(model_path)

    test = pd.read_parquet(config.PROCESSED_DIR / "test_features.parquet")
    drop = [c for c in ("TARGET", "SK_ID_CURR") if c in test.columns]
    X = test.drop(columns=drop)
    if hasattr(clf, "feature_names_in_"):
        X = X[[c for c in X.columns if c in clf.feature_names_in_]]

    import shap
    prep, estimator = clf.named_steps["prep"], clf.named_steps["clf"]
    try:
        feat_names = list(prep.get_feature_names_out())
    except Exception:
        feat_names = None

    # score the whole sealed book once: this powers the live threshold dial and
    # the drift baseline without re-running the model on every request
    pd_all = clf.predict_proba(X)[:, 1]
    exposure = test["AMT_CREDIT"].to_numpy(dtype=float)
    target = test["TARGET"].to_numpy(dtype=int)

    STATE.update(clf=clf, X=X, prep=prep, estimator=estimator, test=test,
                 template=test.iloc[CUSTOM_TEMPLATE_ROW], feat_names=feat_names,
                 explainer=shap.TreeExplainer(estimator), model_name=model_path.name,
                 n_test=len(test), n_features=len(X.columns),
                 pd_all=pd_all, exposure=exposure, target=target,
                 ref_edges=np.quantile(pd_all, np.linspace(0, 1, 11))[1:-1],
                 booted=dt.datetime.now().strftime("%Y-%m-%d %H:%M"))
    print(f"  pipeline {model_path.name} loaded, {len(test):,} sealed test rows scored, "
          f"{time.time() - t0:.1f}s")


def portfolio_at(threshold):
    """Replay the real profit curve at any threshold, on the sealed test book.
    This is the same arithmetic that produced the +$578.7M headline."""
    pd_all, exp, tgt = STATE["pd_all"], STATE["exposure"], STATE["target"]
    declined = pd_all >= threshold
    approved = ~declined
    prevented = float((exp[declined & (tgt == 1)]).sum() * LGD)
    foregone = float((exp[declined & (tgt == 0)]).sum() * MARGIN)
    defaults_total = int((tgt == 1).sum())
    caught = int((declined & (tgt == 1)).sum())
    return {
        "threshold": threshold,
        "approval_rate": float(approved.mean()),
        "defaults_caught": caught,
        "defaults_total": defaults_total,
        "recall": caught / defaults_total if defaults_total else 0.0,
        "prevented_losses": prevented,
        "foregone_margin": foregone,
        "net_benefit": prevented - foregone,
        "approved_exposure": float(exp[approved].sum()),
    }


def psi(reference, current, edges):
    """Population Stability Index between two score distributions."""
    ref = np.clip(np.histogram(reference, bins=np.concatenate(([-np.inf], edges, [np.inf])))[0]
                  / len(reference), 1e-6, None)
    cur = np.clip(np.histogram(current, bins=np.concatenate(([-np.inf], edges, [np.inf])))[0]
                  / len(current), 1e-6, None)
    return float(np.sum((cur - ref) * np.log(cur / ref)))


def stressed_scores(income_shock, score_shock):
    """Apply a macro shock to the book and re-score it, exactly as the
    recession simulation in notebook 05 does."""
    t = STATE["test"].copy()
    if income_shock:
        t["AMT_INCOME_TOTAL"] = t["AMT_INCOME_TOTAL"] * (1 - income_shock / 100.0)
    if score_shock:
        for c in ("EXT_SOURCE_1", "EXT_SOURCE_2", "EXT_SOURCE_3"):
            if c in t.columns:
                t[c] = t[c] * (1 - score_shock / 100.0)
        ext = t[[c for c in ("EXT_SOURCE_1", "EXT_SOURCE_2", "EXT_SOURCE_3") if c in t.columns]]
        if "EXT_SOURCE_MEAN" in t.columns:
            t["EXT_SOURCE_MEAN"] = ext.mean(axis=1)
        if "EXT_SOURCE_MIN" in t.columns:
            t["EXT_SOURCE_MIN"] = ext.min(axis=1)
    # income drives the capacity ratios, so they move with it
    inc = t["AMT_INCOME_TOTAL"].clip(lower=1)
    if "DTI" in t.columns:
        t["DTI"] = t["AMT_ANNUITY"] / (inc + 1e-8)
    if "CREDIT_TO_INCOME" in t.columns:
        t["CREDIT_TO_INCOME"] = t["AMT_CREDIT"] / (inc + 1e-8)
    if "INCOME_PER_PERSON" in t.columns and "CNT_FAM_MEMBERS" in t.columns:
        t["INCOME_PER_PERSON"] = inc / t["CNT_FAM_MEMBERS"].fillna(1).clip(lower=1)
    Xs = t[STATE["X"].columns]
    return STATE["clf"].predict_proba(Xs)[:, 1]


# -------------------------------------------------------------------- keys --
def get_api_key():
    """OPENROUTER_API_KEY if set, otherwise the first real line of api_key.txt.
    The value is never printed, logged, or sent to the browser: the UI is told
    only whether a narrator is live, never where the key came from."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key.strip(), "environment"
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_key.txt")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    v = line.strip()
                    if not v or v.startswith("#"):
                        continue
                    if "=" in v and v.split("=", 1)[0].strip().upper().endswith("KEY"):
                        v = v.split("=", 1)[1].strip()
                    v = v.strip("'\"").strip()
                    if v and not v.startswith("PASTE_"):
                        return v, "api_key.txt"
        except Exception:
            pass
    return None, None


# ------------------------------------------------------------------ scoring --
def score(values):
    row = build_custom_row(STATE["template"], values)
    frame = pd.DataFrame([row])[STATE["X"].columns]
    prob = float(STATE["clf"].predict_proba(frame)[:, 1][0])
    decision = "DECLINE" if prob >= THRESHOLD else "APPROVE"

    exposure = float(values["credit"])
    expected_loss = prob * LGD * exposure
    expected_margin = (1 - prob) * MARGIN * exposure

    sv = STATE["explainer"](STATE["prep"].transform(frame))
    vals = sv.values[0]
    names = STATE["feat_names"] or [f"f{j}" for j in range(len(vals))]
    grouped = {}
    for j, v in enumerate(vals):
        lab = plain_reason(str(names[j]))
        grouped[lab] = grouped.get(lab, 0.0) + float(v)

    ranked = sorted(grouped.items(), key=lambda kv: -abs(kv[1]))[:6]
    factors = [{"label": k, "value": round(v, 3),
                "direction": "increases" if v > 0 else "decreases"} for k, v in ranked]
    reasons = [k for k, v in sorted(grouped.items(), key=lambda kv: -kv[1]) if v > 0][:4]

    return {
        "ref": f"SF-{dt.datetime.now():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}",
        "timestamp": dt.datetime.now().strftime("%d %b %Y, %H:%M:%S"),
        "pd": prob, "decision": decision, "threshold": THRESHOLD,
        "break_even": BREAK_EVEN,
        "money": {"exposure": exposure, "expected_loss": expected_loss,
                  "expected_margin": expected_margin,
                  "expected_value": expected_margin - expected_loss},
        "factors": factors, "reasons": reasons, "inputs": values,
        "model": STATE["model_name"],
    }


# ---------------------------------------------------------------- narration --
NARRATOR_SYSTEM = (
    "You write the plain-English summary in a consumer credit decision report for a "
    "bank's model review committee. The audience is mostly business people, a few are "
    "technical. Rules: use ONLY the figures given to you, never invent or recompute a "
    "number, never contradict or second-guess the decision you are given, and never "
    "imply the AI made the decision. Write exactly three short sentences: (1) the "
    "decision and what the probability means in plain words, (2) what it means in money "
    "for this specific loan, (3) the main reasons in everyday language. No jargon, no "
    "bullet points, no preamble, no markdown."
)


def template_narrative(r):
    """Deterministic. No AI, no network, cannot fail."""
    v = r["money"]["expected_value"]
    side = "above" if r["pd"] >= r["threshold"] else "below"
    ev = (f"a net expected gain of ${v:,.0f}" if v >= 0
          else f"a net expected loss of ${abs(v):,.0f}")
    why = ("The largest factors raising this file's risk are "
           + ", ".join(r["reasons"][:3]) + ".") if r["reasons"] else \
          "No single factor pushes this file materially above the book average."
    return (f"This application scores a {r['pd']:.1%} chance of default, {side} the "
            f"{r['threshold']:.0%} cut-off, so the recommendation is to "
            f"{r['decision'].lower()}. At a ${r['money']['exposure']:,.0f} exposure that is "
            f"${r['money']['expected_loss']:,.0f} of expected loss against "
            f"${r['money']['expected_margin']:,.0f} of expected margin, {ev}. {why}")


def looks_complete(t):
    """A truncated fragment reads as a broken report: reject it."""
    t = (t or "").strip()
    return len(t) >= 80 and t[-1] in ".!?" and t.count(" ") >= 12


def ai_narrative(r):
    key, _src = get_api_key()
    if not key:
        return template_narrative(r), "deterministic template (no narrator configured)"
    facts = {
        "probability_of_default": f"{r['pd']:.2%}",
        "decision": r["decision"], "cutoff": f"{r['threshold']:.0%}",
        "exposure": f"${r['money']['exposure']:,.0f}",
        "expected_loss": f"${r['money']['expected_loss']:,.0f}",
        "expected_margin": f"${r['money']['expected_margin']:,.0f}",
        "expected_value": f"${r['money']['expected_value']:,.0f}",
        "top_risk_factors": r["reasons"],
    }
    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json",
                     "HTTP-Referer": "http://127.0.0.1:5000",
                     "X-Title": "JARVIS Underwriting Desk"},
            json={"model": DEFAULT_MODEL, "max_tokens": 400, "temperature": 0.2,
                  "messages": [{"role": "system", "content": NARRATOR_SYSTEM},
                               {"role": "user", "content": json.dumps(facts, indent=2)}]},
            timeout=HTTP_TIMEOUT)
        if resp.status_code != 200:
            detail = ""
            try:
                detail = (resp.json().get("error") or {}).get("message", "")
            except Exception:
                detail = resp.text[:150]
            return template_narrative(r), f"template (OpenRouter {resp.status_code}: {detail[:120]})"
        text = (resp.json()["choices"][0]["message"]["content"] or "").strip()
        if not looks_complete(text):
            return template_narrative(r), "template (model reply was truncated)"
        return text, f"written live by {DEFAULT_MODEL} via OpenRouter"
    except requests.Timeout:
        return template_narrative(r), f"template (OpenRouter timed out after {HTTP_TIMEOUT}s)"
    except Exception as e:
        return template_narrative(r), f"template ({type(e).__name__})"


# -------------------------------------------------------------------- routes --
@app.post("/api/score")
def api_score():
    b = request.get_json(force=True)
    values = {k: float(b.get(k, d)) for k, d in
              (("age", 35), ("income", 157500), ("credit", 450000),
               ("employed_years", 5), ("active_lines", 3), ("utilization", 45))}
    r = score(values)
    r["narrative"], r["narrative_source"] = ai_narrative(r)
    AUDIT.insert(0, {"ref": r["ref"], "timestamp": r["timestamp"], "pd": r["pd"],
                     "decision": r["decision"],
                     "exposure": r["money"]["exposure"],
                     "ev": r["money"]["expected_value"]})
    del AUDIT[40:]
    r["audit"] = AUDIT
    return jsonify(r)


@app.get("/api/portfolio")
def api_portfolio():
    """Live threshold dial: the real profit curve, recomputed on demand."""
    th = float(request.args.get("threshold", THRESHOLD))
    th = min(max(th, 0.01), 0.60)
    curve = [{"t": round(t, 3), "net": portfolio_at(t)["net_benefit"]}
             for t in np.arange(0.01, 0.601, 0.01)]
    best = max(curve, key=lambda p: p["net"])
    return jsonify({"at": portfolio_at(th), "curve": curve,
                    "optimum": best, "baseline": portfolio_at(THRESHOLD)})


@app.get("/api/drift")
def api_drift():
    """Drift monitor. income_shock / score_shock are percentages."""
    inc = float(request.args.get("income_shock", 0))
    sc = float(request.args.get("score_shock", 0))
    t0 = time.time()
    cur = STATE["pd_all"] if (inc == 0 and sc == 0) else stressed_scores(inc, sc)
    value = psi(STATE["pd_all"], cur, STATE["ref_edges"])
    band = ("stable" if value < 0.10 else "monitor" if value < 0.25 else "investigate")
    base = portfolio_at(THRESHOLD)
    shocked_decline = float((cur >= THRESHOLD).mean())
    return jsonify({
        "psi": value, "band": band,
        "income_shock": inc, "score_shock": sc,
        "mean_pd_before": float(STATE["pd_all"].mean()),
        "mean_pd_after": float(cur.mean()),
        "decline_before": 1 - base["approval_rate"],
        "decline_after": shocked_decline,
        "elapsed": round(time.time() - t0, 2),
        "thresholds": {"stable": 0.10, "investigate": 0.25},
    })


@app.get("/api/status")
def api_status():
    key, src = get_api_key()
    return jsonify({"model": STATE["model_name"], "n_test": STATE["n_test"],
                    "n_features": STATE["n_features"], "booted": STATE["booted"],
                    "threshold": THRESHOLD, "break_even": BREAK_EVEN,
                    "lgd": LGD, "margin": MARGIN,
                    "narrator": (f"{DEFAULT_MODEL} via OpenRouter" if key
                                 else "deterministic template"),
                    "narrator_live": bool(key), "decisions": len(AUDIT)})


@app.get("/")
def index():
    return Response(PAGE, mimetype="text/html")


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>JARVIS · Underwriting Desk · Stark Financial</title>
<style>
:root{--navy:#002856;--navy2:#001B3A;--teal:#12B2A6;--tealdk:#0B8F86;--tealtint:#E4F7F5;
--ink:#10233A;--muted:#56677B;--faint:#8E9DAF;--line:#D8E0E9;--panel:#F2F6F9;
--green:#1E8E5A;--greentint:#E8F5EE;--red:#B83A2E;--redtint:#FBECEA;--amber:#B57C0E}
*{box-sizing:border-box}
body{margin:0;background:#EEF2F6;color:var(--ink);font:14.5px/1.55 "Segoe UI",system-ui,sans-serif}
header{background:var(--navy);color:#fff;padding:0 26px;display:flex;align-items:center;
gap:20px;height:62px;box-shadow:0 1px 0 rgba(0,0,0,.18)}
header .mark{font-weight:700;font-size:19px;letter-spacing:.5px}
header .mark span{color:var(--teal)}
header .sub{font-size:11.5px;color:#93AEC9;letter-spacing:.09em;text-transform:uppercase}
header .spacer{flex:1}
.nav{display:flex;gap:4px;margin-left:14px}
.navb{width:auto;margin:0;padding:7px 14px;font-size:12.5px;font-weight:600;border-radius:7px;
background:transparent;color:#9FBBD4;border:1px solid transparent}
.navb:hover{background:rgba(255,255,255,.07);color:#fff}
.navb.on{background:rgba(255,255,255,.13);color:#fff;border-color:rgba(255,255,255,.2)}
.psi{display:flex;align-items:baseline;gap:14px}
.psinum{font-size:52px;font-weight:700;letter-spacing:-1.5px;font-variant-numeric:tabular-nums}
.band{font-size:12px;font-weight:700;padding:5px 13px;border-radius:99px;text-transform:uppercase;letter-spacing:.07em}
.b-stable{background:var(--greentint);color:var(--green)}
.b-monitor{background:#FBF3E1;color:var(--amber)}
.b-investigate{background:var(--redtint);color:var(--red)}
.gauge{position:relative;height:26px;border-radius:5px;margin:20px 0 8px;
background:linear-gradient(90deg,var(--greentint) 0%,var(--greentint) 40%,#FBF3E1 40%,#FBF3E1 100%,var(--redtint) 100%)}
.chip{font-size:11px;padding:5px 11px;border-radius:99px;background:rgba(255,255,255,.09);
color:#CFE0EE;border:1px solid rgba(255,255,255,.14);white-space:nowrap}
.chip b{color:#fff;font-weight:600}
.dot{display:inline-block;width:7px;height:7px;border-radius:99px;margin-right:6px}
.on{background:var(--teal)} .off{background:#8194A8}
.wrap{display:grid;grid-template-columns:320px 1fr 268px;gap:16px;padding:16px 26px 34px;
align-items:start;max-width:1720px;margin:0 auto}
.card{background:#fff;border:1px solid var(--line);border-radius:10px;padding:17px}
h2{margin:0 0 13px;font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--navy)}
label{display:block;margin:13px 0 5px;font-size:13px;color:var(--muted)}
label b{color:var(--ink);font-weight:600;font-variant-numeric:tabular-nums}
.row{display:flex;justify-content:space-between;align-items:baseline}
input[type=range]{width:100%;accent-color:var(--teal);margin:0}
button{width:100%;margin-top:18px;padding:12px;background:var(--navy);color:#fff;border:0;
border-radius:8px;font-size:14.5px;font-weight:600;cursor:pointer}
button:hover{background:#013A76} button:disabled{opacity:.5;cursor:default}
.presets{display:flex;gap:6px;margin-top:10px}
.presets button{margin:0;padding:8px 4px;font-size:11.5px;background:var(--panel);
color:var(--navy);border:1px solid var(--line);font-weight:600}
.presets button:hover{background:#E3EBF3}
.empty{color:var(--faint);text-align:center;padding:70px 20px}
.verdict{display:flex;align-items:center;gap:30px;padding:20px 22px;border-radius:10px;border:1px solid var(--line)}
.verdict.APPROVE{background:var(--greentint);border-color:var(--green)}
.verdict.DECLINE{background:var(--redtint);border-color:var(--red)}
.big{font-size:50px;font-weight:700;line-height:1;letter-spacing:-1.5px;font-variant-numeric:tabular-nums}
.badge{font-size:22px;font-weight:700}
.APPROVE .big,.APPROVE .badge{color:var(--green)} .DECLINE .big,.DECLINE .badge{color:var(--red)}
.cap{font-size:12px;color:var(--muted);margin-top:4px}
.ref{margin-left:auto;text-align:right;font-size:11px;color:var(--muted);line-height:1.7}
.ref b{display:block;font-family:Consolas,monospace;font-size:12.5px;color:var(--ink)}
.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:14px}
.stat{border:1px solid var(--line);border-radius:9px;padding:12px;background:var(--panel)}
.stat .n{font-size:19px;font-weight:700;font-variant-numeric:tabular-nums}
.stat .l{font-size:11px;color:var(--muted);margin-top:3px;line-height:1.35}
.pos{color:var(--green)}.neg{color:var(--red)}.neu{color:var(--navy)}
.sec{margin-top:14px}
.track{position:relative;height:30px;border-radius:5px;margin:30px 0 30px}
.mk{position:absolute;top:-6px;width:3px;height:42px;border-radius:2px;background:var(--ink)}
.mk.be{background:var(--amber)}
/* the two callouts sit on different rows so they can never collide, however
   close the applicant lands to the break-even line */
.mkl{position:absolute;font-size:10.5px;font-weight:700;white-space:nowrap}
.mkl.above{top:-26px} .mkl.below{top:44px}
.axl{position:absolute;top:44px;font-size:10px;color:var(--faint)}
.fac{display:grid;grid-template-columns:1fr 150px 54px;gap:10px;align-items:center;
padding:7px 0;border-bottom:1px solid #EEF2F6;font-size:13px}
.fac:last-child{border:0}
.fbar{height:10px;border-radius:3px}
.fv{text-align:right;font-variant-numeric:tabular-nums;color:var(--muted);font-size:12px}
.notice{border:1px solid var(--red);border-left-width:5px;border-radius:9px;background:var(--redtint);padding:15px 17px;margin-top:14px}
.notice h3{margin:0 0 8px;font-size:11px;letter-spacing:.09em;color:var(--red);text-transform:uppercase}
.notice ol{margin:6px 0 0;padding-left:20px} .notice li{margin:4px 0}
.narr{border:1px solid var(--teal);border-left-width:5px;border-radius:9px;background:var(--tealtint);padding:15px 17px;margin-top:14px}
.narr h3{margin:0 0 7px;font-size:11px;letter-spacing:.09em;color:var(--tealdk);text-transform:uppercase}
.narr p{margin:0;font-size:14.5px;line-height:1.6}
.src{margin-top:8px;font-size:11px;color:var(--muted)}
.audit{font-size:12px}
.arow{display:grid;grid-template-columns:1fr auto;gap:4px;padding:8px 0;border-bottom:1px solid #EEF2F6}
.arow:last-child{border:0}
.aref{font-family:Consolas,monospace;font-size:11px;color:var(--muted)}
.apd{font-weight:700;font-variant-numeric:tabular-nums}
.atag{font-size:10px;font-weight:700;padding:2px 7px;border-radius:99px}
.tA{background:var(--greentint);color:var(--green)} .tD{background:var(--redtint);color:var(--red)}
.meta{font-size:11.5px;color:var(--muted);line-height:1.9}
.meta b{color:var(--ink);font-weight:600}
@media(max-width:1300px){.wrap{grid-template-columns:1fr}}
</style></head><body>
<header>
  <div><div class="mark">JARVIS<span>.</span></div>
    <div class="sub">Stark Financial · Underwriting Desk</div></div>
  <nav class="nav"><button class="navb on" id="nv_desk" onclick="view('desk')">Underwriting desk</button>
    <button class="navb" id="nv_mon" onclick="view('mon')">Portfolio &amp; monitoring</button></nav>
  <div class="spacer"></div>
  <div class="chip" id="c_model">loading…</div>
  <div class="chip" id="c_narr"></div>
  <div class="chip" id="c_cut"></div>
</header>

<div class="wrap" id="v_desk">
  <div class="card">
    <h2>Applicant</h2>
    <div class="presets">
      <button onclick="preset('thin')">Thin file</button>
      <button onclick="preset('mid')">Typical</button>
      <button onclick="preset('strong')">Strong</button>
    </div>
    <label><span class="row"><span>Age</span><b id="l_age">35</b></span>
      <input type="range" id="age" min="18" max="70" value="35"></label>
    <label><span class="row"><span>Annual income</span><b id="l_income">$157,500</b></span>
      <input type="range" id="income" min="20000" max="500000" value="157500" step="2500"></label>
    <label><span class="row"><span>Requested credit</span><b id="l_credit">$450,000</b></span>
      <input type="range" id="credit" min="20000" max="1200000" value="450000" step="10000"></label>
    <label><span class="row"><span>Years at current job</span><b id="l_employed_years">5</b></span>
      <input type="range" id="employed_years" min="0" max="40" value="5"></label>
    <label><span class="row"><span>Active credit lines</span><b id="l_active_lines">3</b></span>
      <input type="range" id="active_lines" min="0" max="12" value="3"></label>
    <label><span class="row"><span>Utilisation</span><b id="l_utilization">45%</b></span>
      <input type="range" id="utilization" min="0" max="100" value="45" step="5"></label>
    <button id="go" onclick="run()">Run underwriting decision</button>
  </div>

  <div id="out" class="card"><div class="empty">Set an applicant and run the decision.</div></div>

  <div class="card">
    <h2>Session audit trail</h2>
    <div id="audit" class="audit"><div style="color:var(--faint)">No decisions yet.</div></div>
    <h2 style="margin-top:20px">Model</h2>
    <div class="meta" id="meta"></div>
  </div>
</div>

<div id="v_mon" style="display:none;padding:16px 26px 34px;max-width:1720px;margin:0 auto">
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start">

    <div class="card">
      <h2>Decline threshold · live profit curve</h2>
      <div class="cap" style="margin-bottom:10px">Every point on this curve is a policy. Move the
        dial and the whole sealed book of 46,127 applications is re-decided.</div>
      <label><span class="row"><span>Decline at PD ≥</span><b id="l_th">7%</b></span>
        <input type="range" id="th" min="1" max="40" value="7" oninput="thMove()"></label>
      <svg id="curve" viewBox="0 0 620 200" style="width:100%;height:190px;margin-top:8px"></svg>
      <div class="grid4" id="pf"></div>
      <div class="cap" style="margin-top:10px">Computed live on the gender-free pipeline, the variant
        recommended for deployment. It scores marginally better than the champion quoted in the deck.</div>
    </div>

    <div class="card">
      <h2>Population drift monitor</h2>
      <div class="cap" style="margin-bottom:12px">PSI compares today's score distribution against the
        frozen reference. Below 0.10 stable, 0.10 to 0.25 monitor, above 0.25 investigate.</div>
      <div class="psi"><div class="psinum" id="psinum">0.000</div>
        <div class="band b-stable" id="psiband">stable</div></div>
      <div class="gauge"><div class="mk" id="psimk" style="left:0%"></div></div>
      <div class="cap" style="display:flex;justify-content:space-between">
        <span>0.00</span><span>0.10</span><span>0.25+</span></div>

      <h2 style="margin-top:22px">Stress the book</h2>
      <label><span class="row"><span>Income shock</span><b id="l_inc">0%</b></span>
        <input type="range" id="inc" min="0" max="40" value="0" step="5"
          oninput="document.getElementById('l_inc').textContent=this.value+'%'"></label>
      <label><span class="row"><span>External score shock</span><b id="l_sc">0%</b></span>
        <input type="range" id="sc" min="0" max="40" value="0" step="5"
          oninput="document.getElementById('l_sc').textContent=this.value+'%'"></label>
      <div class="presets" style="margin-top:12px">
        <button onclick="stress(0,0)">Control</button>
        <button onclick="stress(15,10)">Mild downturn</button>
        <button onclick="stress(25,20)">Severe recession</button>
      </div>
      <button id="runstress" onclick="stress()">Re-score the book under stress</button>
      <div id="driftout" class="cap" style="margin-top:14px"></div>
    </div>
  </div>
</div>

<script>
const F=["age","income","credit","employed_years","active_lines","utilization"];
const money=n=>"$"+Math.round(n).toLocaleString();
const fmt={age:v=>v,income:money,credit:money,employed_years:v=>v,active_lines:v=>v,utilization:v=>v+"%"};
F.forEach(f=>{const el=document.getElementById(f);
  const p=()=>document.getElementById("l_"+f).textContent=fmt[f](+el.value);
  el.addEventListener("input",p);p();});
const P={thin:{age:23,income:55000,credit:600000,employed_years:1,active_lines:7,utilization:85},
 mid:{age:35,income:157500,credit:450000,employed_years:5,active_lines:3,utilization:45},
 strong:{age:52,income:300000,credit:180000,employed_years:22,active_lines:1,utilization:10}};
function preset(k){const p=P[k];F.forEach(f=>{const e=document.getElementById(f);
  e.value=p[f];e.dispatchEvent(new Event("input"))});run();}

fetch("/api/status").then(r=>r.json()).then(s=>{
  document.getElementById("c_model").innerHTML='<span class="dot on"></span>pipeline <b>'+s.model+'</b>';
  document.getElementById("c_narr").innerHTML='<span class="dot '+(s.narrator_live?"on":"off")+'"></span>narrator <b>'+
    (s.narrator_live?"live":"local")+'</b>';
  document.getElementById("c_cut").innerHTML='cut-off <b>'+(s.threshold*100).toFixed(0)+'%</b> · break-even <b>'+
    (s.break_even*100).toFixed(1)+'%</b>';
  document.getElementById("meta").innerHTML=
    "Artifact <b>"+s.model+"</b><br>Sealed test rows <b>"+s.n_test.toLocaleString()+
    "</b><br>Model columns <b>"+s.n_features+"</b><br>LGD <b>"+(s.lgd*100)+
    "%</b> · margin <b>"+(s.margin*100)+"%</b><br>Narrator <b>"+s.narrator+"</b><br>Loaded <b>"+s.booted+"</b>";
});

function view(v){
  document.getElementById("v_desk").style.display = v==="desk"?"grid":"none";
  document.getElementById("v_mon").style.display  = v==="mon"?"block":"none";
  document.getElementById("nv_desk").classList.toggle("on",v==="desk");
  document.getElementById("nv_mon").classList.toggle("on",v==="mon");
  if(v==="mon" && !window._pf) loadPortfolio();
}

let CURVE=null;
async function loadPortfolio(){
  const r=await fetch("/api/portfolio?threshold="+(+document.getElementById("th").value/100));
  const d=await r.json(); window._pf=true; CURVE=d.curve; drawCurve(d); paintPf(d.at);
}
function drawCurve(d){
  const w=620,h=200,pad=26, xs=CURVE.map(p=>p.t), ys=CURVE.map(p=>p.net);
  const mx=Math.max(...ys), x0=Math.min(...xs), x1=Math.max(...xs);
  const X=t=>pad+(t-x0)/(x1-x0)*(w-pad*2), Y=v=>h-pad-(v/mx)*(h-pad*2);
  const path=CURVE.map((p,i)=>(i?"L":"M")+X(p.t).toFixed(1)+","+Y(p.net).toFixed(1)).join(" ");
  const th=+document.getElementById("th").value/100;
  document.getElementById("curve").innerHTML=`
    <path d="${path}" fill="none" stroke="#002856" stroke-width="2.5"/>
    <line x1="${X(d.optimum.t)}" y1="${pad-8}" x2="${X(d.optimum.t)}" y2="${h-pad}"
      stroke="#12B2A6" stroke-width="2" stroke-dasharray="4 3"/>
    <text x="${X(d.optimum.t)+5}" y="${pad-1}" font-size="11" fill="#0B8F86" font-weight="700">optimum ${(d.optimum.t*100).toFixed(0)}%</text>
    <line x1="${X(th)}" y1="${pad-8}" x2="${X(th)}" y2="${h-pad}" stroke="#10233A" stroke-width="2.5"/>
    <text x="${X(th)+5}" y="${pad+12}" font-size="11" fill="#10233A" font-weight="700">you: ${(th*100).toFixed(0)}%</text>
    <text x="${w/2}" y="${h-5}" font-size="10" fill="#8E9DAF" text-anchor="middle">decline threshold (predicted PD)</text>`;
}
function paintPf(a){
  const m=n=>"$"+(n/1e6).toFixed(1)+"M";
  document.getElementById("pf").innerHTML=`
   <div class="stat"><div class="n neu">${(a.approval_rate*100).toFixed(1)}%</div><div class="l">approval rate</div></div>
   <div class="stat"><div class="n neu">${(a.recall*100).toFixed(1)}%</div><div class="l">of defaults stopped<br>${a.defaults_caught.toLocaleString()} loans</div></div>
   <div class="stat"><div class="n pos">+${m(a.prevented_losses)}</div><div class="l">losses prevented</div></div>
   <div class="stat"><div class="n ${a.net_benefit>=0?"pos":"neg"}">${m(a.net_benefit)}</div><div class="l">net benefit<br>vs approving everyone</div></div>`;
}
let thT=null;
function thMove(){
  const v=+document.getElementById("th").value;
  document.getElementById("l_th").textContent=v+"%";
  clearTimeout(thT); thT=setTimeout(loadPortfolio,110);
}

async function stress(i,s2){
  if(i!==undefined){document.getElementById("inc").value=i;document.getElementById("l_inc").textContent=i+"%";
    document.getElementById("sc").value=s2;document.getElementById("l_sc").textContent=s2+"%";}
  const inc=+document.getElementById("inc").value, sc=+document.getElementById("sc").value;
  const b=document.getElementById("runstress");b.disabled=true;b.textContent="Re-scoring 46,127 applicants…";
  document.getElementById("driftout").textContent="";
  try{
    const d=await (await fetch(`/api/drift?income_shock=${inc}&score_shock=${sc}`)).json();
    document.getElementById("psinum").textContent=d.psi.toFixed(3);
    const bd=document.getElementById("psiband");
    bd.textContent=d.band; bd.className="band b-"+d.band;
    document.getElementById("psimk").style.left=Math.min(d.psi/0.35*100,99)+"%";
    document.getElementById("driftout").innerHTML=
      `Mean predicted default rate moved from <b>${(d.mean_pd_before*100).toFixed(2)}%</b> to
       <b>${(d.mean_pd_after*100).toFixed(2)}%</b>. Decline rate at the 7% cut-off moved from
       <b>${(d.decline_before*100).toFixed(1)}%</b> to <b>${(d.decline_after*100).toFixed(1)}%</b>.
       Re-scored in ${d.elapsed}s.` +
      (d.band==="investigate"?" <b style='color:var(--red)'>Alarm tripped: this is the monthly signal to revalidate.</b>":"");
  }catch(e){document.getElementById("driftout").textContent="Error: "+e;}
  b.disabled=false;b.textContent="Re-score the book under stress";
}

async function run(){
  const b=document.getElementById("go");b.disabled=true;b.textContent="Scoring…";
  const body={};F.forEach(f=>body[f]=+document.getElementById(f).value);
  document.getElementById("out").innerHTML='<div class="empty">Running the applicant through the pipeline…</div>';
  try{const r=await fetch("/api/score",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify(body)});render(await r.json());}
  catch(e){document.getElementById("out").innerHTML='<div class="empty">Error: '+e+'</div>';}
  b.disabled=false;b.textContent="Run underwriting decision";
}

// centre a marker label on its line, but pin it inside the track at the edges
function lbl(pct){
  if(pct<12) return "left:0;transform:none";
  if(pct>88) return "right:0;left:auto;transform:none";
  return "left:50%;transform:translateX(-50%)";
}

function render(d){
  const ev=d.money.expected_value, scale=25;
  const pos=Math.min(d.pd*100/scale*100,100), be=d.break_even*100/scale*100;
  const mx=Math.max(...d.factors.map(f=>Math.abs(f.value)));
  const facs=d.factors.map(f=>`<div class="fac"><div>${f.label}</div>
    <div><div class="fbar" style="width:${Math.min(Math.abs(f.value)/mx*100,100)}%;
      background:${f.value>0?"var(--red)":"var(--navy)"}"></div></div>
    <div class="fv">${f.value>0?"+":""}${f.value.toFixed(2)}</div></div>`).join("");
  document.getElementById("out").innerHTML=`
   <div class="verdict ${d.decision}">
     <div><div class="big">${(d.pd*100).toFixed(1)}%</div><div class="cap">probability of default</div></div>
     <div><div class="badge">${d.decision}</div><div class="cap">at the ${(d.threshold*100).toFixed(0)}% cut-off</div></div>
     <div class="ref"><b>${d.ref}</b>${d.timestamp}<br>decision reference</div>
   </div>
   <div class="grid4">
     <div class="stat"><div class="n neu">${money(d.money.exposure)}</div><div class="l">exposure if we lend</div></div>
     <div class="stat"><div class="n neg">−${money(d.money.expected_loss)}</div><div class="l">expected loss<br>PD × 65% LGD</div></div>
     <div class="stat"><div class="n pos">+${money(d.money.expected_margin)}</div><div class="l">expected margin<br>survival × 5%</div></div>
     <div class="stat"><div class="n ${ev>=0?"pos":"neg"}">${ev>=0?"+":"−"}${money(Math.abs(ev))}</div><div class="l">expected value<br>of this loan</div></div>
   </div>
   <div class="sec card" style="border:1px solid var(--line)">
     <h2>Where this loan sits</h2>
     <div class="track" style="background:linear-gradient(90deg,var(--greentint) 0%,var(--greentint) ${be}%,var(--redtint) ${be}%,var(--redtint) 100%)">
       <div class="mk be" style="left:${be}%">
         <div class="mkl below" style="color:var(--amber);${lbl(be)}">break-even ${(d.break_even*100).toFixed(1)}%</div></div>
       <div class="mk" style="left:${pos}%">
         <div class="mkl above" style="${lbl(pos)}">this applicant ${(d.pd*100).toFixed(1)}%</div></div>
       <div class="axl" style="left:0">0%</div>
       <div class="axl" style="right:0">${scale}%+</div>
     </div>
     <div class="cap" style="margin-top:6px">Left of the amber line the loan earns money. Right of it, a 5% margin no longer covers a 65% loss.</div>
   </div>
   <div class="sec card" style="border:1px solid var(--line)"><h2>What drove this decision</h2>${facs}</div>
   ${d.reasons.length?`<div class="notice"><h3>Adverse action notice · ${d.ref}</h3>
     <div>Principal reasons for the decision:</div><ol>${d.reasons.map(r=>`<li>${r}</li>`).join("")}</ol></div>`:""}
   <div class="narr"><h3>Plain-English report</h3><p>${d.narrative}</p>
     <div class="src">Narrative: ${d.narrative_source}. The decision, the money and the reason codes are
       computed locally by ${d.model} and are identical with or without the AI.</div></div>`;
  document.getElementById("audit").innerHTML=d.audit.map(a=>`<div class="arow">
    <div><div class="apd">${(a.pd*100).toFixed(1)}%</div><div class="aref">${a.ref}</div></div>
    <div style="text-align:right"><span class="atag ${a.decision==="APPROVE"?"tA":"tD"}">${a.decision}</span>
      <div class="aref">${money(a.exposure)}</div></div></div>`).join("");
}
</script></body></html>"""


if __name__ == "__main__":
    print("\n  JARVIS Underwriting Desk · Stark Financial")
    boot()
    key, src = get_api_key()
    if key:
        print(f"  narrator: {DEFAULT_MODEL} via OpenRouter, key from {src} (…{key[-4:]})")
    else:
        print("  narrator: deterministic template. Paste an OpenRouter key into")
        print("            api_key.txt to enable AI narration. Everything else is identical.")
    print("  http://127.0.0.1:5000\n")
    app.run(host="127.0.0.1", port=5000, debug=False)

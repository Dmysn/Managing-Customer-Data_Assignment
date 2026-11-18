"""As-of replay of the Studio North report.

Every snapshot is built only from records dated on or before the as-of month's
end:

* Observed results filter the canonical SQL exports by calendar month (customer
  months), acquisition month (cohorts) or test completion date (holdouts).
* Forecasts refit the report's hierarchical shifted-Beta-Geometric + Gamma model
  (``cohort_lab.model``) on the truncated cohort panel. Parameters fitted on later
  data are never reused. If the panel is too short for the model's own minimum
  (12 renewal cells), the forecast is left blank with the model's reason.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20261116          # same seed as the baseline report fit
STEPS = 3000             # same NUTS budget as the report (1000 warmup + 1000 draws x 4 chains)
KEYS = ["cohort_month", "channel", "primary_need"]
HORIZON = 12
FIRST_COHORTS = ["2024-01-01", "2024-02-01", "2024-03-01"]


def month_range(start: str = "2024-01-01", end: str = "2025-12-01") -> list[str]:
    return [d.strftime("%Y-%m-%d") for d in pd.date_range(start, end, freq="MS")]


def next_month(as_of: str) -> str:
    return (pd.Timestamp(as_of) + pd.DateOffset(months=1)).strftime("%Y-%m-%d")


def _clean(value):
    """JSON-safe scalars (NaN/inf -> None, numpy -> python)."""
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        v = float(value)
        return None if not math.isfinite(v) else v
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if value is pd.NA or value is pd.NaT:
        return None
    return value


# --------------------------------------------------------------------------
# Forecasts: one refit per as-of month (expensive; cached by the builder).
# --------------------------------------------------------------------------
def forecast_as_of(tables_dir: str, as_of: str, seed: int = SEED, steps: int = STEPS) -> dict:
    """Refit the report's model on records dated through ``as_of`` and value every joined cohort."""
    from cohort_lab import model as m  # imported in the worker so JAX is configured there

    tables = Path(tables_dir)
    full = pd.read_csv(tables / "cohort_age_summary.csv")
    frame = m._validate(full[full.calendar_month <= as_of].copy())
    costs = pd.read_csv(tables / "cohort_acquisition_costs.csv")
    costs = costs[costs.cohort_month <= as_of]
    company = pd.read_csv(tables / "cohort_cash_economics.csv").query("age_month == 0")
    company = company[company.cohort_month <= as_of].set_index("cohort_month")
    result = {"as_of": as_of, "seed": seed, "steps": steps,
              "training_rows": int(len(frame)), "training_last_calendar_month": as_of,
              "cohorts_in_training": sorted(frame.cohort_month.unique().tolist())}
    try:
        draws, diagnostic = m._posterior(frame, seed, steps)
    except ValueError as error:  # the model's own minimum-history rule
        result.update(status="blank", reason=f"History too short to fit the report's model: {error}")
        return _clean(result)
    diag = {k: diagnostic[k] for k in ("max_r_hat", "min_ess", "divergences", "n_retention_cells",
                                       "n_revenue_cells", "retention_pearson_dispersion",
                                       "revenue_pearson_dispersion")}
    result["diagnostics"] = diag
    params = {row["parameter"]: {"mean": row["mean"], "p05": row["p05"], "p95": row["p95"]}
              for row in diagnostic["parameter_summary"]
              if row["parameter"].startswith(("mean_beta", "revenue_beta[cohort_trend]"))}
    result["parameters"] = params
    if diag["max_r_hat"] > 1.01 or diag["min_ess"] < 400 or diag["divergences"]:
        result.update(status="withheld",
                      reason=("Fit failed the report's release checks (R-hat <= 1.01, ESS >= 400, "
                              f"0 divergences): R-hat={diag['max_r_hat']:.4f}, ESS={diag['min_ess']:.0f}, "
                              f"divergences={diag['divergences']}"))
        return _clean(result)

    cost_map = costs.set_index(KEYS)
    cells, aggregates = [], {}
    for key, g in frame.groupby(KEYS, sort=True):
        g = g.sort_values("age_month")
        n0 = int(g.n_acquired.iloc[0])
        observed_len = min(len(g), HORIZON)
        retained = np.zeros((m.DRAWS, HORIZON)); contribution = retained.copy(); revenue = retained.copy()
        retained[:, :observed_len] = g.n_retained.to_numpy()[:observed_len]
        revenue[:, :observed_len] = g.net_revenue.to_numpy()[:observed_len]
        contribution[:, :observed_len] = g.contribution.to_numpy()[:observed_len]
        observed = np.arange(HORIZON) < observed_len
        if observed_len < HORIZON:
            ages = list(range(observed_len, HORIZON))
            future_n, future_gross = m._future(draws, g.iloc[-1], ages, float(g.n_retained.iloc[-1]))
            net_ratio, contrib_ratio = m._economic_ratios(frame, g.iloc[-1], ages)  # as-of economics only
            retained[:, observed_len:] = future_n
            revenue[:, observed_len:] = future_gross * net_ratio
            contribution[:, observed_len:] = future_gross * contrib_ratio
        cost = cost_map.loc[key] if key in cost_map.index else None
        supported = cost is not None and pd.notna(cost.cac)
        spend = float(cost.acquisition_spend) if cost is not None and pd.notna(cost.acquisition_spend) else 0.0
        rec = m._valuation_record(key, n0, spend, observed_len, contribution, observed, supported)
        rec.update(channel=key[1], primary_need=key[2])
        cells.append(rec)
        a = aggregates.setdefault(key[0], {"n": 0, "retained": np.zeros_like(retained),
                                           "revenue": np.zeros_like(revenue),
                                           "contribution": np.zeros_like(contribution),
                                           "observed_months": observed_len})
        a["n"] += n0; a["retained"] += retained; a["revenue"] += revenue; a["contribution"] += contribution

    cohorts = []
    for cohort, a in sorted(aggregates.items()):
        spend = float(company.loc[cohort, "acquisition_spend"])
        if int(company.loc[cohort, "n_acquired"]) != a["n"]:
            raise ValueError("Whole-cohort acquisition denominator differs")
        obs = np.arange(HORIZON) < a["observed_months"]
        rec = m._valuation_record((cohort,), a["n"], spend, a["observed_months"], a["contribution"], obs)
        cumul = np.cumsum(a["contribution"].mean(axis=0)) - spend
        rec["curve"] = [{"age": age,
                         "retained_share": float(a["retained"][:, age].mean()) / a["n"],
                         "retained_share_p05": float(np.quantile(a["retained"][:, age], .05)) / a["n"],
                         "retained_share_p95": float(np.quantile(a["retained"][:, age], .95)) / a["n"],
                         "net_revenue": float(a["revenue"][:, age].mean()),
                         "contribution": float(a["contribution"][:, age].mean()),
                         "balance_per_customer": float(cumul[age]) / a["n"],
                         "observed": bool(obs[age])} for age in range(HORIZON)]
        cohorts.append(rec)
    result.update(status="fitted", reason="", cohorts=cohorts, cells=cells)
    return _clean(result)


# --------------------------------------------------------------------------
# Observed snapshots: cheap date filters of the canonical SQL exports.
# --------------------------------------------------------------------------
class Tables:
    def __init__(self, tables_dir: Path):
        t = Path(tables_dir)
        self.totals = pd.read_csv(t / "cohort_totals.csv")
        self.cash = pd.read_csv(t / "cohort_cash_economics.csv")
        self.age = pd.read_csv(t / "cohort_age_summary.csv")
        self.company = pd.read_csv(t / "company_totals.csv")
        self.tests = pd.read_csv(t / "channel_cac.csv")


def observed_snapshot(tb: Tables, as_of: str) -> dict:
    tot = tb.totals[tb.totals.calendar_month <= as_of]
    cash = tb.cash[tb.cash.calendar_month <= as_of]
    triangle = [{"cohort": r.cohort_month, "age": int(r.age_month), "n_acquired": int(r.n_acquired),
                 "n_retained": int(r.n_retained), "retained_share": float(r.retained_share),
                 "net_revenue": float(r.net_revenue), "contribution": float(r.contribution)}
                for r in tot.itertuples()]
    cohorts = []
    for cohort, g in cash.groupby("cohort_month", sort=True):
        g = g.sort_values("age_month")
        paid = g[g.balance_after_acquisition >= 0]
        payback_age = int(paid.age_month.iloc[0]) if len(paid) else None
        cohorts.append({"cohort": cohort, "n_acquired": int(g.n_acquired.iloc[0]),
                        "acquisition_spend": float(g.acquisition_spend.iloc[0]), "cac": float(g.cac.iloc[0]),
                        "observed_months": int(len(g)),
                        "balance": [float(x) for x in g.balance_per_customer],
                        "cumulative_contribution": [float(x) for x in g.cumulative_contribution_per_customer],
                        "observed_payback_month": None if payback_age is None else payback_age + 1})
    first = tb.age[(tb.age.age_month == 0) & (tb.age.cohort_month <= as_of)]
    mix = [{"cohort": r.cohort_month, "channel": r.channel, "primary_need": r.primary_need,
            "n_acquired": int(r.n_acquired)} for r in first.itertuples()]
    comp = tb.company[tb.company.calendar_month <= as_of]
    company = [{"month": r.calendar_month, "active_members": int(r.n_retained), "net_revenue": float(r.net_revenue),
                "contribution": float(r.contribution), "acquisition_spend": float(r.acquisition_spend)}
               for r in comp.itertuples()]
    cutoff = next_month(as_of)  # a test is known once its fixed window has closed by the as-of month end
    done = tb.tests[tb.tests.followup_end_at.str[:10] <= cutoff]
    tests = [{"test_id": r.test_id, "test_month": r.test_month, "channel": r.channel, "primary_need": r.primary_need,
              "followup_end_at": r.followup_end_at[:10], "buyers_treatment": int(r.buyers_treatment),
              "buyers_control": int(r.buyers_control), "incremental_buyers": float(r.incremental_buyers),
              "credited_cac": float(r.credited_cac), "icac": None if pd.isna(r.icac) else float(r.icac),
              "icac_ci_lower": None if pd.isna(r.icac_ci_lower) else float(r.icac_ci_lower),
              "icac_ci_upper": None if pd.isna(r.icac_ci_upper) else float(r.icac_ci_upper)}
             for r in done.itertuples()]
    return _clean({"triangle": triangle, "cohorts": cohorts, "mix": mix, "company": company, "tests": tests,
                   "matched_age": matched_age_signal(tb, as_of)})


def matched_age_signal(tb: Tables, as_of: str) -> dict:
    """Observed same-age comparison: latest three cohorts with six receipts vs Jan-Mar 2024 (age 5)."""
    cash = tb.cash[(tb.cash.calendar_month <= as_of) & (tb.cash.age_month == 5)]
    tot = tb.totals[(tb.totals.calendar_month <= as_of) & (tb.totals.age_month == 5)]
    eligible = sorted(set(cash.cohort_month) - set(FIRST_COHORTS))
    if len(set(FIRST_COHORTS) & set(cash.cohort_month)) < 3 or len(eligible) < 3:
        return {"available": False, "reason": "Fewer than three later cohorts have six observed receipts."}
    latest = eligible[-3:]

    def summary(cohorts):
        c = cash[cash.cohort_month.isin(cohorts)]; t = tot[tot.cohort_month.isin(cohorts)]
        n = float(c.n_acquired.sum())
        return {"cohorts": list(cohorts), "n_acquired": int(n),
                "retained_share": float(t.n_retained.sum()) / float(t.n_acquired.sum()),
                "cash_after_cac_per_customer": float(c.balance_after_acquisition.sum()) / n,
                "cac": float((c.cac * c.n_acquired).sum()) / n}
    base, late = summary(FIRST_COHORTS), summary(latest)
    supported = (late["retained_share"] > base["retained_share"]
                 and late["cash_after_cac_per_customer"] > base["cash_after_cac_per_customer"]
                 and late["cash_after_cac_per_customer"] >= 0)
    return {"available": True, "baseline": base, "latest": late, "supported": bool(supported)}


def decision_snapshot(observed: dict, forecast: dict | None, as_of: str) -> dict:
    """Pair each cell's latest completed iCAC with as-of contribution value before CAC (report section 08)."""
    tests = pd.DataFrame(observed["tests"])
    if tests.empty:
        return {"available": False, "reason": "No monthly holdout test had completed its 31-day window."}
    latest = (tests.sort_values(["followup_end_at", "test_id"], ascending=[False, True])
              .groupby(["channel", "primary_need"], sort=True).head(1))
    benchmark = (pd.Timestamp(as_of) - pd.DateOffset(months=5)).strftime("%Y-%m-%d")
    if not forecast or forecast.get("status") != "fitted":
        return {"available": False, "reason": "No released as-of forecast for contribution value.",
                "tests": latest.to_dict("records")}
    cells = pd.DataFrame(forecast["cells"])
    value = cells[cells.cohort_month == benchmark]
    rows = []
    for t in latest.itertuples():
        v = value[(value.channel == t.channel) & (value.primary_need == t.primary_need)]
        if v.empty or t.icac is None or pd.isna(t.icac):
            continue
        ltv = float(v.ltv_before_cac_mean.iloc[0])
        rows.append({"channel": t.channel, "primary_need": t.primary_need, "test_id": t.test_id,
                     "test_month": t.test_month, "icac": float(t.icac), "icac_ci_lower": t.icac_ci_lower,
                     "icac_ci_upper": t.icac_ci_upper, "credited_cac": float(t.credited_cac),
                     "incremental_buyers": float(t.incremental_buyers), "value_cohort": benchmark,
                     "value_before_cac": ltv, "value_p05": float(v.ltv_before_cac_p05.iloc[0]),
                     "value_p95": float(v.ltv_before_cac_p95.iloc[0]),
                     "forecast_share": float(v.forecast_share.iloc[0]),
                     "value_less_icac": ltv - float(t.icac), "value_to_icac": ltv / float(t.icac)})
    if len(rows) < 4:
        return {"available": False, "reason": "Not every channel-by-need cell has both a completed test and a value benchmark.",
                "rows": rows}
    df = pd.DataFrame(rows)
    sb = df[(df.channel == "search") & (df.primary_need == "build_skill")].iloc[0]
    save = df[df.primary_need == "save_time"]
    point = bool(sb.value_less_icac > 0 and sb.value_less_icac == df.value_less_icac.max()
                 and (save.value_less_icac < 0).all())
    robust = bool(point and sb.icac_ci_upper is not None and sb.value_before_cac > sb.icac_ci_upper)
    return _clean({"available": True, "benchmark_cohort": benchmark, "rows": rows,
                   "supported_point": point, "supported_robust": robust})


def build_snapshots(tables_dir: Path, forecasts: dict[str, dict]) -> list[dict]:
    tb = Tables(tables_dir)
    snapshots = []
    for as_of in month_range():
        obs = observed_snapshot(tb, as_of)
        fc = forecasts.get(as_of)
        snapshots.append({"as_of": as_of, "observed": obs, "forecast": fc,
                          "decision": decision_snapshot(obs, fc, as_of)})
    return snapshots


def first_support(snapshots: list[dict]) -> dict:
    """First as-of month at which each evidence rule holds (and whether it then held every month after)."""
    def first(flag):
        months = [s["as_of"] for s in snapshots]
        hits = [flag(s) for s in snapshots]
        for i, hit in enumerate(hits):
            if hit:
                return {"first_month": months[i], "held_every_month_after": all(hits[i:])}
        return {"first_month": None, "held_every_month_after": False}
    return {
        "matched_age_improvement": first(lambda s: s["observed"]["matched_age"].get("supported", False)),
        "acquisition_priority_point": first(lambda s: s["decision"].get("supported_point", False)),
        "acquisition_priority_robust": first(lambda s: s["decision"].get("supported_robust", False)),
    }


def load_forecasts(directory: Path) -> dict[str, dict]:
    return {json.loads(p.read_text())["as_of"]: json.loads(p.read_text())
            for p in sorted(Path(directory).glob("*.json"))}

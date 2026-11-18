"""Build the Studio North month-by-month replay dashboard.

    uv run --frozen python build_dashboard.py            # full build (refits every as-of month)
    uv run --frozen python build_dashboard.py --workers 3
    uv run --frozen python build_dashboard.py --reuse-fits   # rebuild HTML from saved fits only

Steps
1. Locate/download the pinned Studio North lab release (same commit as the baseline report).
2. Re-run the lab's canonical DuckDB SQL on the released CSVs (no data are regenerated).
3. For every as-of month, refit the report's model on records dated through that month.
4. Build observed snapshots by date filtering, pair them with the as-of forecasts,
   reconcile December 2025 with the baseline report, and write one self-contained HTML file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from studio_dashboard import replay  # noqa: E402
from studio_dashboard.lab_source import BASELINE_REPORT_COMMIT, LAB_COMMIT, LAB_REPOSITORY, ensure_lab  # noqa: E402


def _init_worker(lab_path: str) -> None:
    if lab_path not in sys.path:
        sys.path.insert(0, lab_path)


def _fit(tables_dir: str, as_of: str) -> dict:
    started = time.time()
    result = replay.forecast_as_of(tables_dir, as_of)
    result["fit_seconds"] = round(time.time() - started, 1)
    return result


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reconcile(final: dict, baseline_dir: Path) -> dict:
    """Compare the December 2025 replay with the baseline report's saved tables."""
    out = {"baseline_dir": str(baseline_dir.relative_to(ROOT)) if baseline_dir.is_relative_to(ROOT) else str(baseline_dir)}
    pdf = baseline_dir / "customer-economics-report.pdf"
    if pdf.exists():
        out["baseline_pdf_sha256"] = sha256(pdf)
    fc = final["forecast"]
    if not fc or fc.get("status") != "fitted":
        out["status"] = "not_available"
        return out
    rows = []
    base = pd.read_csv(baseline_dir / "cohort_valuation.csv")
    mine = pd.DataFrame(fc["cohorts"]).drop(columns=["curve"])
    merged = base.merge(mine, on="cohort_month", suffixes=("_report", "_replay"))
    for col in ["cac", "ltv_before_cac_mean", "net_ltv_mean", "forecast_share", "payback_month"]:
        diff = (merged[f"{col}_replay"].astype(float) - merged[f"{col}_report"].astype(float)).abs()
        rows.append({"table": "cohort_valuation", "measure": col, "rows": int(len(merged)),
                     "max_abs_difference": float(diff.max())})
    dec = pd.read_csv(baseline_dir / "channel_value_decision.csv")
    replay_dec = pd.DataFrame(final["decision"].get("rows", []))
    if not replay_dec.empty:
        m = dec.merge(replay_dec, on=["channel", "primary_need"], suffixes=("_report", "_replay"))
        for a, b in [("ltv_before_cac_mean", "value_before_cac"), ("icac_report", "icac_replay"),
                     ("value_less_icac_report", "value_less_icac_replay")]:
            diff = (m[b].astype(float) - m[a].astype(float)).abs()
            rows.append({"table": "channel_value_decision", "measure": b.replace("_replay", ""),
                         "rows": int(len(m)), "max_abs_difference": float(diff.max())})
    cash = pd.read_csv(baseline_dir / "cohort_cash_economics.csv")
    last = cash.sort_values("age_month").groupby("cohort_month").tail(1).set_index("cohort_month")
    obs = {c["cohort"]: c["balance"][-1] for c in final["observed"]["cohorts"]}
    diff = max(abs(obs[k] - float(last.loc[k, "balance_per_customer"])) for k in obs)
    rows.append({"table": "cohort_cash_economics", "measure": "latest_balance_per_customer",
                 "rows": len(obs), "max_abs_difference": float(diff)})
    out["checks"] = rows
    worst = max(r["max_abs_difference"] for r in rows)
    out["max_abs_difference"] = worst
    out["status"] = "exact" if worst < 1e-6 else "within_one_cent" if worst < 0.01 else "differs"
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--lab-dir", help="Existing lab checkout at the pinned commit (default: download into .lab/)")
    p.add_argument("--baseline-dir", default=str(ROOT / "baseline"), help="Baseline report tables and PDF")
    p.add_argument("--workers", type=int, default=3, help="Parallel as-of refits (each uses one CPU core)")
    p.add_argument("--reuse-fits", action="store_true", help="Only use saved fits in results/forecasts")
    p.add_argument("--months", nargs="*", help="Restrict refits to these as-of months (YYYY-MM)")
    args = p.parse_args()

    lab = ensure_lab(ROOT, args.lab_dir)
    from cohort_lab.analysis import build_views

    work = ROOT / "work" / "analysis"
    print("Running the lab's canonical SQL on the released data ...", flush=True)
    analysis = build_views(lab / "data", work)
    tables = work / "tables"

    fit_dir = ROOT / "results" / "forecasts"
    fit_dir.mkdir(parents=True, exist_ok=True)
    months = replay.month_range()
    wanted = [m for m in months if not args.months or m[:7] in args.months]
    # Largest (latest) panels first for better load balancing across workers.
    todo = sorted((m for m in wanted if not (fit_dir / f"{m[:7]}.json").exists()), reverse=True)
    if todo and not args.reuse_fits:
        print(f"Refitting {len(todo)} as-of months with {args.workers} workers ...", flush=True)
        with ProcessPoolExecutor(max_workers=args.workers, initializer=_init_worker, initargs=(str(lab),)) as pool:
            jobs = {pool.submit(_fit, str(tables), m): m for m in todo}
            for job in as_completed(jobs):
                res = job.result()
                (fit_dir / f"{res['as_of'][:7]}.json").write_text(json.dumps(res, indent=1, allow_nan=False), encoding="utf-8")
                d = res.get("diagnostics", {})
                print(f"  {res['as_of'][:7]}: {res['status']:<8} {res.get('fit_seconds', 0):>6}s "
                      f"R-hat={d.get('max_r_hat', float('nan')):.4f} ESS={d.get('min_ess', float('nan')):.0f}", flush=True)

    forecasts = replay.load_forecasts(fit_dir)
    snapshots = replay.build_snapshots(tables, forecasts)
    support = replay.first_support(snapshots)
    rec = reconcile(snapshots[-1], Path(args.baseline_dir))

    meta = {
        "lab_repository": LAB_REPOSITORY, "lab_commit": LAB_COMMIT, "baseline_report_commit": BASELINE_REPORT_COMMIT,
        "data_as_of": analysis["data_as_of"], "currency": analysis["currency"], "timezone": analysis["timezone"],
        "seed": replay.SEED, "nuts_steps": replay.STEPS, "horizon_receipts": replay.HORIZON, "monthly_discount": 0.01,
        "source_hashes": {p.name: sha256(p) for p in sorted((lab / "data").glob("*.csv"))},
        "evidence_rules": {
            "matched_age_improvement": "Observed: the latest three cohorts with six receipts beat Jan-Mar 2024 at age 5 on retention and on cash after CAC, and their cash after CAC is >= 0.",
            "acquisition_priority_point": "Search / build skill has the largest positive value less iCAC and both save-time cells are negative (point estimates).",
            "acquisition_priority_robust": "As above, and Search / build skill value exceeds the upper 95% bound of its iCAC.",
        },
    }
    data = {"meta": meta, "snapshots": snapshots, "first_support": support, "reconciliation": rec}
    results = ROOT / "results"
    (results / "summary.json").write_text(json.dumps({"meta": meta, "first_support": support, "reconciliation": rec,
        "forecast_status": {s["as_of"][:7]: (s["forecast"] or {}).get("status", "missing") for s in snapshots}},
        indent=1), encoding="utf-8")
    template = (ROOT / "studio_dashboard" / "template.html").read_text(encoding="utf-8")
    payload = json.dumps(data, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")
    out = ROOT / "dashboard" / "studio-north-dashboard.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(template.replace("/*__DATA__*/null", payload), encoding="utf-8")
    print(f"First support: {json.dumps(support)}")
    print(f"Reconciliation: {rec.get('status')} (max abs difference {rec.get('max_abs_difference')})")
    print(f"Dashboard written to {out}")


if __name__ == "__main__":
    main()

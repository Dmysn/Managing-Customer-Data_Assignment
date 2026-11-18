# Studio North — month-by-month replay dashboard

An extension of the Studio North customer-economics analysis (Path A, FAQ 4: *“Replay the report as a month-by-month dashboard”*).
It answers the same managerial question — **Are we moving in the right direction as a company?** — by letting you step through
Studio North's history one month at a time, from January 2024 to December 2025. Each as-of month shows **only what the company could
have known by that month's end**.

**Open the dashboard:** [`dashboard/studio-north-dashboard.html`](dashboard/studio-north-dashboard.html) — a single self-contained file
(no server, no internet, no external libraries). Download it and open it in any modern browser.

## What the dashboard shows

| Panel | What it shows at the selected as-of month | Observed or forecast |
|---|---|---|
| Header and status line | As-of month, slider, ◀ ▶ buttons, Play, ←/→ keys; data and model status for that month | — |
| KPI tiles | Active members, net revenue, contribution, acquisition spend, newest cohort CAC, cohorts already paid back | Observed |
| Contractual retention triangle | % of each joining cohort still subscribed, by age; cohorts not yet joined are hidden | Observed |
| Company revenue, contribution, spend | Monthly totals across active cohorts up to the as-of month | Observed |
| 12-receipt contribution LTV vs CAC | Per acquired customer, discounted 1%/month; solid = already observed, hatched = forecast remainder; tick = historical average CAC | Both, visibly distinct |
| Cash payback month | Payment at which undiscounted cumulative contribution covers CAC; filled = observed, hollow = forecast | Both |
| Cohort explorer | One cohort's cash after CAC per customer and retention curve; forecast dashed with 90% parameter band | Both |
| Cohort mix | Each cohort's split across Search/Partner × save-time/build-skill | Observed |
| Acquisition decision | Latest *completed* monthly holdout iCAC per cell vs as-of contribution value before CAC | Experiment + forecast |
| Same-age check | Latest three cohorts with six receipts vs Jan–Mar 2024 at age 5 | Observed |
| Evidence timeline | In which months each decision rule held; answers *“when did the evidence first support the recommendation?”* | — |
| Reconciliation | December 2025 replay vs the original report's saved tables | — |

Definitions follow the baseline report exactly: a cohort is the calendar month of a customer's first successful payment; age 0 is the
acquisition month; denominators stay the original acquired customers; contribution = net revenue (after discounts and refunds) − variable
costs; LTV = first 12 monthly receipts discounted at 1% per month with the first receipt at t = 1; CAC = historical average (tracked
acquisition spend ÷ customers acquired); payback = first payment at which undiscounted cumulative contribution ≥ CAC; iCAC = incremental
spend ÷ incremental buyers from the randomized monthly holdouts. Fixed operating costs are outside the data.

## How “only information available by the as-of month” is enforced

* **Observed results** are the lab's canonical DuckDB SQL exports filtered by date: customer-months by `calendar_month ≤ as-of`,
  cohorts by acquisition month, and holdout tests only once their fixed 31-day window has closed (`followup_end_at ≤` the as-of month end).
  Each snapshot is precomputed in Python from the filtered rows, so the HTML file only contains what each month could see.
* **Forecasts** are refit for every as-of month with the report's own model (`cohort_lab.model`: hierarchical shifted-Beta-Geometric
  retention + Gamma revenue, NumPyro NUTS, 4 chains × 1,000 warm-up + 1,000 draws, seed 20261116) on the cohort panel truncated to that
  month. Gross-to-contribution ratios also come only from the truncated panel. Parameters fitted on later data are never reused.
* **Too-short history is left blank.** January and February 2024 have fewer than the model's minimum 12 renewal cells, so their forecasts
  are blank and the dashboard says so. Every other month (March 2024 – December 2025) passed the report's release checks
  (R-hat ≤ 1.01, ESS ≥ 400, 0 divergences); per-month diagnostics are in `results/forecasts/*.json`.

## Reconciliation with the original report

The December 2025 view refits the model on the full panel with the same data, SQL, code, seed and sampling budget as the report and is
compared with the baseline report's saved tables in [`baseline/`](baseline/) (including the original PDF):

| Baseline table | Measures | Max absolute difference |
|---|---|---|
| `cohort_valuation.csv` (24 cohorts) | CAC, 12-receipt LTV, net LTV, forecast share, payback month | < 5×10⁻¹¹ (payback identical) |
| `channel_value_decision.csv` (4 cells) | value before CAC, iCAC, value − iCAC | < 1×10⁻¹⁰ |
| `cohort_cash_economics.csv` | latest observed cash after CAC per customer | 0 |

The latest month **reproduces the report exactly**; the only differences are floating-point rounding from CSV storage.

## What the replay shows

**Are newer cohorts' economics improving?** Yes, and it is visible early in observed data alone.

* From **November 2024** onward, the latest three cohorts with six receipts beat Jan–Mar 2024 at the same age on both retention and cash
  after CAC, and the rule held in every later month. As of Nov 2024: retained at age 5 rose from 46.9% to 57.2% and cash after CAC per
  customer from −$11.88 to +$9.20 (Apr–Jun 2024 cohorts). By Dec 2025 the comparison (May–Jul 2025 cohorts) is 65.4% retained and +$56.01.
* Cash payback shortened from 7–8 payments (early 2024 cohorts) to 3 payments for the newest cohorts; historical average CAC fell from about
  $111 to about $71–75.
* The first as-of forecast (March 2024) valued the January 2024 cohort at $164 of 12-receipt contribution; it actually earned $167.

**When did the evidence first support the report's recommendation** (prioritise Search · build skill, hold Partner · build skill,
don't scale save-time campaigns)?

* The acquisition comparison only exists once monthly holdouts completed (first window closed 1 Aug 2025). On point estimates the rule first
  held as of **October 2025** (Search · build skill: value $288 vs iCAC $196; both save-time cells below iCAC), but it was **not stable** —
  in November 2025 Partner · build skill briefly had the larger margin.
* It first held **robustly** — Search · build skill value above even the upper 95% bound of its iCAC — as of **December 2025**
  (value $284 vs iCAC $151, upper bound $215), the month the report was written.
* So the *direction* (improving cohorts) was supported by November 2024, but the *specific acquisition recommendation* needed the
  continuous holdouts and was only robust at the final month — a reason to keep the monthly tests running.

## Run it yourself

Requirements: Python 3.12 and [uv](https://docs.astral.sh/uv/). No GPU. Internet only for the first `uv sync` and the one-time lab download.

```bash
uv sync --frozen
uv run --frozen python build_dashboard.py --reuse-fits     # rebuild the HTML from the saved fits (seconds)
uv run --frozen python build_dashboard.py --workers 3      # refit every as-of month that lacks a saved fit
```

To redo all fits from scratch, delete `results/forecasts/` first (≈ 45 minutes on a 4-core laptop with 3 workers; later months take
3–5 minutes each). `--months 2025-06 2025-07` refits only selected months. `--lab-dir PATH` uses an existing lab checkout instead of
downloading one.

What the build does:

1. Downloads the Studio North lab at commit `4848f4b75628bde8a43858bb54ca7c09de603f61` into `.lab/` (not committed).
   The baseline report was produced from `0e40ce3cd0b788a3914ca4eb9f90d58ae1b62903`, which is no longer downloadable after the upstream
   history was rewritten; its data CSVs, data manifest, `sql/00_sources.sql`, `sql/01_views.sql` and `cohort_lab/model.py`, `analysis.py`
   and `data.py` are byte-identical (SHA-256) to the pinned commit, and the exact reconciliation above confirms it.
2. Runs the lab's canonical SQL (`cohort_lab.analysis.build_views`) on the released data into `work/` — no data are regenerated.
3. Refits the model per as-of month in parallel and saves `results/forecasts/YYYY-MM.json`.
4. Builds the snapshots, evidence rules and reconciliation (`results/summary.json`) and writes `dashboard/studio-north-dashboard.html`.

## Repository layout

```
build_dashboard.py              command-line build
studio_dashboard/lab_source.py  pinned lab download / import
studio_dashboard/replay.py      as-of snapshots, refits, decision and evidence rules
studio_dashboard/template.html  dashboard page (vanilla HTML/SVG/JS)
dashboard/                      generated self-contained dashboard
results/forecasts/              one refit per as-of month (diagnostics, valuations, curves)
results/summary.json            first-support months, reconciliation, fit status
baseline/                       original report PDF and its saved tables (unchanged)
pyproject.toml, uv.lock         reproducible dependencies (same versions as the lab)
```

## Limitations

* Forecast bands reflect parameter uncertainty only (not renewal noise, future cost changes or regime change), exactly as in the report.
* The decision rule assumes additional customers are worth the benchmark cohort's average customer; it is a planning projection, not a
  measured causal lifetime return. Test spend and test customers are a separate research budget, excluded from company exhibits.
* The evidence rules are explicit, simple thresholds chosen to mirror the report's reasoning; other reasonable rules could date the evidence
  differently.
* Studio North is a fictional business with synthetic data.

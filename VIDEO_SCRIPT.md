# Demo video script (about 2 min 45 s)

## Map of the dashboard (top to bottom)

Panel titles below are written exactly as they appear on screen.

| Where on the page | Panel title on screen | What it shows |
|---|---|---|
| **Top bar** (stays visible when you scroll) | big month name, e.g. "Dec 2025" + **◀ Prev**, slider, **Next ▶**, **▶ Play** | the as-of month and the controls |
| Just below the controls | grey box starting with "**Observed data:** …" | what data is used, and whether the forecast was fitted or left blank |
| Row of 6 small boxes | "Active members", "Net revenue (month)", "Contribution (month)", "Acquisition spend (month)", "Newest cohort CAC", "Cohorts paid back (observed)" | headline numbers for that month |
| Row 1, left | **Contractual retention triangle** | blue grid of percentages: share of each cohort still subscribed by age |
| Row 1, right | **Company revenue, contribution and acquisition spend** | three lines over time (blue, green, orange) |
| Row 2, left (wide) | **12-receipt contribution LTV vs historical average CAC, per acquired customer** | one bar per cohort: solid blue = observed value, striped = forecast, black dash = CAC |
| Row 2, right | **Cash payback month** | dots: filled = observed payback, hollow ring = forecast |
| Row 3, left | **Cohort explorer** (with a "Cohort:" dropdown) | two small line charts for one cohort: cash after CAC and retention |
| Row 3, right | **Who joined: cohort mix by channel × stated need** | stacked colored bars (4 customer groups) |
| Row 4, left | **Acquisition decision: value vs incremental CAC** | a table with 4 rows and green / yellow / red badges |
| Row 4, right | **Same-age check: are newer cohorts better?** | a small table "Jan–Mar 2024" vs newer cohorts, with a rule badge |
| Row 5 (full width) | **When did the evidence first support the report's recommendation?** | 3 rows of small squares (blue = rule held that month) + a grey answer box |
| Bottom | **Reconciliation with the original report (as of December 2025)** | table of differences, badge "exact match" |

---

## Before recording

Open `dashboard/studio-north-dashboard.html` in Chrome or Edge, maximize the window, and set browser zoom to about 80–90% so two panels fit side by side.
Drag the slider all the way **left to "Jan 2024"** and scroll to the very top.
Record with **Win + Alt + R** (Xbox Game Bar) or OBS. Lines in *italics* are what you do; quoted lines are what you say.

---

### 0:00 – 0:20 · What this is
*Stay at the top of the page at **Jan 2024**. Circle the mouse around the big month name and the slider.*

> "This is a month-by-month replay of our Studio North customer-economics report. The question is the report's question:
> are we moving in the right direction as a company? The slider at the top sets the as-of month. At each month, every chart shows only
> what Studio North could have known by that month's end. Later months, and cohorts that hadn't joined yet, are hidden."

### 0:20 – 0:45 · How to use it
*Click **Next ▶** once (now "Feb 2024"). Point at the **grey "Observed data:" box** under the slider; it says "Forecast left blank".
Then press the **→ key** three times until the month reads **"May 2024"**, and point at the grey box again; it now says the model was refit.*

> "You can drag the slider, click Prev and Next, use the arrow keys, or press Play. This grey status box tells you what's behind the view.
> In January and February 2024 the forecast is blank. There isn't enough renewal history to fit the report's model, so we don't pretend.
> From March 2024 on, the model is refit every month using only the data available up to that month."

### 0:45 – 1:10 · Reading the panels
*Still at **May 2024**. Move the mouse over a few blue cells in **Contractual retention triangle** (row 1, left) so a tooltip appears.
Then scroll slightly and hover over a bar in **12-receipt contribution LTV vs historical average CAC** (row 2, left): point at the solid
blue part, the striped part and the black dash. Finally point at the dots in **Cash payback month** (row 2, right).*

> "The retention triangle shows what share of each joining cohort is still subscribed at each age. In the LTV chart, the solid blue part of
> each bar is contribution value we have already observed; the striped part is the model's forecast; and the black dash is what it cost to
> acquire each customer. In the payback chart, filled dots are paybacks we've actually seen and hollow rings are forecasts. Observed and
> forecast are always shown differently."

### 1:10 – 1:45 · The change that matters (1): newer cohorts get better
*Scroll down so **Same-age check: are newer cohorts better?** (row 4, right) and the timeline **When did the evidence first support…**
(row 5) are both visible. Press **→** until the top bar reads **"Oct 2024"**: the Same-age panel says "Fewer than three later cohorts…".
Press **→** once more to **"Nov 2024"**: the table appears and the badge turns green, "✓ newer cohorts better at the same age".
Point at the numbers in the table, then at the first **blue square** in the top row of the timeline.*

> "Here's the first change that matters for management. In November 2024, for the first time, the newest cohorts with six payments beat our
> first cohorts at the same age. Retention at age five rose from about 47 to 57 percent, and cash after acquisition cost went from minus
> 12 to plus 9 dollars per customer. As the timeline shows, that rule holds every month after. So the direction was clear more than a year
> before the report."

### 1:45 – 2:25 · The change that matters (2): where to spend the next dollar
*Keep **Acquisition decision: value vs incremental CAC** (row 4, left) and the timeline (row 5) on screen.
Drag the slider to **"Jun 2025"**: the decision panel says no holdout test has completed yet. Press **→** to **"Jul 2025"**: the 4-row table
appears. Press **→** until **"Oct 2025"**: point at the **"Search · build skill"** row (top) and the second timeline row turning blue.
Press **→** to **"Nov 2025"**: point at the table, where "Partner · build skill" is now on top, and the timeline square, which is empty again.
Press **→** to **"Dec 2025"**: point at the green **"✓ robust"** badge on Search · build skill and the third timeline row turning blue.*

> "The acquisition decision needs our randomized monthly holdout tests, which first completed in July 2025. In October, Search build-skill
> first looks like the best place for the next dollar, but in November another group briefly overtakes it, so the evidence isn't stable yet.
> Only in December does Search build-skill's value, about 284 dollars per customer, beat even the upper bound of its incremental acquisition
> cost. That's when our report recommends shifting budget there and not scaling the save-time campaigns. The lesson for management: keep
> the monthly tests running, because the spending recommendation depends on them."

### 2:25 – 2:45 · Trust and wrap-up
*Stay at **Dec 2025** and scroll to the bottom panel, **Reconciliation with the original report (as of December 2025)**. Point at the green
"exact match" badge.*

> "Finally, the December 2025 view reproduces our original report exactly; the differences are only rounding. The code, the data pipeline
> and every monthly refit are in our GitHub repository, so anyone can rebuild this dashboard. Thanks for watching."

---

**Timing tips:** if you run long, shorten the 0:45 section to one sentence. If you run short, scroll back to the top at the end, drag the
slider to Jan 2024 and press **▶ Play** to let it run through the months while you summarize.

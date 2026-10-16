# AI Inventory Planner — California Region

A Python inventory planning tool for a three-DC beverage distribution network in California (Fresno, San Jose and Riverside). It takes the RMS 10-day daily demand forecast, the current inventory snapshot, and days-on-hand (DOH) targets, then flags stock-out risk, recommends DC-to-DC transfers and purchase orders, scores vendors on confirmation rate, OTIF and lead time, and uses Claude (generative AI) to write the daily inventory update for leadership. Results are shown in an interactive dashboard.



## Features

* **Inputs from planning systems**
  * RMS daily demand forecast for the next 10 days, per SKU and DC
  * Current inventory: on hand and open purchase orders with arrival dates
  * DOH targets by SKU (3-gallon jugs: 14 days, all other SKUs: 2 days), kept in a config file
  * 13 weeks of purchase-order history: ordered, confirmed, promised and received
* **Days on hand (DOH)**, calculated by walking forward through the RMS daily forecast, so slow weekends are counted correctly
* **Projected end-of-day inventory** for 10 days, including open PO receipts
* **Status alerts against target**
  * Critical: stock-out before a PO placed today can arrive
  * Below target, above target (more than 2× target) and on target
* **Replenishment recommendations**
  * Order-up-to-target quantity that covers lead-time demand plus the target DOH
  * Vendor minimum order quantity (MOQ) and rounding rules
  * "Pull in open PO" when an existing PO lands after the stock-out day
* **Network rebalancing**: transfers stock a DC holds beyond its own target to a DC that is short on the same SKU, before any new PO is placed
* **Network DOH** per SKU with all DCs pooled
* **Vendor scorecard** from PO history
  * Confirmation rate, fill rate, on-time rate and OTIF (on time, in full)
  * Actual vs quoted lead time
  * OTIF trend: last 4 weeks vs the 9 before
  * Out-of-stock risk: today's critical positions on each vendor's SKUs
  * Status (at risk / watch / good) with the main driver in plain words, and a weekly OTIF trend chart
* **AI daily summary**: Claude writes a short leadership update from a fact sheet of KPIs, alerts, transfers and vendor performance (no raw data is sent), with a rule-based fallback when no API key is set
* **Interactive dashboard** with KPI tiles, an action list, a DOH heatmap by SKU and DC, daily forecast and projection charts, a vendor scorecard with weekly OTIF trend, and transfer recommendations

## Tech Stack

* Language: Python
* Data processing: pandas, NumPy
* Generative AI: Claude API (Anthropic)
* Dashboard: HTML, CSS, JavaScript, D3.js
* Inputs and outputs: CSV, JSON

## Project Structure

```
ai-inventory-planner/
├── data/
│   ├── generate_data.py          # creates synthetic sample inputs
│   ├── rms_forecast.csv          # RMS daily forecast, next 10 days
│   ├── inventory_snapshot.csv    # on hand + open POs
│   ├── doh_targets.csv           # target DOH per SKU
│   ├── sku_master.csv            # unit cost, vendor, lead time, MOQ
│   └── po_history.csv            # last 13 weeks of POs
├── src/
│   ├── planner.py                # DOH, projections, status, orders, transfers
│   ├── vendors.py                # vendor scorecard and weekly OTIF
│   └── ai_summary.py             # Claude summary + rule-based fallback
├── dashboard/
│   └── index.html                # dashboard page
├── outputs/                      # results written by the pipeline
├── run_pipeline.py               # daily planning run
├── export_dashboard_data.py      # data files for the dashboard
├── requirements.txt
└── README.md
```

## Setup Instructions

1. Clone the repository:

```
git clone <your-repository-url>
cd ai-inventory-planner
```

2. Create and activate a virtual environment:

```
python -m venv .venv
.venv\Scripts\activate
```

3. Install dependencies:

```
pip install -r requirements.txt
```

4. (Optional) Set your Claude API key so Claude writes the daily summary:

```
$env:ANTHROPIC_API_KEY="your-api-key"
```

5. Generate sample data and run the planner:

```
python data/generate_data.py
python run_pipeline.py
python export_dashboard_data.py
```

To use your own data, replace the five CSV files in `data/` with exports in the same columns and run `python run_pipeline.py`.

## Outputs

| File | What it contains |
|---|---|
| `outputs/planner_results.csv` | One row per SKU and DC: DOH, target, status, stock-out day, order quantity, transfers, action |
| `outputs/transfer_recommendations.csv` | Recommended DC-to-DC moves and PO spend avoided |
| `outputs/network_doh.csv` | Network DOH vs target per SKU |
| `outputs/vendor_scorecard.csv` | Per vendor: confirmation rate, on time, OTIF, lead time vs quote, trend, status, driver |
| `outputs/vendor_weekly.csv` | Weekly OTIF, on-time and confirmation rate per vendor |
| `outputs/kpis.json` | Headline metrics for the day |
| `outputs/daily_summary.md` | AI (or rule-based) daily summary |

## Sample Results

On the sample network (12 SKUs × 3 DCs, inventory as of Oct 15, 2026):

* 18 of 36 positions on target, 8 critical, 3 below target, 7 above target
* $12.6K of stock above target identified
* 3 transfers move 700 units between DCs and avoid $3,448 of new purchase orders
* 230 units recommended for purchase after transfers
* Vendor OTIF of 77.7% across 1,087 POs; 2 of 4 vendors at risk
  * One vendor short-confirmed 143 of 363 POs and supplies 3 of the 8 critical positions
  * The 3-gallon vendor's lead time runs 5.6 days vs 5 quoted, with OTIF down 22 points in 4 weeks

All data is synthetic; brands, SKUs, and volumes are invented.

## Resume Summary

Built an AI-assisted inventory planning tool in Python that uses a 10-day RMS daily forecast, current inventory, and SKU-level days-on-hand targets to flag stock-out risk, recommend purchase orders and DC-to-DC transfers, and rebalance stock across a 3-DC network. Added a vendor scorecard that tracks confirmation rate, OTIF, and actual vs quoted lead time from PO history and links vendor issues to out-of-stock risk. Integrated Claude (generative AI) to write the daily inventory update for leadership, and built an interactive dashboard showing DOH by SKU and DC, projected inventory, vendor performance, and recommended actions.

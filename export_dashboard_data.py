"""
Export the pipeline results as small flat files for the dashboard
(CSV/JSON row tables; each file is one data source on the page).

Run after run_pipeline.py:  python export_dashboard_data.py
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
OUT = ROOT / "outputs" / "dashboard"
OUT.mkdir(parents=True, exist_ok=True)
for old in OUT.iterdir():
    old.unlink()

d = json.loads((ROOT / "outputs" / "dashboard_data.json").read_text())
SEVERITY = {"CRITICAL": 0, "BELOW TARGET": 1, "ABOVE TARGET": 2, "ON TARGET": 3}

# 1. one row per SKU x DC position
pos = pd.DataFrame(d["positions"])
pos["severity_rank"] = pos["status"].map(SEVERITY)
pos["item"] = pos["description"]
keep = ["sku", "dc", "item", "dc_name", "category", "status", "severity_rank", "on_hand", "open_po_units",
        "open_po_day", "avg_daily_forecast", "forecast_10d", "doh", "target_doh", "target_units", "lead_time_days",
        "stockout_day", "order_qty", "transfer_in_qty", "transfer_from", "transfer_out_qty", "action",
        "on_hand_value", "excess_value", "reason"]
pos[keep].sort_values(["severity_rank", "stockout_day", "doh", "sku"]).to_csv(OUT / "positions.csv", index=False)

# 2. headline KPIs (one row)
(OUT / "kpis.json").write_text(json.dumps([d["kpis"]], indent=2))

# 3. daily series per position: RMS forecast, projected end-of-day inventory, PO receipts
rows = [{"sku": s["sku"], "dc": s["dc"], **day} for s in d["series"] for day in s["days"]]
pd.DataFrame(rows).to_csv(OUT / "daily.csv", index=False)

# 4. transfers
names = {p["dc"]: p["dc_name"] for p in d["positions"]}
items = {p["sku"]: p["description"] for p in d["positions"]}
tr = pd.DataFrame(d["transfers"])
if not tr.empty:
    tr.insert(1, "item", tr["sku"].map(items))
    tr["move"] = tr["sku"] + " " + tr["from_dc"] + "→" + tr["to_dc"]
tr.to_csv(OUT / "transfers.csv", index=False)

# 5. network DOH vs target per SKU
pd.DataFrame(d["network"]).to_csv(OUT / "network.csv", index=False)

# 6. vendor scorecard and weekly trend
pd.DataFrame(d["vendors"]).to_csv(OUT / "vendors.csv", index=False)
pd.DataFrame(d["vendor_weekly"]).to_csv(OUT / "vendor_weekly.csv", index=False)

# 7. AI summary (Claude-written example if present, else the pipeline's output)
claude = ROOT / "outputs" / "daily_summary_claude_example.md"
text, source = (claude.read_text(), "claude") if claude.exists() else (d["summary"], d["summary_source"])
(OUT / "summary.json").write_text(json.dumps([{"source": source, "text": text}], indent=2))

for f in sorted(OUT.iterdir()):
    print(f"{f.name:16s} {f.stat().st_size:>8,} bytes")

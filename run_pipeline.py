"""
Daily planning run.

Inputs (data/):
    rms_forecast.csv        RMS daily forecast, next 10 days, per SKU x DC
    inventory_snapshot.csv  on hand + open POs per SKU x DC
    doh_targets.csv         target days on hand per SKU (3-gallon 14, others 2)
    sku_master.csv          unit cost, vendor lead time (days), MOQ
    po_history.csv          last 13 weeks of POs (ordered, confirmed, promised, received)

Steps:
    1. DOH per position, walking forward through the RMS forecast
    2. Projected end-of-day inventory for 10 days, open POs included
    3. Status vs target (CRITICAL / BELOW / ABOVE / ON TARGET) and order-up-to-target qty
    4. Transfers from DCs above target to DCs short of the same SKU, before any PO
    5. Vendor scorecard: confirmation rate, on-time, OTIF, lead time vs quote, out-of-stock risk
    6. AI (or rule-based) summary
    7. CSV / JSON outputs for the dashboard

Run:  python run_pipeline.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.ai_summary import build_facts, generate_summary
from src.planner import Position, days_on_hand, describe_actions, evaluate, recommend_transfers
from src.vendors import network_totals, scorecard

ROOT = Path(__file__).parent
DATA, OUT = ROOT / "data", ROOT / "outputs"
DEFAULT_TARGET_DOH = 2


def main() -> None:
    OUT.mkdir(exist_ok=True)
    fc = pd.read_csv(DATA / "rms_forecast.csv", parse_dates=["forecast_date"])
    inv = pd.read_csv(DATA / "inventory_snapshot.csv", parse_dates=["snapshot_date", "open_po_eta"])
    skus = pd.read_csv(DATA / "sku_master.csv").set_index("sku")
    targets = pd.read_csv(DATA / "doh_targets.csv").set_index("sku")["target_doh"].to_dict()
    po_hist = pd.read_csv(DATA / "po_history.csv")

    snapshot = inv["snapshot_date"].max()
    dates = sorted(fc["forecast_date"].unique())

    results = []
    for _, row in inv.iterrows():
        sku, dc = row["sku"], row["dc"]
        f = (fc[(fc.sku == sku) & (fc.dc == dc)].sort_values("forecast_date")["forecast_units"]
             .to_numpy(dtype=float))
        po_day = int((row["open_po_eta"] - snapshot).days) if pd.notna(row["open_po_eta"]) else None
        meta = skus.loc[sku]
        pos = Position(sku=sku, dc=dc, on_hand=int(row["on_hand_units"]), open_po_units=int(row["open_po_units"]),
                       open_po_day=po_day, target_doh=float(targets.get(sku, DEFAULT_TARGET_DOH)),
                       lead_time_days=int(meta.lead_time_days), moq=int(meta.moq_units),
                       unit_cost=float(meta.unit_cost))
        r = evaluate(pos, f)
        r.update(description=meta.description, category=meta.category, vendor=meta.vendor, dc_name=row["dc_name"])
        results.append(r)

    transfers = recommend_transfers(results, skus["unit_cost"].to_dict())
    describe_actions(results, dict(zip(inv.dc, inv.dc_name)))

    res = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in results])
    counts = res["status"].value_counts()
    kpis = {
        "snapshot_date": snapshot.strftime("%Y-%m-%d"),
        "forecast_start": pd.Timestamp(dates[0]).strftime("%Y-%m-%d"),
        "forecast_end": pd.Timestamp(dates[-1]).strftime("%Y-%m-%d"),
        "positions_total": len(res),
        "on_target": int(counts.get("ON TARGET", 0)),
        "critical": int(counts.get("CRITICAL", 0)),
        "below_target": int(counts.get("BELOW TARGET", 0)),
        "above_target": int(counts.get("ABOVE TARGET", 0)),
        "on_hand_value": round(float(res["on_hand_value"].sum()), 2),
        "excess_value": round(float(res["excess_value"].sum()), 2),
        "order_units": int(res["order_qty"].sum()),
        "order_lines": int((res["order_qty"] > 0).sum()),
        "transfer_moves": len(transfers),
        "transfer_units": int(sum(t["units"] for t in transfers)),
        "po_value_avoided": round(sum(t["po_value_avoided"] for t in transfers), 2),
        **network_totals(po_hist),
    }
    vendors, vendor_weekly = scorecard(po_hist, skus, res, snapshot)
    kpis["vendors_at_risk"] = int((vendors.status == "AT RISK").sum())

    facts = build_facts(kpis, results, transfers, skus["description"].to_dict(), dict(zip(inv.dc, inv.dc_name)),
                        vendors)
    summary, source = generate_summary(facts)

    # network DOH per SKU vs target: all DCs pooled, same forward-walk DOH as each position
    network = []
    for sku in skus.index:
        rs = [r for r in results if r["sku"] == sku]
        pooled_fc = sum(r["_forecast"] for r in rs)
        pooled_oh = sum(r["on_hand"] for r in rs)
        network.append({"sku": sku, "item": skus.loc[sku, "description"],
                        "target_doh": float(targets.get(sku, DEFAULT_TARGET_DOH)),
                        "network_on_hand": int(pooled_oh),
                        "network_forecast_10d": int(pooled_fc.sum()),
                        "network_doh": round(days_on_hand(pooled_oh, pooled_fc), 1)})

    # ---- exports ----
    res.drop(columns=["projected"]).to_csv(OUT / "planner_results.csv", index=False)
    pd.DataFrame(transfers).to_csv(OUT / "transfer_recommendations.csv", index=False)
    pd.DataFrame(network).to_csv(OUT / "network_doh.csv", index=False)
    vendors.to_csv(OUT / "vendor_scorecard.csv", index=False)
    vendor_weekly.to_csv(OUT / "vendor_weekly.csv", index=False)
    (OUT / "kpis.json").write_text(json.dumps(kpis, indent=2))
    (OUT / "daily_summary.md").write_text(summary)
    series = [{"sku": r["sku"], "dc": r["dc"],
               "days": [{"date": pd.Timestamp(d).strftime("%Y-%m-%d"), "forecast": int(f), "projected": p,
                         "po_in": r["open_po_units"] if r["open_po_day"] == i + 1 else 0}
                        for i, (d, f, p) in enumerate(zip(dates, r["_forecast"], r["projected"]))]}
              for r in results]
    (OUT / "dashboard_data.json").write_text(json.dumps(
        {"kpis": kpis, "summary": summary, "summary_source": source, "network": network,
         "vendors": vendors.to_dict("records"), "vendor_weekly": vendor_weekly.to_dict("records"),
         "positions": res.to_dict("records"), "transfers": transfers, "series": series}, default=str))

    print(json.dumps(kpis, indent=2))
    print(f"\nSummary source: {source}\nOutputs written to {OUT}")


if __name__ == "__main__":
    main()

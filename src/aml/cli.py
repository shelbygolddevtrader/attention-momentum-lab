import argparse
from datetime import date
import json
from pathlib import Path
import sys
import pandas as pd
from aml.alpaca_rest import AlpacaREST
from aml.replay import replay_to_frame
from aml.reporting import price_chart, volume_chart
from aml.settings import Settings

def parser():
    p = argparse.ArgumentParser(description="Attention Momentum Lab")
    subs = p.add_subparsers(dest="command", required=True)
    subs.add_parser("check-account")
    for name in ("fetch", "replay", "demo"):
        q = subs.add_parser(name)
        q.add_argument("--symbol", required=True)
        q.add_argument("--date", required=True, type=date.fromisoformat)
    return p

def paths(symbol, day):
    symbol = symbol.upper()
    return (
        Path("data/raw") / symbol / f"{day}_alpaca_response.json",
        Path("data/processed") / symbol / f"{day}_1min.csv",
        Path("artifacts") / symbol / str(day),
    )

def fetch(client, symbol, day):
    raw, csv, _ = paths(symbol, day)
    raw.parent.mkdir(parents=True, exist_ok=True); csv.parent.mkdir(parents=True, exist_ok=True)
    payload, bars = client.get_minute_bars(symbol, day)
    raw.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    bars.to_csv(csv, index=False)
    print(f"Saved raw response: {raw}\nSaved minute bars: {csv}\nRows: {len(bars)}")
    return bars

def load(symbol, day):
    _, csv, _ = paths(symbol, day)
    if not csv.exists():
        raise RuntimeError(f"Missing {csv}; run fetch first")
    bars = pd.read_csv(csv)
    bars["timestamp"] = pd.to_datetime(bars["timestamp"])
    return bars

def replay(symbol, day, bars):
    _, _, out = paths(symbol, day)
    out.mkdir(parents=True, exist_ok=True)
    result = replay_to_frame(bars)
    result.to_csv(out / "replay_log.csv", index=False)
    price_chart(result, out / "price_replay.png")
    volume_chart(result, out / "volume_replay.png")
    summary = {
        "symbol": symbol.upper(), "date": str(day), "minutes_replayed": len(result),
        "eligible_minutes": int(result["eligible"].sum()),
        "maximum_score": int(result["score"].max()),
        "first_eligible_timestamp": str(result.loc[result["eligible"], "timestamp"].iloc[0]) if result["eligible"].any() else None,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Saved replay artifacts: {out}\n{json.dumps(summary, indent=2)}")

def main():
    args = parser().parse_args()
    try:
        client = AlpacaREST(Settings.from_env())
        if args.command == "check-account":
            account = client.get_paper_account()
            print("Paper account connection verified.")
            print(f"Status: {account.get('status')} | Currency: {account.get('currency')} | Equity: {account.get('equity')}")
            print("No order was submitted.")
        elif args.command == "fetch":
            fetch(client, args.symbol, args.date)
        elif args.command == "replay":
            replay(args.symbol, args.date, load(args.symbol, args.date))
        else:
            replay(args.symbol, args.date, fetch(client, args.symbol, args.date))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())

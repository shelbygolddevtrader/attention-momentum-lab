import argparse
from datetime import date
import json
import sys
from aml.alpaca_rest import AlpacaREST
from aml.data_paths import (
    HISTORICAL_DATA_FEED, RESEARCH_FEEDS, LEGACY_FEED, artifact_directory,
    feed_paths, load_bars,
)
from aml.replay import replay_to_frame
from aml.reporting import price_chart, volume_chart
from aml.settings import Settings
from aml.market_halts import CompletenessMode, completeness_metadata, load_verified_halts

def parser():
    p = argparse.ArgumentParser(description="Attention Momentum Lab")
    subs = p.add_subparsers(dest="command", required=True)
    subs.add_parser("check-account")
    for name in ("fetch", "replay", "demo"):
        q = subs.add_parser(name)
        q.add_argument("--symbol", required=True)
        q.add_argument("--date", required=True, type=date.fromisoformat)
        choices = (*RESEARCH_FEEDS, LEGACY_FEED) if name == "replay" else RESEARCH_FEEDS
        q.add_argument("--feed", choices=choices, default=HISTORICAL_DATA_FEED)
        if name in {"replay", "demo"}:
            q.add_argument("--completeness-mode", choices=[mode.value for mode in CompletenessMode], default=CompletenessMode.HALT_AWARE.value)
    return p

def paths(symbol, day, feed=HISTORICAL_DATA_FEED):
    """Compatibility wrapper returning feed-qualified raw/processed/artifact paths."""
    raw, processed, _, artifacts = feed_paths(symbol, day, feed)
    return raw, processed, artifacts

def fetch(client, symbol, day, feed=HISTORICAL_DATA_FEED):
    raw, csv, metadata_path, _ = feed_paths(symbol, day, feed)
    raw.parent.mkdir(parents=True, exist_ok=True)
    csv.parent.mkdir(parents=True, exist_ok=True)
    payload, bars = client.get_minute_bars(symbol, day, feed=feed)
    metadata = dict(payload["acquisition_metadata"])
    metadata.update(source_raw_file=str(raw), processed_file=str(csv))
    raw.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    bars.to_csv(csv, index=False)
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    raw_metadata = raw.with_name(raw.name.replace("_alpaca_response.json", "_metadata.json"))
    raw_metadata.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    bars.attrs.update(data_feed=feed, source_path=str(csv), acquisition_metadata=metadata)
    print(
        f"Requested feed: {feed}\nSaved raw response: {raw}\n"
        f"Saved minute bars: {csv}\nSaved metadata: {metadata_path}\nRows: {len(bars)}"
    )
    return bars

def load(symbol, day, feed=None):
    """Compatibility loader; an omitted feed reads legacy unsuffixed IEX data."""
    return load_bars(symbol, day, feed)

def replay(symbol, day, bars, feed=None, completeness_mode=CompletenessMode.HALT_AWARE):
    if feed is None:
        actual = bars.attrs.get("data_feed")
        feed = LEGACY_FEED if actual in {None, "legacy_iex"} else actual
    out = artifact_directory(symbol, day, feed)
    completeness_mode = CompletenessMode(completeness_mode)
    halts = load_verified_halts(symbol, day)
    out.mkdir(parents=True, exist_ok=True)
    result = replay_to_frame(bars)
    result.to_csv(out / "replay_log.csv", index=False)
    price_chart(result, out / "price_replay.png")
    volume_chart(result, out / "volume_replay.png")
    summary = {
        "symbol": symbol.upper(), "date": str(day), "minutes_replayed": len(result),
        "requested_feed": feed, "data_feed": bars.attrs.get("data_feed", feed),
        "source_path": bars.attrs.get("source_path"),
        **completeness_metadata(completeness_mode, halts),
        "eligible_minutes": int(result["eligible"].sum()),
        "maximum_score": int(result["score"].max()),
        "first_eligible_timestamp": str(result.loc[result["eligible"], "timestamp"].iloc[0]) if result["eligible"].any() else None,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(
        f"Replay feed: {summary['data_feed']}\nCompleteness mode: {completeness_mode.value}\n"
        f"Verified halts: {len(halts.records)}\nFull halt minutes excluded: "
        f"{summary['verified_halt_minutes_excluded']}\nSaved replay artifacts: {out}\n"
        f"{json.dumps(summary, indent=2)}"
    )

def main():
    args = parser().parse_args()
    try:
        if args.command == "check-account":
            client = AlpacaREST(Settings.from_env())
            account = client.get_paper_account()
            print("Paper account connection verified.")
            print(f"Status: {account.get('status')} | Currency: {account.get('currency')} | Equity: {account.get('equity')}")
            print("No order was submitted.")
        elif args.command == "fetch":
            client = AlpacaREST(Settings.from_env())
            fetch(client, args.symbol, args.date, args.feed)
        elif args.command == "replay":
            replay(args.symbol, args.date, load(args.symbol, args.date, args.feed), args.feed, args.completeness_mode)
        else:
            client = AlpacaREST(Settings.from_env())
            replay(
                args.symbol, args.date,
                fetch(client, args.symbol, args.date, args.feed), args.feed, args.completeness_mode,
            )
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())

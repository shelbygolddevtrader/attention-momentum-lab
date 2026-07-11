import argparse
import json
import math

import pandas as pd

from aml.trade_simulator import SimulationConfig, simulate_trades
from aml.data_paths import (
    HISTORICAL_DATA_FEED, LEGACY_FEED, RESEARCH_FEEDS, artifact_directory,
    load_bars, validate_replay_feed,
)


def main():
    parser = argparse.ArgumentParser(description="Run conservative historical trade simulation")
    parser.add_argument("symbol", nargs="?", default="GME")
    parser.add_argument("date", nargs="?", default="2024-05-13")
    parser.add_argument("--feed", choices=(*RESEARCH_FEEDS, LEGACY_FEED), default=HISTORICAL_DATA_FEED)
    args = parser.parse_args()
    symbol = args.symbol.upper()
    directory = artifact_directory(symbol, args.date, args.feed)
    validate_replay_feed(directory, args.feed)
    signals = pd.read_csv(directory / "replay_log.csv")
    bars = load_bars(symbol, args.date, args.feed)
    trades, summary = simulate_trades(signals, bars, SimulationConfig())
    trades.to_csv(directory / "simulated_trades.csv", index=False)
    serializable = {key: (None if isinstance(value, float) and math.isinf(value) else value) for key, value in summary.items()}
    (directory / "trade_summary.json").write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    print(trades.to_string(index=False))
    print(json.dumps(serializable, indent=2))


if __name__ == "__main__":
    main()

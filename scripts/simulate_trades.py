import argparse
import json
import math
from pathlib import Path

import pandas as pd

from aml.trade_simulator import SimulationConfig, simulate_trades


def main():
    parser = argparse.ArgumentParser(description="Run conservative historical trade simulation")
    parser.add_argument("symbol", nargs="?", default="GME")
    parser.add_argument("date", nargs="?", default="2024-05-13")
    args = parser.parse_args()
    symbol = args.symbol.upper()
    directory = Path("artifacts") / symbol / args.date
    signals = pd.read_csv(directory / "replay_log.csv")
    bars = pd.read_csv(Path("data/processed") / symbol / f"{args.date}_1min.csv")
    trades, summary = simulate_trades(signals, bars, SimulationConfig())
    trades.to_csv(directory / "simulated_trades.csv", index=False)
    serializable = {key: (None if isinstance(value, float) and math.isinf(value) else value) for key, value in summary.items()}
    (directory / "trade_summary.json").write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    print(trades.to_string(index=False))
    print(json.dumps(serializable, indent=2))


if __name__ == "__main__":
    main()

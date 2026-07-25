"""Verify a frozen Alpaca dataset and write its versioned manifest."""

import argparse
from pathlib import Path

from aml.dataset_manifest import build_dataset_manifest, write_manifest


DEFAULT_VINTAGE = "alpaca-sip-liquid-markets-2023-07-24_to_2026-07-23-v001"


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--root", type=Path, default=Path.cwd())
    value.add_argument("--dataset-vintage", default=DEFAULT_VINTAGE)
    value.add_argument("--universe", type=Path, default=Path("config/liquid_day_trading_universe_v001.csv"))
    value.add_argument("--start", default="2023-07-24")
    value.add_argument("--end", default="2026-07-23")
    value.add_argument("--source-commit", required=True)
    value.add_argument("--repository", default="https://github.com/shelbygolddevtrader/attention-momentum-lab")
    value.add_argument("--subscription-plan", default="Algo Trader Plus")
    value.add_argument("--subscription-price-usd", type=int, default=99)
    value.add_argument("--workers", type=int, default=4)
    value.add_argument(
        "--output", type=Path,
        default=Path("manifests/alpaca-sip-liquid-markets-2023-07-24_to_2026-07-23-v001.json"),
    )
    return value


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    universe = args.universe if args.universe.is_absolute() else root / args.universe
    output = args.output if args.output.is_absolute() else root / args.output
    manifest = build_dataset_manifest(
        root,
        dataset_vintage=args.dataset_vintage,
        universe_path=universe,
        source_commit=args.source_commit,
        repository=args.repository,
        start=args.start,
        end=args.end,
        subscription_plan=args.subscription_plan,
        subscription_price_usd_per_month=args.subscription_price_usd,
        workers=args.workers,
    )
    write_manifest(output, manifest)
    print(f"Manifest validation passed: {manifest['dataset_fingerprint_sha256']}")
    print(output.relative_to(root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

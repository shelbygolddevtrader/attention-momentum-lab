import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from aml.candidate_outcomes import analyze_candidate_outcomes
from aml.signals import SignalConfig
from aml.trade_simulator import SimulationConfig, simulate_trades

_SPEC = importlib.util.spec_from_file_location(
    "analyze_candidates", Path(__file__).parents[1] / "scripts" / "analyze_candidates.py"
)
_CLI = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_CLI)
parser = _CLI.parser
resolve_candidate_score_threshold = _CLI.resolve_candidate_score_threshold


def test_legacy_simulation_keyword_maps_to_execution_threshold():
    with pytest.deprecated_call(match="minimum_score"):
        config = SimulationConfig(minimum_score=75)
    assert config.eligible_score_threshold == 75


def test_conflicting_simulation_threshold_names_fail_clearly():
    with pytest.raises(ValueError, match="Conflicting.*eligible_score_threshold.*minimum_score"):
        SimulationConfig(eligible_score_threshold=70, minimum_score=55)


def test_legacy_signal_keyword_maps_to_canonical_threshold():
    with pytest.deprecated_call(match="eligible_score"):
        config = SignalConfig(eligible_score=75)
    assert config.eligible_score_threshold == 75


def test_conflicting_signal_threshold_names_fail_clearly():
    with pytest.raises(ValueError, match="Conflicting.*eligible_score_threshold.*eligible_score"):
        SignalConfig(eligible_score_threshold=70, eligible_score=55)


def test_legacy_cli_flag_selects_research_candidates_only():
    p = parser()
    args = p.parse_args(["TEST", "2024-01-02", "--minimum-score", "55"])
    threshold = resolve_candidate_score_threshold(p, args)
    timestamps = pd.date_range("2024-01-02 09:30", periods=6, freq="min", tz="America/New_York")
    replay = pd.DataFrame({
        "timestamp": timestamps, "symbol": "TEST", "price": 100.0,
        "high": 100.0, "low": 100.0, "score": [54, 55, 69, 70, 0, 0],
    })
    assert analyze_candidate_outcomes(replay, threshold)["score"].tolist() == [55, 69, 70]

    bars = pd.DataFrame({
        "timestamp": timestamps, "symbol": "TEST", "open": 100.0,
        "high": 100.0, "low": 100.0, "close": 100.0,
    })
    signals = replay[["timestamp", "symbol", "score"]]
    trades, _ = simulate_trades(signals, bars, SimulationConfig())
    assert trades["signal_score"].tolist() == [70]


def test_conflicting_cli_flags_exit_with_parser_error(capsys):
    p = parser()
    args = p.parse_args(["--candidate-score-threshold", "55", "--minimum-score", "60"])
    with pytest.raises(SystemExit):
        resolve_candidate_score_threshold(p, args)
    assert "conflicting thresholds" in capsys.readouterr().err

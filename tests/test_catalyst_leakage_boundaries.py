import ast
import hashlib
import json
from pathlib import Path

from aml.catalyst_observations import FORWARD_OUTCOME_FIELDS


ROOT = Path(__file__).parents[1]
V011_MODULES = (
    "src/aml/signals.py",
    "src/aml/tournament_strategies.py",
    "src/aml/trade_simulator.py",
    "src/aml/portfolio_simulator.py",
    "src/aml/batch_evaluation.py",
    "src/aml/forward_validation.py",
    "scripts/run_v011_forward_validation.py",
)
CATALYST_MODULES = (
    "src/aml/catalyst_observations.py",
    "src/aml/catalyst_storage.py",
    "src/aml/catalyst_collectors.py",
    "src/aml/experiment_registry.py",
    "src/aml/historical_catalyst_ingestion.py",
    "src/aml/historical_catalyst_providers.py",
)


def imported_modules(path):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_v011_execution_modules_do_not_import_catalyst_research():
    for relative in V011_MODULES:
        assert not any("catalyst" in name for name in imported_modules(relative)), relative


def test_catalyst_modules_do_not_import_execution_or_outcome_layers():
    prohibited = ("forward_validation", "replay", "signals", "trade_simulator", "tournament")
    for relative in CATALYST_MODULES:
        imports = imported_modules(relative)
        assert not any(token in name for name in imports for token in prohibited), relative


def test_catalyst_modules_have_no_network_clients():
    prohibited = {"requests", "urllib", "http.client", "socket", "aiohttp"}
    for relative in CATALYST_MODULES:
        assert prohibited.isdisjoint(imported_modules(relative)), relative


def test_operator_and_forward_validation_do_not_invoke_historical_ingestion():
    protected = (
        "scripts/run_v011_forward_validation.py",
        "src/aml/forward_validation.py",
    )
    for relative in protected:
        imports = imported_modules(relative)
        assert not any("historical_catalyst" in name for name in imports), relative


def test_historical_ingestion_cli_has_no_network_or_evaluation_commands():
    relative = "scripts/ingest_historical_catalysts.py"
    prohibited = {"requests", "urllib", "http.client", "socket", "aiohttp"}
    assert prohibited.isdisjoint(imported_modules(relative))
    source = (ROOT / relative).read_text(encoding="utf-8").casefold()
    assert "evaluate" not in source
    assert "alpaca" not in source
    assert "sec edgar" not in source


def test_synthetic_fixture_contains_no_forward_outcomes():
    fixture = json.loads(
        (ROOT / "tests/fixtures/catalysts/synthetic_story_v001.json").read_text()
    )
    normalized = {key.casefold().replace("-", "_") for key in fixture}
    assert normalized.isdisjoint(FORWARD_OUTCOME_FIELDS)


def test_forward_validation_operator_and_strategy_files_are_not_part_of_feature_diff():
    protected = {
        "src/aml/signals.py": "18d96dc38b1fc1be20412913e1367ded516ebb1a752babd5ef9217a09be476bf",
        "src/aml/tournament_strategies.py": "3dc2bdac1c90ad61936256f889c05cafae06863e2db39704f574a901c57ef07f",
        "src/aml/forward_validation.py": "6bf3fcdef1a136588bbb39c0276b4cacbe146464bff27c8e59fb89fb07b744a8",
        "scripts/run_v011_forward_validation.py": "db728af7dbe1a28a3212a3430863d9856dfcfbece95c1bae714f643ead1758ed",
    }
    for path, expected in protected.items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected

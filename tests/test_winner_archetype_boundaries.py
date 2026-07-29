import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).parents[1]
CLI = ROOT / "scripts/research_winner_archetypes.py"
SPEC = ROOT / "config/winner_archetype_experiment_v001.json"
ENVIRONMENT = os.environ.copy()
ENVIRONMENT["PYTHONPATH"] = str(ROOT / "src")


def command(*args):
    return [sys.executable, str(CLI), "--spec", str(SPEC), *args]


def test_cli_validation_and_synthetic_inspection_are_deterministic():
    for arguments in (
        ("validate-spec",),
        ("partition-plan", "--sessions", "60"),
        ("synthetic-outcome", "--case", "ambiguous"),
        ("synthetic-match",),
    ):
        first = subprocess.run(
            command(*arguments), cwd=ROOT, capture_output=True, text=True,
            check=True, env=ENVIRONMENT,
        )
        second = subprocess.run(
            command(*arguments), cwd=ROOT, capture_output=True, text=True,
            check=True, env=ENVIRONMENT,
        )
        assert first.stdout == second.stdout
        assert first.stderr == second.stderr == ""


def test_cli_identity_is_independent_of_spec_filename_and_working_directory(tmp_path):
    first_spec = tmp_path / "first-name.json"
    second_spec = tmp_path / "other-name.json"
    first_spec.write_bytes(SPEC.read_bytes())
    second_spec.write_bytes(SPEC.read_bytes())
    first = subprocess.run(
        [sys.executable, str(CLI), "--spec", str(first_spec), "validate-spec"],
        cwd=ROOT, capture_output=True, text=True, check=True, env=ENVIRONMENT,
    )
    second = subprocess.run(
        [sys.executable, str(CLI), "--spec", str(second_spec), "validate-spec"],
        cwd=tmp_path, capture_output=True, text=True, check=True, env=ENVIRONMENT,
    )
    assert first.stdout == second.stdout


def test_cli_validation_creates_no_bytecode_cache_or_output(tmp_path):
    isolated_source = tmp_path / "isolated-src"
    shutil.copytree(
        ROOT / "src/aml", isolated_source / "aml",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(isolated_source)
    environment.pop("PYTHONDONTWRITEBYTECODE", None)
    before = set(tmp_path.rglob("*"))
    subprocess.run(
        command("validate-spec"), cwd=tmp_path, capture_output=True,
        text=True, check=True, env=environment,
    )
    after = set(tmp_path.rglob("*"))
    assert list(isolated_source.rglob("__pycache__")) == []
    assert after == before


def test_cli_rejects_hypothesis_path_through_symlink(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    (target / "hypothesis.json").write_text("{}", encoding="utf-8")
    linked = tmp_path / "linked"
    try:
        linked.symlink_to(target, target_is_directory=True)
    except OSError:
        return
    result = subprocess.run(
        command("validate-hypothesis", str(linked / "hypothesis.json")),
        cwd=tmp_path, capture_output=True, text=True, env=ENVIRONMENT,
    )
    assert result.returncode != 0
    assert "symlink" in result.stderr


def test_research_layer_has_no_network_or_provider_dependency():
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT / "src/aml/winner_archetype.py",
            ROOT / "src/aml/winner_archetype_contracts.py",
            CLI,
        )
    ).casefold()
    for prohibited in (
        "import requests", "import httpx", "import socket", "alpaca",
        "download", "api_key", "live provider",
    ):
        assert prohibited not in sources


def test_production_modules_do_not_import_research_layer():
    protected = (
        "signals.py", "trade_simulator.py", "portfolio_simulator.py",
        "tournament_strategies.py", "tournament_runner.py", "forward_validation.py",
        "validation_extension.py",
    )
    for name in protected:
        source = (ROOT / "src/aml" / name).read_text(encoding="utf-8")
        assert "winner_archetype" not in source


def test_cli_has_no_real_study_or_mutating_command():
    source = CLI.read_text(encoding="utf-8")
    for prohibited in (
        'add_parser("run-study")', 'add_parser("download")',
        'add_parser("evaluate-strategy")', 'add_parser("publish")',
    ):
        assert prohibited not in source

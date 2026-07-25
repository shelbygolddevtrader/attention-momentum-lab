from datetime import date, datetime, timezone
import json
from pathlib import Path
import subprocess

import pytest

from aml.forward_validation import (
    BASELINE_COMMIT,
    DATASET_VINTAGE,
    ForwardValidationError,
    ForwardValidationPlan,
    RedactedProviderClient,
    build_preflight_plan,
    credential_presence,
    execute_acquisition,
    preflight_report,
    validate_acquisition_only_tokens,
    validate_date_range,
    verify_repository,
)
from aml.market_backfill import BackfillResult, BackfillTask, MarketInstrument
from aml.market_calendar import NonTradingSessionError
from aml.validation_extension import EXTENSION_END, EXTENSION_START, FROZEN_UNIVERSE
from scripts.run_v011_forward_validation import parser


ENVIRONMENT = {
    "ALPACA_API_KEY": "test-key-never-logged",
    "ALPACA_SECRET_KEY": "test-secret-never-logged",
    "ALPACA_HISTORICAL_DATA_FEED": "sip",
}


def completed_clock():
    return datetime(2026, 7, 28, tzinfo=timezone.utc)


class Schedule:
    calendar_id = "XNYS"

    def __init__(self, day):
        import pandas as pd

        self.open_timestamp = pd.Timestamp(f"{day} 09:30", tz="America/New_York")
        self.close_timestamp = pd.Timestamp(f"{day} 16:00", tz="America/New_York")
        self.expected_minutes = pd.date_range(
            self.open_timestamp, self.close_timestamp, inclusive="left", freq="min"
        )


class Calendar:
    def schedule(self, day, calendar_id):
        if day.weekday() >= 5:
            raise NonTradingSessionError("closed")
        return Schedule(day)


def _universe(root: Path) -> Path:
    path = root / "config" / "liquid_day_trading_universe_v001.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "symbol,market,category,notes\n"
        + "".join(f"{symbol},market,category,notes\n" for symbol in FROZEN_UNIVERSE),
        encoding="utf-8",
    )
    return path


def _plan(root: Path, control_root: Path | None = None) -> ForwardValidationPlan:
    universe = _universe(root)
    instrument = MarketInstrument("SPY", "market", "category", "notes")
    return ForwardValidationPlan(
        root=root,
        start=EXTENSION_START,
        end=EXTENSION_START,
        source_commit="a" * 40,
        universe_path=universe,
        control_root=control_root or root / "artifacts" / "forward_validation" / "sealed",
        sessions=(EXTENSION_START,),
        tasks=(BackfillTask(instrument, EXTENSION_START),),
    )


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (date(2026, 7, 26), EXTENSION_START),
        (EXTENSION_START, date(2028, 7, 27)),
        (date(2026, 7, 28), EXTENSION_START),
    ],
)
def test_invalid_or_out_of_boundary_dates_fail_closed(start, end):
    with pytest.raises(ForwardValidationError):
        validate_date_range(start, end)
    validate_date_range(EXTENSION_START, EXTENSION_END)


def test_cli_rejects_malformed_dates_and_defaults_to_no_acquisition():
    with pytest.raises(SystemExit):
        parser().parse_args(["--start", "not-a-date", "--end", "2026-07-27"])
    args = parser().parse_args(["--start", "2026-07-27", "--end", "2026-07-27"])
    assert args.execute_acquisition is False


def test_missing_credentials_and_wrong_feed_fail_without_echoing_values():
    with pytest.raises(ForwardValidationError, match="ALPACA_SECRET_KEY") as missing:
        from aml.forward_validation import verify_credentials

        verify_credentials({"ALPACA_API_KEY": "do-not-echo"})
    assert "do-not-echo" not in str(missing.value)
    with pytest.raises(ForwardValidationError, match="SIP"):
        verify_credentials({**ENVIRONMENT, "ALPACA_HISTORICAL_DATA_FEED": "iex"})


def test_credential_status_and_report_never_contain_secret_values(tmp_path):
    plan = _plan(tmp_path)
    payload = json.dumps({
        "credentials": credential_presence(ENVIRONMENT),
        "preflight": preflight_report(plan),
    })
    assert credential_presence(ENVIRONMENT) == {
        "ALPACA_API_KEY": True,
        "ALPACA_SECRET_KEY": True,
    }
    assert ENVIRONMENT["ALPACA_API_KEY"] not in payload
    assert ENVIRONMENT["ALPACA_SECRET_KEY"] not in payload


def test_repository_requires_clean_expected_baseline_descendant(monkeypatch, tmp_path):
    responses = {
        ("rev-parse", "--show-toplevel"): str(tmp_path.resolve()),
        ("status", "--porcelain"): " M README.md",
    }
    monkeypatch.setattr(
        "aml.forward_validation._git", lambda root, *args: responses[args]
    )
    with pytest.raises(ForwardValidationError, match="clean"):
        verify_repository(tmp_path)

    responses[("status", "--porcelain")] = ""
    responses[("rev-parse", "v0.1.1-research-baseline^{}")] = "b" * 40
    with pytest.raises(ForwardValidationError, match="baseline tag"):
        verify_repository(tmp_path)

    responses[("rev-parse", "v0.1.1-research-baseline^{}")] = BASELINE_COMMIT

    def not_ancestor(root, *args):
        if args[0] == "merge-base":
            raise subprocess.CalledProcessError(1, "git")
        return responses[args]

    monkeypatch.setattr("aml.forward_validation._git", not_ancestor)
    with pytest.raises(ForwardValidationError, match="not descended"):
        verify_repository(tmp_path)


def test_network_free_preflight_uses_no_client_and_produces_no_results(
    monkeypatch, tmp_path
):
    def network_forbidden(*args, **kwargs):
        raise AssertionError("preflight attempted a network request")

    monkeypatch.setattr("requests.get", network_forbidden)
    universe = _universe(tmp_path)
    plan = build_preflight_plan(
        tmp_path,
        start=EXTENSION_START,
        end=EXTENSION_START,
        environment=ENVIRONMENT,
        calendar=Calendar(),
        universe=universe,
        require_clean_repository=False,
        source_commit="a" * 40,
    )
    report = preflight_report(plan)
    assert report["network_requests_performed"] == 0
    assert report["market_data_fetched"] is False
    assert report["strategy_replay_performed"] is False
    assert report["strategy_results_generated"] is False
    assert not (tmp_path / "data").exists()
    assert not (tmp_path / "artifacts").exists()


def test_partial_raw_data_and_manifest_overwrite_are_rejected(tmp_path):
    universe = _universe(tmp_path)
    plan = build_preflight_plan(
        tmp_path,
        start=EXTENSION_START,
        end=EXTENSION_START,
        environment=ENVIRONMENT,
        calendar=Calendar(),
        universe=universe,
        require_clean_repository=False,
        source_commit="a" * 40,
    )
    schedule = Calendar().schedule(EXTENSION_START, "XNYS")
    from aml.research_acquisition import requests_for_session, research_segment_paths

    request = requests_for_session("SPY", EXTENSION_START, schedule, DATASET_VINTAGE)[0]
    paths = research_segment_paths(tmp_path, request)
    paths.raw_response.parent.mkdir(parents=True)
    paths.raw_response.write_text("partial", encoding="utf-8")
    with pytest.raises(ForwardValidationError, match="Incomplete write-once"):
        build_preflight_plan(
            tmp_path,
            start=EXTENSION_START,
            end=EXTENSION_START,
            environment=ENVIRONMENT,
            calendar=Calendar(),
            universe=universe,
            require_clean_repository=False,
            source_commit="a" * 40,
        )

    paths.raw_response.unlink()
    plan.sealed_directory.mkdir(parents=True)
    plan.manifest_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ForwardValidationError, match="different identity"):
        execute_acquisition(
            plan, client=object(), calendar=Calendar(), clock=completed_clock
        )


def test_finalized_artifact_collisions_and_result_operations_are_rejected(tmp_path):
    universe = _universe(tmp_path)
    with pytest.raises(ForwardValidationError, match="finalized"):
        build_preflight_plan(
            tmp_path,
            start=EXTENSION_START,
            end=EXTENSION_START,
            environment=ENVIRONMENT,
            calendar=Calendar(),
            universe=universe,
            control_root=tmp_path / "artifacts" / "tournaments" / "run" / "final",
            require_clean_repository=False,
            source_commit="a" * 40,
        )
    for tokens in (
        ["--replay"], ["--run-analysis"], ["--include-holdout"], ["results.csv"],
    ):
        with pytest.raises(ForwardValidationError, match="cannot invoke"):
            validate_acquisition_only_tokens(tokens)


def test_absolute_parent_traversal_and_component_substitution_paths_fail(tmp_path):
    universe = _universe(tmp_path)
    unsafe = (
        Path("artifacts/../escape"),
        tmp_path.parent / "outside-repository",
        tmp_path / "artifacts" / "final_artifacts",
        tmp_path / "artifacts" / "sealed.holdout.copy",
    )
    for control_root in unsafe:
        with pytest.raises(ForwardValidationError):
            build_preflight_plan(
                tmp_path,
                start=EXTENSION_START,
                end=EXTENSION_START,
                environment=ENVIRONMENT,
                calendar=Calendar(),
                universe=universe,
                control_root=control_root,
                require_clean_repository=False,
                source_commit="a" * 40,
            )


def test_symlinked_control_manifest_and_audit_paths_fail_closed(tmp_path):
    universe = _universe(tmp_path)
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    linked = tmp_path / "linked-control"
    try:
        linked.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are unavailable")
    with pytest.raises((ForwardValidationError, ValueError), match="Symlinked"):
        build_preflight_plan(
            tmp_path,
            start=EXTENSION_START,
            end=EXTENSION_START,
            environment=ENVIRONMENT,
            calendar=Calendar(),
            universe=universe,
            control_root=linked,
            require_clean_repository=False,
            source_commit="a" * 40,
        )

    plan = _plan(tmp_path / "files")
    plan.sealed_directory.mkdir(parents=True)
    target = tmp_path / "target"
    target.write_text("{}\n", encoding="utf-8")
    plan.manifest_path.symlink_to(target)
    with pytest.raises(ForwardValidationError, match="non-symlink"):
        execute_acquisition(
            plan, client=object(), calendar=Calendar(), clock=completed_clock
        )

    plan.manifest_path.unlink()
    plan.manifest_path.write_text(
        json.dumps(plan.identity, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    plan.audit_path.symlink_to(target)
    with pytest.raises(ForwardValidationError, match="non-symlink"):
        execute_acquisition(
            plan, client=object(), calendar=Calendar(), clock=completed_clock
        )


def test_manifest_identity_and_audit_schema_are_deterministic(monkeypatch, tmp_path):
    plan = _plan(tmp_path)
    same = _plan(tmp_path / "equivalent")
    assert plan.request_id == same.request_id
    assert plan.identity == same.identity

    monkeypatch.setattr(
        "aml.forward_validation.run_task",
        lambda *args, **kwargs: BackfillResult(
            "SPY", EXTENSION_START, 2, 0, "completed"
        ),
    )
    execute_acquisition(
        plan, client=object(), calendar=Calendar(), clock=completed_clock
    )
    execute_acquisition(
        same, client=object(), calendar=Calendar(), clock=completed_clock
    )
    assert plan.manifest_path.read_bytes() == same.manifest_path.read_bytes()
    assert plan.audit_path.read_bytes() == same.audit_path.read_bytes()
    assert plan.manifest_path.read_bytes().endswith(b"\n")
    assert json.loads(plan.manifest_path.read_text()) == plan.identity
    lines = plan.audit_path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["event"] for line in lines] == [
        "acquisition_started", "partition_processed", "acquisition_finished",
    ]
    records = [json.loads(line) for line in lines]
    assert [record["sequence"] for record in records] == [1, 2, 3]
    assert records[1]["previous_record_sha256"] == records[0]["record_sha256"]
    assert records[2]["previous_record_sha256"] == records[1]["record_sha256"]
    assert all("test-key" not in line and "test-secret" not in line for line in lines)
    assert not any(
        token in line for line in lines for token in ("net_pnl", "win_rate", "trades")
    )


def test_existing_result_like_file_blocks_resume_before_client_use(tmp_path):
    plan = _plan(tmp_path)
    plan.sealed_directory.mkdir(parents=True)
    (plan.sealed_directory / "results.csv").write_text("forbidden\n", encoding="utf-8")
    with pytest.raises(ForwardValidationError, match="result-like"):
        execute_acquisition(
            plan, client=object(), calendar=Calendar(), clock=completed_clock
        )


def test_report_or_manifest_inside_dataset_vintage_blocks_acquisition(tmp_path):
    universe = _universe(tmp_path)
    dataset = tmp_path / "data" / "research" / DATASET_VINTAGE
    dataset.mkdir(parents=True)
    (dataset / "performance_summary.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(ForwardValidationError, match="report, manifest, or result"):
        build_preflight_plan(
            tmp_path,
            start=EXTENSION_START,
            end=EXTENSION_START,
            environment=ENVIRONMENT,
            calendar=Calendar(),
            universe=universe,
            require_clean_repository=False,
            source_commit="a" * 40,
        )


def test_live_acquisition_rejects_future_or_incomplete_session(tmp_path):
    plan = _plan(tmp_path)

    def before_close():
        return datetime(2026, 7, 27, 18, 0, tzinfo=timezone.utc)

    with pytest.raises(ForwardValidationError, match="incomplete or future"):
        execute_acquisition(
            plan, client=object(), calendar=Calendar(), clock=before_close
        )
    assert not plan.sealed_directory.exists()


def test_orphaned_or_mutated_audit_log_blocks_resume(monkeypatch, tmp_path):
    plan = _plan(tmp_path)
    plan.sealed_directory.mkdir(parents=True)
    plan.audit_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ForwardValidationError, match="without its request manifest"):
        execute_acquisition(
            plan, client=object(), calendar=Calendar(), clock=completed_clock
        )

    plan.audit_path.unlink()
    monkeypatch.setattr(
        "aml.forward_validation.run_task",
        lambda *args, **kwargs: BackfillResult(
            "SPY", EXTENSION_START, 2, 0, "completed"
        ),
    )
    execute_acquisition(
        plan, client=object(), calendar=Calendar(), clock=completed_clock
    )
    original = plan.audit_path.read_text(encoding="utf-8")
    plan.audit_path.write_text(original.replace("acquisition_started", "acquisition_finished", 1))
    with pytest.raises(ForwardValidationError, match="schema|hash|chain"):
        execute_acquisition(
            plan, client=object(), calendar=Calendar(), clock=completed_clock
        )


def test_interrupted_acquisition_appends_a_hash_chained_resume(monkeypatch, tmp_path):
    plan = _plan(tmp_path)

    def interrupt(*args, **kwargs):
        raise RuntimeError("synthetic interruption")

    monkeypatch.setattr("aml.forward_validation.run_task", interrupt)
    with pytest.raises(ForwardValidationError, match="Acquisition failed"):
        execute_acquisition(
            plan, client=object(), calendar=Calendar(), clock=completed_clock
        )
    manifest_before = plan.manifest_path.read_bytes()

    monkeypatch.setattr(
        "aml.forward_validation.run_task",
        lambda *args, **kwargs: BackfillResult(
            "SPY", EXTENSION_START, 2, 0, "completed"
        ),
    )
    execute_acquisition(
        plan, client=object(), calendar=Calendar(), clock=completed_clock
    )
    assert plan.manifest_path.read_bytes() == manifest_before
    records = [json.loads(line) for line in plan.audit_path.read_text().splitlines()]
    assert [record["event"] for record in records] == [
        "acquisition_started", "acquisition_failed", "acquisition_started",
        "partition_processed", "acquisition_finished",
    ]
    assert [record["sequence"] for record in records] == [1, 2, 3, 4, 5]


def test_prior_failure_status_fails_the_live_wrapper(monkeypatch, tmp_path):
    plan = _plan(tmp_path)
    monkeypatch.setattr(
        "aml.forward_validation.run_task",
        lambda *args, **kwargs: BackfillResult(
            "SPY", EXTENSION_START, 0, 0, "failed", "secret path not logged"
        ),
    )
    with pytest.raises(ForwardValidationError, match="remains failed") as failure:
        execute_acquisition(
            plan, client=object(), calendar=Calendar(), clock=completed_clock
        )
    assert "secret path" not in str(failure.value)
    assert "secret path" not in plan.audit_path.read_text(encoding="utf-8")


def test_provider_exception_secrets_are_redacted_from_files_logs_and_terminal(tmp_path):
    plan = _plan(tmp_path)
    secret_key = "secret-like-key-material"
    secret_value = "secret-like-secret-material"

    class LeakyClient:
        def get_bars_range(self, *args, **kwargs):
            error = RuntimeError(f"request leaked {secret_key} and {secret_value}")
            error.partial_payload = {
                "message": f"provider echoed {secret_key}",
                secret_value: "unsafe-key",
            }
            raise error

    client = RedactedProviderClient(LeakyClient(), (secret_key, secret_value))
    with pytest.raises(ForwardValidationError, match="Acquisition failed") as failure:
        execute_acquisition(
            plan, client=client, calendar=Calendar(), clock=completed_clock
        )
    assert failure.value.__cause__ is None
    all_text = str(failure.value) + plan.audit_path.read_text(encoding="utf-8")
    for path in (tmp_path / "data").rglob("*"):
        if path.is_file():
            all_text += path.read_text(encoding="utf-8")
    assert secret_key not in all_text
    assert secret_value not in all_text
    assert "[REDACTED]" in all_text

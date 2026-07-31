from __future__ import annotations

from copy import deepcopy

from aml.professional_strategy_olympics_input_manifest_v003 import (
    CONTRACT_IDENTITY,
    SCHEMA,
    VERSION,
    V002_CONTRACT_IDENTITY,
    V003_ADAPTER_CONTRACT_IDENTITY,
    manifest_identity,
    project_to_v002,
)
from aml.professional_strategy_olympics_orchestrator_input_adapter_v003 import (
    adapter_implementation_identity,
)

from olympics_v002_test_support import ROOT, make_manifest, reidentify


def make_v003_manifest(*, with_trades: bool = True) -> dict[str, object]:
    value = make_manifest(with_trades=with_trades)
    value["schema_name"] = SCHEMA
    value["schema_version"] = VERSION
    value["v002_contract_identity"] = V002_CONTRACT_IDENTITY
    value["v003_contract_identity"] = CONTRACT_IDENTITY
    value["v003_adapter_contract_identity"] = V003_ADAPTER_CONTRACT_IDENTITY
    value["v003_adapter_implementation_identity"] = adapter_implementation_identity(ROOT)
    value["manifest_identity"] = manifest_identity(value)
    return value


def reidentify_v003(value: dict[str, object]) -> dict[str, object]:
    result = deepcopy(value)
    inherited = reidentify(project_to_v002(result))
    result["entrants"] = inherited["entrants"]
    result["fixture_identity"] = inherited["fixture_identity"]
    result["manifest_identity"] = manifest_identity(result)
    return result

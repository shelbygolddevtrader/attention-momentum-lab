"""Named score thresholds shared by research and execution code."""

import warnings

CANDIDATE_SCORE_THRESHOLD = 55
ELIGIBLE_SCORE_THRESHOLD = 70

UNSET_THRESHOLD = object()


def resolve_deprecated_threshold_alias(canonical, legacy, default, canonical_name, legacy_name):
    """Resolve a deprecated keyword alias while detecting explicit conflicts."""
    if canonical is not UNSET_THRESHOLD and legacy is not UNSET_THRESHOLD and canonical != legacy:
        raise ValueError(
            f"Conflicting threshold values: {canonical_name}={canonical} and "
            f"deprecated {legacy_name}={legacy}"
        )
    if legacy is not UNSET_THRESHOLD:
        warnings.warn(
            f"{legacy_name} is deprecated; use {canonical_name}",
            DeprecationWarning,
            stacklevel=3,
        )
        return legacy
    return default if canonical is UNSET_THRESHOLD else canonical

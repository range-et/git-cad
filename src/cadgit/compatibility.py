"""Additive format compatibility, independent of the application's package version."""

from typing import cast

from .errors import CadgitError

FORMAT_MAJOR = 1
FORMAT_MINOR = 0
# Future releases register semantics they can safely execute here. Optional
# extensions do not need a feature gate; behavior-changing requirements do.
MATERIAL_LIBRARY_FEATURE = "cadgit.material-library.v1"
BREP_JOB_FEATURE = "cadgit.brep-job.v1"
SUPPORTED_FEATURES = frozenset({MATERIAL_LIBRARY_FEATURE, BREP_JOB_FEATURE})


def check_compatibility(
    data: object, context: str = "record", legacy: bool = False
) -> None:
    if not isinstance(data, dict):
        raise CadgitError(f"{context}: expected a JSON object")
    data = cast(dict[str, object], data)
    major = data.get("schema_version", FORMAT_MAJOR if legacy else None)
    minor = data.get("schema_minor", 0)
    if type(major) is not int or major != FORMAT_MAJOR:
        raise CadgitError(
            f"{context}: unsupported schema version {major!r}; this release supports major {FORMAT_MAJOR}. Original data was not migrated."
        )
    if type(minor) is not int or minor < 0:
        raise CadgitError(f"{context}: invalid schema_minor {minor!r}")
    required = data.get("required_features", [])
    if not isinstance(required, list) or any(
        not isinstance(feature, str) for feature in required
    ):
        raise CadgitError(
            f"{context}: required_features must be a list of feature identifiers"
        )
    unsupported = set(required) - SUPPORTED_FEATURES
    if unsupported:
        raise CadgitError(
            f"{context}: requires unsupported features: {', '.join(sorted(unsupported))}. Upgrade Git CAD to use this data."
        )

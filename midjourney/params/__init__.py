"""Parameter system for Midjourney API.

Provides version-specific parameter classes via the create_params() factory.
"""

from __future__ import annotations

from midjourney.params.base import BaseParams
from midjourney.params.v7 import V7Params

_VERSION_MAP: dict[int, type[BaseParams]] = {
    7: V7Params,
}


def create_params(version: int = 7, **kwargs) -> BaseParams:
    """Factory function to create version-specific parameters.

    Args:
        version: Midjourney model version (currently only 7).
        **kwargs: Version-specific parameters (prompt, ar, stylize, etc.).

    Returns:
        A parameter object for the specified version.

    Raises:
        ValueError: If the version is not supported.
    """
    cls = _VERSION_MAP.get(version)
    if cls is None:
        supported = ", ".join(str(v) for v in sorted(_VERSION_MAP))
        raise ValueError(f"Unsupported version {version}. Supported: {supported}")
    return cls(**kwargs)

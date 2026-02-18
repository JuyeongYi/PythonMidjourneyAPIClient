"""Parameter system for Midjourney API.

Provides version-specific parameter classes via the create_params() factory.
Raw values (int, str, bool) are automatically cast to typed parameters.
"""

from __future__ import annotations

from midjourney_api.params.base import BaseParams
from midjourney_api.params.types import Version
from midjourney_api.params.v7 import V7Params

_VERSION_MAP: dict[int, type[BaseParams]] = {
    7: V7Params,
}


def create_params(version: int = 7, **kwargs) -> BaseParams:
    """Factory function to create version-specific parameters.

    Accepts raw values (int, str, bool) and casts them to typed parameters
    via the class's _CAST_MAP before constructing.

    Args:
        version: Midjourney model version (currently only 7).
        **kwargs: Version-specific parameters (prompt, ar, stylize, etc.).

    Returns:
        A parameter object for the specified version.

    Raises:
        ValidationError: If version or parameter values are invalid.
    """
    v = Version(version)
    cls = _VERSION_MAP.get(v)
    if cls is None:
        supported = ", ".join(str(v) for v in sorted(_VERSION_MAP))
        raise ValueError(f"Unsupported version {version}. Supported: {supported}")

    cast_map = getattr(cls, "_CAST_MAP", {})
    for key, typ in cast_map.items():
        if key in kwargs and kwargs[key] is not None:
            kwargs[key] = typ(kwargs[key])

    return cls(**kwargs)

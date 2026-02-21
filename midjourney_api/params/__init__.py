"""Midjourney API 파라미터 시스템.

create_params() 팩토리를 통해 버전별 파라미터 클래스를 제공합니다.
원시 값(int, str, bool)은 자동으로 타입 파라미터로 캐스팅됩니다.
"""

from __future__ import annotations

from midjourney_api.params.base import BaseParams
from midjourney_api.params.types import Version
from midjourney_api.params.v7 import V7Params

_VERSION_MAP: dict[int, type[BaseParams]] = {
    7: V7Params,
}


def create_params(version: int = 7, **kwargs) -> BaseParams:
    """버전별 파라미터를 생성하는 팩토리 함수.

    클래스의 _CAST_MAP을 통해 원시 값(int, str, bool)을 타입 파라미터로
    자동 캐스팅한 후 생성합니다.

    매개변수:
        version: Midjourney 모델 버전 (현재 7만 지원).
        **kwargs: 버전별 파라미터 (prompt, ar, stylize 등).

    반환값:
        지정된 버전의 파라미터 객체.

    예외:
        ValidationError: 버전 또는 파라미터 값이 유효하지 않은 경우.
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

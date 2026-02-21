"""Midjourney 파라미터 타입 — 유효성 검사 및 프롬프트 생성 내장.

각 타입은 기본 타입(int, str, float)과 MJParam을 함께 상속하여
기존 코드와 완전 호환되면서 to_prompt()를 추가합니다.
유효성 검사는 __new__에서 생성 시점에 수행됩니다.
"""

from __future__ import annotations

import re
from enum import StrEnum

from midjourney_api.exceptions import ValidationError


# -- 버전 ------------------------------------------------------------------

class Version(int):
    """Midjourney 모델 버전."""

    _flag = "--v"
    _supported = {6, 7}

    def __new__(cls, value: int):
        value = int(value)
        if value not in cls._supported:
            supported = ", ".join(str(v) for v in sorted(cls._supported))
            raise ValidationError(
                f"version must be one of [{supported}], got {value}"
            )
        return int.__new__(cls, value)

    def to_prompt(self) -> str:
        return f"{self._flag} {self}"


# -- 인터페이스 ----------------------------------------------------------------

class MJParam:
    """모든 파라미터에 CLI 플래그와 프롬프트 조각을 부여하는 믹스인."""
    _flag: str

    def to_prompt(self, version: Version) -> str:
        if version == 7:
            return f"{self._flag} {self}"
        return f"{self._flag} {self}"


# -- 기본 헬퍼 -------------------------------------------------------------

class _Flag(MJParam, int):
    """int로 구현된 bool 유사 플래그 (bool은 서브클래싱 불가).

    int 값(0 또는 1)으로 참/거짓. to_prompt()는 플래그만 반환합니다.
    """

    def __new__(cls, value=False):
        return int.__new__(cls, bool(value))

    def __bool__(self):
        return int.__ne__(self, 0)

    def __repr__(self):
        return f"{type(self).__name__}({bool(self)})"

    def to_prompt(self, version: Version) -> str:
        if version == 7:
            return self._flag
        return self._flag


class _RangeInt(MJParam, int):
    """[_min, _max] 범위로 제한된 int."""
    _min: int
    _max: int
    _name: str

    def __new__(cls, value: int):
        value = int(value)
        if not cls._min <= value <= cls._max:
            raise ValidationError(
                f"{cls._name} must be {cls._min}-{cls._max}, got {value}"
            )
        return int.__new__(cls, value)


class _RangeFloat(MJParam, float):
    """[_min, _max] 범위로 제한된 float."""
    _min: float
    _max: float
    _name: str

    def __new__(cls, value: float):
        value = float(value)
        if not cls._min <= value <= cls._max:
            raise ValidationError(
                f"{cls._name} must be {cls._min}-{cls._max}, got {value}"
            )
        return float.__new__(cls, value)


# -- 문자열 타입 -------------------------------------------------------------

class AspectRatio(MJParam, str):
    """w:h 형식의 화면 비율 (예: '16:9')."""
    _flag = "--ar"

    def __new__(cls, value: str):
        if not re.match(r"^\d+:\d+$", value):
            raise ValidationError(f"ar must be w:h format, got '{value}'")
        return str.__new__(cls, value)


class Personalize(MJParam, str):
    """개인화 — 코드 또는 빈 문자열 (플래그만)."""
    _flag = "--p"

    def __new__(cls, value: str = ""):
        return str.__new__(cls, value)

    def to_prompt(self, version: Version) -> str:
        if version == 7:
            return f"{self._flag} {self}" if self else self._flag
        return f"{self._flag} {self}" if self else self._flag


class StyleRef(MJParam, str):
    """스타일 참조 — URL 또는 스타일 코드. 유효성 검사 없음."""
    _flag = "--sref"

    def __new__(cls, value: str):
        return str.__new__(cls, value)


class OmniRef(MJParam, str):
    """오브젝트/캐릭터 참조 — 이미지 URL이어야 함 (코드 불가)."""
    _flag = "--oref"

    def __new__(cls, value: str):
        if not value.startswith(("http://", "https://")):
            raise ValidationError(
                f"oref must be an image URL (not a code), got '{value}'"
            )
        return str.__new__(cls, value)


# -- Int 타입 ----------------------------------------------------------------

class Stylize(_RangeInt):
    _flag = "--s"
    _min, _max, _name = 0, 1000, "stylize"


class Chaos(_RangeInt):
    _flag = "--c"
    _min, _max, _name = 0, 100, "chaos"


class Weird(_RangeInt):
    _flag = "--w"
    _min, _max, _name = 0, 3000, "weird"


class Stop(_RangeInt):
    _flag = "--stop"
    _min, _max, _name = 10, 100, "stop"


class Seed(_RangeInt):
    _flag = "--seed"
    _min, _max, _name = 0, 4294967295, "seed"


class StyleWeight(_RangeInt):
    _flag = "--sw"
    _min, _max, _name = 0, 1000, "sw"


class OmniWeight(_RangeInt):
    _flag = "--ow"
    _min, _max, _name = 1, 1000, "ow"


class StyleVersion(MJParam, int):
    """스타일 버전 (--sv).

    유효값: 4, 6, 7, 8.
    - sv=7 + --v 7: 프롬프트에서 생략 (중복 기본값)
    - sv=8: NotImplementedError 발생 (API 미지원)
    """
    _flag = "--sv"
    _allowed = (4, 6, 7, 8)

    def __new__(cls, value: int):
        value = int(value)
        if value not in cls._allowed:
            raise ValidationError(
                f"sv must be one of {cls._allowed}, got {value}"
            )
        return int.__new__(cls, value)


class Quality(MJParam, int):
    """화질 — 1, 2, 4 중 하나여야 합니다."""
    _flag = "--q"
    _allowed = (1, 2, 4)

    def __new__(cls, value: int):
        value = int(value)
        if value not in cls._allowed:
            raise ValidationError(
                f"quality must be one of {cls._allowed}, got {value}"
            )
        return int.__new__(cls, value)


# -- Float 타입 --------------------------------------------------------------

class ImageWeight(_RangeFloat):
    _flag = "--iw"
    _min, _max, _name = 0, 3, "iw"


# -- 플래그 타입 ---------------------------------------------------------------

class Tile(_Flag):
    _flag = "--tile"


class Raw(_Flag):
    _flag = "--raw"


class Draft(_Flag):
    _flag = "--draft"


class Niji(MJParam, int):
    """Niji 모델 버전 (--v 대체). 예: --niji 7"""
    _flag = "--niji"

    def __new__(cls, value: int):
        value = int(value)
        if value < 1:
            raise ValidationError(f"niji version must be >= 1, got {value}")
        return int.__new__(cls, value)


class _ModeEnum(StrEnum):
    """상호 배타적 모드 열거형의 기반.

    서브클래스는 멤버만 정의하면 됩니다 — 유효성 검사와 프롬프트
    생성은 상속됩니다.
    """

    @classmethod
    def _missing_(cls, value):
        raise ValidationError(
            f"{cls.__name__} must be one of {[m.value for m in cls]}, got '{value}'"
        )

    def to_prompt(self, version: Version) -> str:
        return f"--{self.value}"


class SpeedMode(_ModeEnum):
    FAST = "fast"
    RELAX = "relax"
    TURBO = "turbo"


class VisibilityMode(_ModeEnum):
    STEALTH = "stealth"
    PUBLIC = "public"

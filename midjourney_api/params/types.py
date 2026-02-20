"""Parameter types with built-in validation and prompt generation.

Each type inherits from a primitive (int, str, float) AND MJParam,
so it's fully compatible with existing code while adding to_prompt().
Validation happens at construction time via __new__.
"""

from __future__ import annotations

import re
from enum import StrEnum

from midjourney_api.exceptions import ValidationError


# -- Version ------------------------------------------------------------------

class Version(int):
    """Midjourney model version."""

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


# -- Interface ----------------------------------------------------------------

class MJParam:
    """Mixin that gives every parameter its CLI flag and prompt fragment."""
    _flag: str

    def to_prompt(self, version: Version) -> str:
        if version == 7:
            return f"{self._flag} {self}"
        return f"{self._flag} {self}"


# -- Base helpers -------------------------------------------------------------

class _Flag(MJParam, int):
    """Bool-like flag backed by int (bool is not subclassable).

    Truthy/falsy via int value (0 or 1). to_prompt() returns just the flag.
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
    """Int constrained to [_min, _max]."""
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
    """Float constrained to [_min, _max]."""
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


# -- String types -------------------------------------------------------------

class AspectRatio(MJParam, str):
    """Aspect ratio in w:h format (e.g. '16:9')."""
    _flag = "--ar"

    def __new__(cls, value: str):
        if not re.match(r"^\d+:\d+$", value):
            raise ValidationError(f"ar must be w:h format, got '{value}'")
        return str.__new__(cls, value)


class Personalize(MJParam, str):
    """Personalize — code or empty (flag-only)."""
    _flag = "--p"

    def __new__(cls, value: str = ""):
        return str.__new__(cls, value)

    def to_prompt(self, version: Version) -> str:
        if version == 7:
            return f"{self._flag} {self}" if self else self._flag
        return f"{self._flag} {self}" if self else self._flag


class StyleRef(MJParam, str):
    """Style reference — URL or style code. No validation."""
    _flag = "--sref"

    def __new__(cls, value: str):
        return str.__new__(cls, value)


class OmniRef(MJParam, str):
    """Object/character reference — must be an image URL, not a code."""
    _flag = "--oref"

    def __new__(cls, value: str):
        if not value.startswith(("http://", "https://")):
            raise ValidationError(
                f"oref must be an image URL (not a code), got '{value}'"
            )
        return str.__new__(cls, value)


# -- Int types ----------------------------------------------------------------

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
    """Style version (--sv). Valid values: 6, 7, 8."""
    _flag = "--sv"
    _allowed = (6, 7, 8)

    def __new__(cls, value: int):
        value = int(value)
        if value not in cls._allowed:
            raise ValidationError(
                f"sv must be one of {cls._allowed}, got {value}"
            )
        return int.__new__(cls, value)


class Quality(MJParam, int):
    """Quality — must be 1, 2, or 4."""
    _flag = "--q"
    _allowed = (1, 2, 4)

    def __new__(cls, value: int):
        value = int(value)
        if value not in cls._allowed:
            raise ValidationError(
                f"quality must be one of {cls._allowed}, got {value}"
            )
        return int.__new__(cls, value)


# -- Float types --------------------------------------------------------------

class ImageWeight(_RangeFloat):
    _flag = "--iw"
    _min, _max, _name = 0, 3, "iw"


# -- Flag types ---------------------------------------------------------------

class Tile(_Flag):
    _flag = "--tile"


class Raw(_Flag):
    _flag = "--raw"


class Draft(_Flag):
    _flag = "--draft"


class Niji(MJParam, int):
    """Niji model version (alternative to --v). e.g. --niji 7"""
    _flag = "--niji"

    def __new__(cls, value: int):
        value = int(value)
        if value < 1:
            raise ValidationError(f"niji version must be >= 1, got {value}")
        return int.__new__(cls, value)


class _ModeEnum(StrEnum):
    """Base for mutually-exclusive mode enums.

    Subclasses only need to define members — validation and prompt
    generation are inherited.
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

"""V7 전용 Midjourney 파라미터."""

from __future__ import annotations

from midjourney_api.exceptions import ValidationError
from midjourney_api.params.base import BaseParams
from midjourney_api.params.types import (
    AspectRatio,
    Chaos,
    Draft,
    ImageWeight,
    Niji,
    OmniRef,
    OmniWeight,
    Personalize,
    Quality,
    Raw,
    Seed,
    SpeedMode,
    Stop,
    StyleRef,
    StyleVersion,
    StyleWeight,
    Stylize,
    Tile,
    Version,
    VisibilityMode,
    Weird,
)


class V7Params(BaseParams):
    """Midjourney V7 파라미터 세트 (전체 유효성 검사 포함)."""

    _CAST_MAP: dict[str, type] = {
        "ar": AspectRatio,
        "chaos": Chaos,
        "quality": Quality,
        "seed": Seed,
        "stylize": Stylize,
        "weird": Weird,
        "stop": Stop,
        "iw": ImageWeight,
        "sref": StyleRef,
        "sw": StyleWeight,
        "sv": StyleVersion,
        "oref": OmniRef,
        "ow": OmniWeight,
        "personalize": Personalize,
        "tile": Tile,
        "raw": Raw,
        "draft": Draft,
        "niji": Niji,
        "speed": SpeedMode,
        "visibility": VisibilityMode,
    }

    VERSION = Version(7)

    def __init__(
        self,
        prompt: str,
        *,
        # Image generation
        ar: AspectRatio | None = None,
        chaos: Chaos | None = None,
        no: str | None = None,
        quality: Quality | None = None,
        seed: Seed | None = None,
        stylize: Stylize | None = None,
        weird: Weird | None = None,
        stop: Stop | None = None,
        tile: Tile = Tile(),
        raw: Raw = Raw(),
        draft: Draft = Draft(),
        iw: ImageWeight | None = None,
        # Reference
        sref: StyleRef | None = None,
        sw: StyleWeight | None = None,
        sv: StyleVersion | None = None,
        oref: OmniRef | None = None,
        ow: OmniWeight | None = None,
        personalize: Personalize | None = None,
        # Mode
        niji: Niji | None = None,
        speed: SpeedMode | None = None,
        visibility: VisibilityMode | None = None,
    ):
        super().__init__(prompt)
        self.version = self.VERSION
        # Image generation params
        self.ar = ar
        self.chaos = chaos
        self.no = no
        self.quality = quality
        self.seed = seed
        self.stylize = stylize
        self.weird = weird
        self.stop = stop
        self.tile = tile
        self.raw = raw
        self.draft = draft
        self.iw = iw
        # Reference params
        self.sref = sref
        self.sw = sw
        self.sv = sv
        self.oref = oref
        self.ow = ow
        self.personalize = personalize
        # Mode params
        self.niji = niji
        self.speed = speed
        self.visibility = visibility

    def validate(self) -> None:
        """교차 필드 유효성 검사만 수행 — 범위 검사는 타입이 담당합니다."""
        errors: list[str] = []

        if self.sw is not None and not self.sref:
            errors.append("sw requires sref to be set")

        if self.ow is not None and not self.oref:
            errors.append("ow requires oref to be set")

        if self.niji is not None:
            niji_incompatible = []
            if self.oref:
                niji_incompatible.append("oref")
            if self.tile:
                niji_incompatible.append("tile")
            if self.quality is not None:
                niji_incompatible.append("quality")
            if niji_incompatible:
                errors.append(
                    f"{', '.join(niji_incompatible)} not compatible with niji"
                )

        if errors:
            raise ValidationError("; ".join(errors))

    def to_prompt_suffix(self) -> str:
        v = self.version
        parts: list[str] = []

        # 버전 — 반드시 맨 앞에 위치
        if self.niji is not None:
            parts.append(self.niji.to_prompt(v))
        else:
            parts.append(v.to_prompt())

        # 단순 선택적 파라미터: (attr_value, condition)
        simple: list[tuple[object, bool]] = [
            (self.ar,         self.ar is not None),
            (self.chaos,      self.chaos is not None),
            (self.quality,    self.quality is not None),
            (self.seed,       self.seed is not None),
            (self.stylize,    self.stylize is not None),
            (self.weird,      self.weird is not None),
            (self.stop,       self.stop is not None),
            (self.tile,       bool(self.tile)),
            (self.raw,        bool(self.raw)),
            (self.draft,      bool(self.draft)),
            (self.iw,         self.iw is not None),
        ]
        for param, cond in simple:
            if cond:
                parts.append(param.to_prompt(v))  # type: ignore[union-attr]

        if self.no:
            parts.append(f"--no {self.no}")

        # 참조 파라미터 (순서 중요: sref+sw, sv, oref+ow, personalize)
        if self.sref:
            parts.append(self.sref.to_prompt(v))
            parts.append((self.sw if self.sw is not None else StyleWeight(100)).to_prompt(v))
        if self.sv is not None and v >= 7:
            if int(self.sv) == 8:
                raise NotImplementedError("sv=8 is not yet supported by the Midjourney API")
            if not (v == 7 and int(self.sv) == 7):
                parts.append(self.sv.to_prompt(v))
        if self.oref:
            parts.append(self.oref.to_prompt(v))
            parts.append((self.ow if self.ow is not None else OmniWeight(100)).to_prompt(v))
        if self.personalize is not None:
            parts.append(self.personalize.to_prompt(v))

        # 모드 열거형
        if self.speed is not None:
            parts.append(self.speed.to_prompt(v))
        if self.visibility is not None:
            parts.append(self.visibility.to_prompt(v))

        return " ".join(parts)

"""V7-specific Midjourney parameters."""

from __future__ import annotations

from midjourney.exceptions import ValidationError
from midjourney.params.base import BaseParams
from midjourney.params.types import (
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
    StyleWeight,
    Stylize,
    Tile,
    Version,
    VisibilityMode,
    Weird,
)


class V7Params(BaseParams):
    """Midjourney V7 parameter set with full validation."""

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
        self.oref = oref
        self.ow = ow
        self.personalize = personalize
        # Mode params
        self.niji = niji
        self.speed = speed
        self.visibility = visibility

    def validate(self) -> None:
        """Cross-field validation only — range checks are handled by types."""
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

        # Version — must come first
        if self.niji is not None:
            parts.append(self.niji.to_prompt(v))
        else:
            parts.append(v.to_prompt())

        # Image generation params
        if self.ar:
            parts.append(self.ar.to_prompt(v))
        if self.chaos is not None:
            parts.append(self.chaos.to_prompt(v))
        if self.no:
            parts.append(f"--no {self.no}")
        if self.quality is not None:
            parts.append(self.quality.to_prompt(v))
        if self.seed is not None:
            parts.append(self.seed.to_prompt(v))
        if self.stylize is not None:
            parts.append(self.stylize.to_prompt(v))
        if self.weird is not None:
            parts.append(self.weird.to_prompt(v))
        if self.stop is not None:
            parts.append(self.stop.to_prompt(v))
        if self.tile:
            parts.append(self.tile.to_prompt(v))
        if self.raw:
            parts.append(self.raw.to_prompt(v))
        if self.draft:
            parts.append(self.draft.to_prompt(v))
        if self.iw is not None:
            parts.append(self.iw.to_prompt(v))

        # Reference params
        if self.sref:
            parts.append(self.sref.to_prompt(v))
            parts.append((self.sw if self.sw is not None else StyleWeight(100)).to_prompt(v))
        if self.oref:
            parts.append(self.oref.to_prompt(v))
            parts.append((self.ow if self.ow is not None else OmniWeight(100)).to_prompt(v))
        if self.personalize is not None:
            parts.append(self.personalize.to_prompt(v))

        # Mode enums
        if self.speed is not None:
            parts.append(self.speed.to_prompt(v))
        if self.visibility is not None:
            parts.append(self.visibility.to_prompt(v))

        return " ".join(parts)

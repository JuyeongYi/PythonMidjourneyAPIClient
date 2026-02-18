"""V7-specific Midjourney parameters."""

from __future__ import annotations

import re
from typing import Optional

from midjourney.exceptions import ValidationError
from midjourney.params.base import BaseParams


class V7Params(BaseParams):
    """Midjourney V7 parameter set with full validation."""

    def __init__(
        self,
        prompt: str,
        *,
        # Image generation
        ar: Optional[str] = None,
        chaos: Optional[int] = None,
        no: Optional[str] = None,
        quality: Optional[int] = None,
        seed: Optional[int] = None,
        stylize: Optional[int] = None,
        weird: Optional[int] = None,
        stop: Optional[int] = None,
        tile: bool = False,
        raw: bool = False,
        draft: bool = False,
        iw: Optional[float] = None,
        # Reference
        sref: Optional[str] = None,
        sw: Optional[int] = None,
        oref: Optional[str] = None,
        personalize: Optional[str] = None,
        # Mode
        fast: bool = False,
        relax: bool = False,
        turbo: bool = False,
        stealth: bool = False,
        public: bool = False,
        niji: bool = False,
    ):
        super().__init__(prompt)
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
        self.personalize = personalize
        # Mode params
        self.fast = fast
        self.relax = relax
        self.turbo = turbo
        self.stealth = stealth
        self.public = public
        self.niji = niji

    def validate(self) -> None:
        errors: list[str] = []

        if self.ar is not None and not re.match(r"^\d+:\d+$", self.ar):
            errors.append(f"ar must be in w:h format (e.g., '16:9'), got '{self.ar}'")

        if self.chaos is not None and not (0 <= self.chaos <= 100):
            errors.append(f"chaos must be 0-100, got {self.chaos}")

        if self.quality is not None and self.quality not in (1, 2, 4):
            errors.append(f"quality must be 1, 2, or 4, got {self.quality}")

        if self.seed is not None and not (0 <= self.seed <= 4294967295):
            errors.append(f"seed must be 0-4294967295, got {self.seed}")

        if self.stylize is not None and not (0 <= self.stylize <= 1000):
            errors.append(f"stylize must be 0-1000, got {self.stylize}")

        if self.weird is not None and not (0 <= self.weird <= 3000):
            errors.append(f"weird must be 0-3000, got {self.weird}")

        if self.stop is not None and not (10 <= self.stop <= 100):
            errors.append(f"stop must be 10-100, got {self.stop}")

        if self.iw is not None and not (0 <= self.iw <= 3):
            errors.append(f"iw must be 0-3, got {self.iw}")

        if self.sw is not None and not (0 <= self.sw <= 1000):
            errors.append(f"sw must be 0-1000, got {self.sw}")

        # Mutually exclusive speed modes
        speed_modes = sum([self.fast, self.relax, self.turbo])
        if speed_modes > 1:
            errors.append("Only one speed mode allowed: fast, relax, or turbo")

        # Mutually exclusive visibility modes
        if self.stealth and self.public:
            errors.append("stealth and public are mutually exclusive")

        if errors:
            raise ValidationError("; ".join(errors))

    def to_prompt_suffix(self) -> str:
        parts: list[str] = []

        # Always include version
        if self.niji:
            parts.append("--niji")
        else:
            parts.append("--v 7")

        # Image generation params
        if self.ar:
            parts.append(f"--ar {self.ar}")
        if self.chaos is not None:
            parts.append(f"--c {self.chaos}")
        if self.no:
            parts.append(f"--no {self.no}")
        if self.quality is not None:
            parts.append(f"--q {self.quality}")
        if self.seed is not None:
            parts.append(f"--seed {self.seed}")
        if self.stylize is not None:
            parts.append(f"--s {self.stylize}")
        if self.weird is not None:
            parts.append(f"--w {self.weird}")
        if self.stop is not None:
            parts.append(f"--stop {self.stop}")
        if self.tile:
            parts.append("--tile")
        if self.raw:
            parts.append("--raw")
        if self.draft:
            parts.append("--draft")
        if self.iw is not None:
            parts.append(f"--iw {self.iw}")

        # Reference params
        if self.sref:
            parts.append(f"--sref {self.sref}")
        if self.sw is not None:
            parts.append(f"--sw {self.sw}")
        if self.oref:
            parts.append(f"--oref {self.oref}")
        if self.personalize is not None:
            parts.append(f"--p {self.personalize}" if self.personalize else "--p")

        # Mode flags
        if self.fast:
            parts.append("--fast")
        if self.relax:
            parts.append("--relax")
        if self.turbo:
            parts.append("--turbo")
        if self.stealth:
            parts.append("--stealth")
        if self.public:
            parts.append("--public")

        return " ".join(parts)

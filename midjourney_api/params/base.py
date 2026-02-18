"""Abstract base class for version-specific parameter sets."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseParams(ABC):
    """Base class for Midjourney generation parameters.

    Subclasses implement version-specific validation and prompt suffix generation.
    """

    def __init__(self, prompt: str, **kwargs):
        self.prompt = prompt

    @abstractmethod
    def validate(self) -> None:
        """Validate all parameters against version-specific rules.

        Raises:
            ValidationError: If any parameter is out of range or invalid.
        """

    @abstractmethod
    def to_prompt_suffix(self) -> str:
        """Build the parameter suffix string (e.g., '--ar 16:9 --s 200').

        Returns only the flags portion, without the prompt text.
        """

    def build_prompt(self) -> str:
        """Combine the text prompt with parameter flags.

        Returns:
            Full prompt string ready for API submission.
        """
        suffix = self.to_prompt_suffix()
        if suffix:
            return f"{self.prompt} {suffix}"
        return self.prompt

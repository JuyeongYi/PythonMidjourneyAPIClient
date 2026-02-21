"""버전별 파라미터 세트의 추상 기본 클래스."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseParams(ABC):
    """Midjourney 생성 파라미터의 기본 클래스.

    서브클래스는 버전별 유효성 검사 및 프롬프트 접미사 생성을 구현합니다.
    """

    def __init__(self, prompt: str, **kwargs):
        self.prompt = prompt

    @abstractmethod
    def validate(self) -> None:
        """모든 파라미터를 버전별 규칙에 따라 검증합니다.

        예외:
            ValidationError: 파라미터가 범위를 벗어나거나 유효하지 않은 경우.
        """

    @abstractmethod
    def to_prompt_suffix(self) -> str:
        """파라미터 접미사 문자열을 빌드합니다 (예: '--ar 16:9 --s 200').

        프롬프트 텍스트 없이 플래그 부분만 반환합니다.
        """

    def build_prompt(self) -> str:
        """텍스트 프롬프트와 파라미터 플래그를 결합합니다.

        반환값:
            API 제출 준비가 된 전체 프롬프트 문자열.
        """
        suffix = self.to_prompt_suffix()
        if suffix:
            return f"{self.prompt} {suffix}"
        return self.prompt

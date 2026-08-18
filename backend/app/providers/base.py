"""Provider base classes + registry.

Design:
- All providers (LLM, Image, Video, TTS) share the same `generate()` signature
- Per-call `user_config` carries user's BYOK credentials (or None → use platform fallback)
- `ProviderRegistry` is a simple name→class lookup; the factory picks based on user config
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ProviderError(Exception):
    """Raised when a provider fails. Wraps the underlying error with provider context."""

    def __init__(self, provider: str, message: str, *, original: Exception | None = None):
        self.provider = provider
        self.original = original
        super().__init__(f"[{provider}] {message}" + (f": {original}" if original else ""))


@dataclass
class UserProviderConfig:
    """User's BYOK config (or None → use platform fallback).

    Either explicit api_key + base_url, or a public provider name to use
    platform's stored credentials.
    """

    provider_name: str = "toapis"      # toapis | yijia | 302 | openai_compat
    api_key: str | None = None         # user-provided
    base_url: str | None = None        # user-provided (for openai_compat)
    model: str | None = None           # user-overridden model (else use provider default)


@dataclass
class GenerationResult:
    """Result of any generation. Output depends on modality."""

    success: bool
    output_url: str | None = None          # for image/video: hosted URL or local path
    output_path: Path | None = None        # local file path (if downloaded)
    text: str | None = None                # for LLM: response text
    metadata: dict[str, Any] = field(default_factory=dict)
    cost_credits: int = 0                  # for credit mode
    error: str | None = None


class LLMProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    async def generate_text(
        self,
        *,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        config: UserProviderConfig | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        response_format: dict | None = None,
    ) -> GenerationResult: ...


class ImageProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    async def generate_image(
        self,
        *,
        prompt: str,
        model: str | None = None,
        config: UserProviderConfig | None = None,
        size: str = "1024x1024",
        reference_images: list[str] | None = None,
    ) -> GenerationResult: ...


class VideoProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    async def generate_video(
        self,
        *,
        prompt: str,
        first_frame: str | None = None,  # image URL or path
        duration: float = 5.0,
        aspect_ratio: str = "16:9",
        model: str | None = None,
        config: UserProviderConfig | None = None,
    ) -> GenerationResult: ...


class TTSProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    async def synthesize(
        self,
        *,
        text: str,
        voice: str = "zh-CN-YunyangNeural",
        output_path: Path,
        config: UserProviderConfig | None = None,
    ) -> GenerationResult: ...


class ProviderRegistry:
    """Static registry of provider name → class."""

    _llm: dict[str, type[LLMProvider]] = {}
    _image: dict[str, type[ImageProvider]] = {}
    _video: dict[str, type[VideoProvider]] = {}
    _tts: dict[str, type[TTSProvider]] = {}

    @classmethod
    def register_llm(cls, name: str, provider_cls: type[LLMProvider]) -> None:
        cls._llm[name] = provider_cls

    @classmethod
    def register_image(cls, name: str, provider_cls: type[ImageProvider]) -> None:
        cls._image[name] = provider_cls

    @classmethod
    def register_video(cls, name: str, provider_cls: type[VideoProvider]) -> None:
        cls._video[name] = provider_cls

    @classmethod
    def register_tts(cls, name: str, provider_cls: type[TTSProvider]) -> None:
        cls._tts[name] = provider_cls

    @classmethod
    def get_llm(cls, name: str, **kwargs) -> LLMProvider:
        if name not in cls._llm:
            raise ProviderError(name, f"LLM provider not registered")
        return cls._llm[name](**kwargs)

    @classmethod
    def get_image(cls, name: str, **kwargs) -> ImageProvider:
        if name not in cls._image:
            raise ProviderError(name, f"Image provider not registered")
        return cls._image[name](**kwargs)

    @classmethod
    def get_video(cls, name: str, **kwargs) -> VideoProvider:
        if name not in cls._video:
            raise ProviderError(name, f"Video provider not registered")
        return cls._video[name](**kwargs)

    @classmethod
    def get_tts(cls, name: str, **kwargs) -> TTSProvider:
        if name not in cls._tts:
            raise ProviderError(name, f"TTS provider not registered")
        return cls._tts[name](**kwargs)

    @classmethod
    def list_llm(cls) -> list[str]:
        return list(cls._llm.keys())

    @classmethod
    def list_image(cls) -> list[str]:
        return list(cls._image.keys())

    @classmethod
    def list_video(cls) -> list[str]:
        return list(cls._video.keys())

    @classmethod
    def list_tts(cls) -> list[str]:
        return list(cls._tts.keys())
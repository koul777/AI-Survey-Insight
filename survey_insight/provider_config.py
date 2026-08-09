from __future__ import annotations

from dataclasses import dataclass


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"
GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_AZURE_API_VERSION = "2024-10-21"


@dataclass(frozen=True)
class ProviderConfig:
    key: str
    display_name: str
    default_chat_model: str | None
    default_embedding_model: str | None
    chat_presets: tuple[tuple[str, str], ...] = ()
    supports_embeddings: bool = True


# Presets are UI examples, not a promise that a provider currently offers a
# model. Users can always enter a model or deployment name directly.
PROVIDER_CONFIGS: dict[str, ProviderConfig] = {
    "openai": ProviderConfig(
        key="openai",
        display_name="OpenAI",
        default_chat_model="gpt-5.5",
        default_embedding_model="text-embedding-3-small",
        chat_presets=(
            ("gpt-5.5", "GPT-5.5"),
            ("gpt-5.4", "GPT-5.4"),
            ("gpt-5.4-mini", "GPT-5.4 Mini"),
        ),
    ),
    "gemini": ProviderConfig(
        key="gemini",
        display_name="Gemini",
        default_chat_model="gemini-3.5-flash",
        default_embedding_model="gemini-embedding-001",
        chat_presets=(
            ("gemini-3.5-flash", "Gemini 3.5 Flash"),
            ("gemini-3.1-pro-preview", "Gemini 3.1 Pro Preview"),
            ("gemini-3.1-flash", "Gemini 3.1 Flash"),
            ("gemini-3.1-flash-lite", "Gemini 3.1 Flash-Lite"),
        ),
    ),
    "claude": ProviderConfig(
        key="claude",
        display_name="Claude",
        default_chat_model="claude-sonnet-5",
        default_embedding_model=None,
        chat_presets=(
            ("claude-sonnet-5", "Claude Sonnet 5"),
            ("claude-opus-4-8", "Claude Opus 4.8"),
            ("claude-sonnet-4-6", "Claude Sonnet 4.6"),
            ("claude-haiku-4-5-20251001", "Claude Haiku 4.5"),
        ),
        supports_embeddings=False,
    ),
    "azure_openai": ProviderConfig(
        key="azure_openai",
        display_name="Azure OpenAI",
        default_chat_model=None,
        default_embedding_model=None,
    ),
    "openai_compatible": ProviderConfig(
        key="openai_compatible",
        display_name="OpenAI-compatible",
        default_chat_model="gpt-5.5",
        default_embedding_model="text-embedding-3-small",
    ),
}


def provider_config(provider: str) -> ProviderConfig:
    normalized = provider.strip().casefold()
    if normalized == "custom":
        normalized = "openai_compatible"
    try:
        return PROVIDER_CONFIGS[normalized]
    except KeyError as exc:
        raise ValueError(f"Unsupported provider: {provider}") from exc


def ui_chat_presets() -> dict[str, list[list[str]]]:
    return {
        key: [[model, label] for model, label in config.chat_presets]
        for key, config in PROVIDER_CONFIGS.items()
        if config.chat_presets
    }

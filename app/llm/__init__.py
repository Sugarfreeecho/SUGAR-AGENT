"""Public LLM transport boundary.

Callers should import provider selection and normalized stream contracts from
this package, never from an individual provider implementation.
"""

from .transport import (
    AnthropicMessagesTransport,
    LLMProvider,
    OpenAICompatibleTransport,
    OpenAIResponsesTransport,
    PROVIDER_SEMANTICS_VERSION,
    ResponsesStateMode,
    build_transport,
    canonical_llm_type,
    chat_messages_to_anthropic,
    chat_messages_to_responses_input,
    detect_provider,
    merge_streamed_tool_name,
    normalize_provider,
    normalize_responses_state_mode,
    resolve_provider,
    resolve_profile_provider,
)
from .provider_registry import ProviderDescriptor, ProviderRegistry, provider_registry
from .types import LLMRequestContext, LLMRequestPurpose, TransportEvent

__all__ = [
    "AnthropicMessagesTransport",
    "LLMProvider",
    "OpenAICompatibleTransport",
    "OpenAIResponsesTransport",
    "PROVIDER_SEMANTICS_VERSION",
    "ResponsesStateMode",
    "TransportEvent",
    "build_transport",
    "canonical_llm_type",
    "chat_messages_to_anthropic",
    "chat_messages_to_responses_input",
    "detect_provider",
    "merge_streamed_tool_name",
    "normalize_provider",
    "normalize_responses_state_mode",
    "resolve_provider",
    "resolve_profile_provider",
    "ProviderDescriptor",
    "ProviderRegistry",
    "provider_registry",
    "LLMRequestContext",
    "LLMRequestPurpose",
]

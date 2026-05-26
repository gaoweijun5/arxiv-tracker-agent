"""LLM factory — creates the correct LangChain chat model based on provider config."""

from langchain_core.language_models import BaseChatModel
from loguru import logger

from backend.core.config import get_settings


def create_llm(temperature: float | None = None, model_kwargs: dict | None = None) -> BaseChatModel:
    """Create a chat model instance based on the configured provider.

    Returns ChatOpenAI for openai-compatible providers (DeepSeek, OpenAI, etc.)
    or ChatAnthropic for Anthropic.
    """
    settings = get_settings()
    provider = settings.llm_provider.lower()
    temp = temperature if temperature is not None else settings.llm_temperature

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when llm_provider=anthropic")

        logger.info(f"Using Anthropic model: {settings.anthropic_model}")
        kwargs = {"model_name": settings.anthropic_model, "temperature": temp, "api_key": settings.anthropic_api_key}
        if model_kwargs:
            kwargs["default_request_headers"] = model_kwargs
        return ChatAnthropic(**kwargs)

    # Default: OpenAI-compatible (DeepSeek, OpenAI, etc.)
    from langchain_openai import ChatOpenAI

    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required when llm_provider=openai")

    logger.info(f"Using OpenAI-compatible model: {settings.llm_model} @ {settings.openai_api_base}")
    kwargs = {
        "model": settings.llm_model,
        "temperature": temp,
        "api_key": settings.openai_api_key,
        "base_url": settings.openai_api_base,
    }
    if model_kwargs:
        kwargs["model_kwargs"] = model_kwargs
    return ChatOpenAI(**kwargs)

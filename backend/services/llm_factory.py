"""LLM factory — creates the correct LangChain chat model based on provider config."""

from langchain_core.language_models import BaseChatModel
from loguru import logger

from backend.core.config import get_settings


def create_llm(
    temperature: float | None = None,
    model_kwargs: dict | None = None,
    model: str | None = None,
    extra_body: dict | None = None,
) -> BaseChatModel:
    """Create a chat model instance based on the configured provider.

    Returns ChatOpenAI for openai-compatible providers (DeepSeek, OpenAI, etc.)
    or ChatAnthropic for Anthropic.
    """
    settings = get_settings()
    provider = settings.llm_provider.lower()
    temp = temperature if temperature is not None else settings.llm_temperature
    model_name = model or settings.llm_model

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when llm_provider=anthropic")

        anthropic_model = model or settings.anthropic_model
        logger.info(f"Using Anthropic model: {anthropic_model}")
        kwargs = {
            "model_name": anthropic_model,
            "temperature": temp,
            "api_key": settings.anthropic_api_key,
        }
        if model_kwargs:
            kwargs["default_request_headers"] = model_kwargs
        return ChatAnthropic(**kwargs)

    # Default: OpenAI-compatible (DeepSeek, OpenAI, etc.)
    from langchain_openai import ChatOpenAI

    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required when llm_provider=openai")

    logger.info(f"Using OpenAI-compatible model: {model_name} @ {settings.openai_api_base}")
    kwargs = {
        "model": model_name,
        "temperature": temp,
        "api_key": settings.openai_api_key,
        "base_url": settings.openai_api_base,
    }
    passthrough_kwargs = {}
    if model_kwargs:
        # langchain-openai 1.x expects provider-specific request bodies as
        # explicit ChatOpenAI kwargs, not buried inside model_kwargs.
        if "extra_body" in model_kwargs and extra_body is None:
            extra_body = model_kwargs["extra_body"]
        passthrough_kwargs = {
            key: value for key, value in model_kwargs.items() if key != "extra_body"
        }
    if extra_body:
        kwargs["extra_body"] = extra_body
    if passthrough_kwargs:
        kwargs["model_kwargs"] = passthrough_kwargs
    return ChatOpenAI(**kwargs)

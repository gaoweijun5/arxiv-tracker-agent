"""OpenAI-compatible VLM caption service."""

from io import BytesIO
from typing import Any, Optional

import httpx
from loguru import logger

from backend.core.config import Settings, get_settings


class VLMService:
    """Caption table and figure images through an OpenAI-compatible chat API."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

    @property
    def is_configured(self) -> bool:
        """Return whether VLM captioning has enough configuration to run."""
        return bool(
            self.settings.vlm_api_key
            and self.settings.vlm_api_endpoint
            and self.settings.vlm_model
        )

    @property
    def chat_completions_url(self) -> str:
        endpoint = self.settings.vlm_api_endpoint.rstrip("/")
        if endpoint.endswith("/chat/completions"):
            return endpoint
        return f"{endpoint}/chat/completions"

    def caption_image(self, image: Any, prompt: str) -> Optional[str]:
        """Generate a plain-text caption for one image.

        The request body follows the OpenAI chat-completions vision format and
        works with providers that expose an OpenAI-compatible endpoint.
        """
        if not self.is_configured:
            return None

        try:
            data_url = self._image_to_data_url(image)
            response = httpx.post(
                self.chat_completions_url,
                headers={
                    "Authorization": f"Bearer {self.settings.vlm_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.settings.vlm_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You create concise, faithful captions for scientific "
                                "paper tables and figures. Return plain text only."
                            ),
                        },
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": data_url},
                                },
                            ],
                        },
                    ],
                    "temperature": self.settings.vlm_temperature,
                    "max_tokens": self.settings.vlm_max_tokens,
                },
                timeout=self.settings.vlm_timeout_seconds,
            )
            response.raise_for_status()
            caption = self._extract_caption(response.json())
            return " ".join(caption.split()) or None
        except Exception as e:
            logger.warning(f"VLM caption request failed: {e}")
            return None

    def _image_to_data_url(self, image: Any) -> str:
        if isinstance(image, bytes):
            image_bytes = image
        else:
            buffer = BytesIO()
            if getattr(image, "mode", "RGB") not in ("RGB", "L"):
                image = image.convert("RGB")
            image.save(buffer, format="PNG")
            image_bytes = buffer.getvalue()

        import base64

        encoded = base64.b64encode(image_bytes).decode("ascii")
        return f"data:image/png;base64,{encoded}"

    def _extract_caption(self, payload: dict) -> str:
        choices = payload.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if text:
                        parts.append(str(text))
            return "\n".join(parts)
        return str(content)


_vlm_service: Optional[VLMService] = None


def get_vlm_service() -> VLMService:
    """Get or create VLM service singleton."""
    global _vlm_service
    if _vlm_service is None:
        _vlm_service = VLMService()
    return _vlm_service

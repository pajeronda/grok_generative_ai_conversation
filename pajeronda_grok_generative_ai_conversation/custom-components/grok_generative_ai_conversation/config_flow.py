from __future__ import annotations

from typing import Any
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigEntry, OptionsFlowWithConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import llm
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import (
    DOMAIN,
    CONF_PROMPT,
    CONF_CHAT_MODEL,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    CONF_MAX_TOKENS,
    CONF_API_ENDPOINT,
    DEFAULT_API_ENDPOINT,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_P,
    RECOMMENDED_MAX_TOKENS,
)


class GrokConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Grok Generative AI."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            # Qui dovresti validare la API Key prima di creare l'entry
            return self.async_create_entry(title="Grok Generative AI", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Optional(
                        CONF_API_ENDPOINT, default=DEFAULT_API_ENDPOINT
                    ): str,
                }
            ),
            description_placeholders={"api_key_url": DEFAULT_API_ENDPOINT},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowWithConfigEntry:
        """Get the options flow for this handler."""
        return GrokOptionsFlow(config_entry)


class GrokOptionsFlow(OptionsFlowWithConfigEntry):
    """Handle an options flow for Grok Generative AI."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        super().__init__(config_entry)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""

        if user_input is not None:
            # Pulisci il prompt se è vuoto
            if not user_input.get(CONF_PROMPT, "").strip():
                user_input.pop(CONF_PROMPT, None)

            return self.async_create_entry(title="", data=user_input)

        # Get current value for suggested_value
        current_llm_apis = self.options.get(CONF_LLM_HASS_API, False)
        # Convert old list format to boolean
        if isinstance(current_llm_apis, (list, tuple)):
            suggested_assist = bool(current_llm_apis)
        else:
            suggested_assist = bool(current_llm_apis)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_PROMPT,
                        description={
                            "suggested_value": self.options.get(CONF_PROMPT, "")
                        },
                    ): str,
                    vol.Optional(
                        CONF_CHAT_MODEL,
                        description={
                            "suggested_value": self.options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL)
                        },
                    ): str,
                    vol.Optional(
                        CONF_TEMPERATURE,
                        description={
                            "suggested_value": self.options.get(CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE)
                        },
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_TOP_P,
                        description={
                            "suggested_value": self.options.get(CONF_TOP_P, RECOMMENDED_TOP_P)
                        },
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_MAX_TOKENS,
                        description={
                            "suggested_value": self.options.get(CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS)
                        },
                    ): int,
                    vol.Optional(
                        CONF_LLM_HASS_API,
                        description={"suggested_value": suggested_assist},
                    ): bool,
                }
            ),
            description_placeholders={
                "recommended_chat_model": RECOMMENDED_CHAT_MODEL,
                "recommended_temperature": str(RECOMMENDED_TEMPERATURE),
                "recommended_top_p": str(RECOMMENDED_TOP_P),
                "recommended_max_tokens": str(RECOMMENDED_MAX_TOKENS),
            },
        )
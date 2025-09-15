"""Conversation support for the Grok Generative AI Conversation integration."""

from __future__ import annotations

from typing import Literal

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_LLM_HASS_API, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers import llm

from .const import CONF_PROMPT, DOMAIN, LOGGER
from .prompt_default import DEFAULT_CONVERSATION_PROMPT
from .entity import GrokGenerativeAILLMBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up conversation entities."""
    # Se esistono subentry di tipo "conversation", le istanziamo.
    created = False
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "conversation":
            continue
        async_add_entities(
            [GrokGenerativeAIConversationEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )
        created = True

    if not created:
        class _PseudoSub:
            def __init__(self, entry: ConfigEntry) -> None:
                self.subentry_type = "conversation"
                self.subentry_id = f"{entry.entry_id}:conversation"
                self.title = entry.title or "Grok AI Conversation"
                # Merge data+options come sorgente impostazioni
                data = dict(entry.data)
                data.update(entry.options)
                self.data = data

        pseudo = _PseudoSub(config_entry)
        async_add_entities([GrokGenerativeAIConversationEntity(config_entry, pseudo)])


class GrokGenerativeAIConversationEntity(
    conversation.ConversationEntity,
    conversation.AbstractConversationAgent,
    GrokGenerativeAILLMBaseEntity,
):
    """Grok Generative AI conversation agent."""

    _attr_supports_streaming = True

    def __init__(self, entry: ConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the agent."""
        super().__init__(entry, subentry)
        # Espone CONTROL sempre per supportare il fallback con tools
        # La logica di attivazione è gestita tramite tools_control parameter
        self._attr_supported_features = conversation.ConversationEntityFeature.CONTROL

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return a list of supported languages."""
        return MATCH_ALL

    def _get_llm_hass_api_option(self) -> bool:
        """True if LLM_HASS_API is configured (handles both bool and list formats)."""
        # Check subentry, then root options, then root data
        for source in [self.subentry.data, self.entry.options, self.entry.data]:
            value = source.get(CONF_LLM_HASS_API)
            if value is not None:
                # Handle both bool and list formats
                if isinstance(value, bool):
                    return value
                elif isinstance(value, (list, tuple)):
                    # Legacy format: convert list to boolean
                    return bool(value and ("assist" in value or "conversation.home_assistant" in value))
        return False

    def _get_str_option(self, key: str) -> str | None:
        """Stringa non vuota da subentry o root, altrimenti None."""
        def pick(v):
            return v if isinstance(v, str) and v.strip() else None
        return pick(self.subentry.data.get(key)) or pick(self.entry.options.get(key)) or pick(self.entry.data.get(key))

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self.entry, self)

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from Home Assistant."""
        conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Call the LLM using standard HA pattern."""
        # Build system prompt using standard HA approach
        user_prompt = self._get_str_option(CONF_PROMPT)
        if user_prompt:
            system_prompt = (
                f"{DEFAULT_CONVERSATION_PROMPT}\n\n"
                "# --- USER INSTRUCTIONS ---\n"
                f"{user_prompt}"
            )
        else:
            system_prompt = DEFAULT_CONVERSATION_PROMPT

        # Get LLM API configuration
        llm_apis = [llm.LLM_API_ASSIST] if self._get_llm_hass_api_option() else None

        try:
            await chat_log.async_provide_llm_data(
                user_input.as_llm_context(DOMAIN),
                llm_apis,
                system_prompt,
                user_input.extra_system_prompt,
            )
        except conversation.ConverseError as err:
            return err.as_conversation_result()

        # Delegate to base entity for LLM processing and custom tag pipeline
        await self._async_handle_chat_log(chat_log, user_input=user_input)

        return conversation.async_get_result_from_chat_log(user_input, chat_log)

    async def async_fallback_with_tools(self, text: str, language: str | None) -> str | None:
        """Execute fallback using tools-enabled conversation pipeline."""
        try:
            # Create user input for fallback
            user_input = conversation.ConversationInput(
                text=text,
                context=None,
                conversation_id="fallback_tools",
                device_id=None,
                language=language or "en",
                agent_id=self.entity_id,
            )

            # Use HA's standard chat session/log pattern
            from homeassistant.helpers.chat_session import async_get_chat_session
            from homeassistant.components.conversation.chat_log import async_get_chat_log

            with (
                async_get_chat_session(self.hass, user_input.conversation_id) as session,
                async_get_chat_log(self.hass, session, user_input) as chat_log,
            ):
                # Provide tools-enabled LLM data
                await chat_log.async_provide_llm_data(
                    user_input.as_llm_context(DOMAIN),
                    [llm.LLM_API_ASSIST],  # Enable tools for fallback
                    None,  # Let HA manage the tools prompt automatically
                    None,
                )

                # Process with tools enabled
                await self._async_handle_chat_log(chat_log, user_input=user_input, tools_control=True)

                # Get result using standard HA method
                result = conversation.async_get_result_from_chat_log(user_input, chat_log)

                if result and result.response and result.response.speech:
                    return result.response.speech.get("plain", {}).get("speech")

        except Exception as err:
            LOGGER.error("Error in conversation fallback with tools: %s", err, exc_info=True)

        return None

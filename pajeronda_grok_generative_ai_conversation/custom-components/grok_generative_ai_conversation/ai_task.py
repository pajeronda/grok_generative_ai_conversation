"""AI Task integration for Grok Generative AI Conversation."""

from json import JSONDecodeError

from homeassistant.components import ai_task, conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.json import json_loads

from .const import LOGGER
from .entity import ERROR_GETTING_RESPONSE, GrokGenerativeAILLMBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AI Task entities."""
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "ai_task_data":
            continue

        async_add_entities(
            [GrokGenerativeAITaskEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class GrokGenerativeAITaskEntity(
    ai_task.AITaskEntity,
    GrokGenerativeAILLMBaseEntity,
):
    """Grok Generative AI AI Task entity."""

    _attr_supported_features = (
        ai_task.AITaskEntityFeature.GENERATE_DATA
    )

    async def _async_generate_data(
        self,
        task: ai_task.GenDataTask,
        chat_log: conversation.ChatLog,
    ) -> ai_task.GenDataTaskResult:
        """Handle a generate data task."""
        await self._async_handle_chat_log(chat_log, task.structure)

        # Get the LAST available AssistantContent, not necessarily the last log element.
        last_assistant = None
        for item in reversed(chat_log.content):
            if isinstance(item, conversation.AssistantContent):
                last_assistant = item
                break

        if last_assistant is None:
            LOGGER.error(
                "Last assistant message not found in chat log. Tail: %s. This could be due to the model not returning a valid response",
                chat_log.content[-1] if chat_log.content else None,
            )
            raise HomeAssistantError(ERROR_GETTING_RESPONSE)

        text = last_assistant.content or ""

        if not task.structure:
            return ai_task.GenDataTaskResult(
                conversation_id=chat_log.conversation_id,
                data=text,
            )

        try:
            data = json_loads(text)
        except JSONDecodeError as err:
            LOGGER.error(
                "Failed to parse JSON response: %s. Response: %s",
                err,
                text,
            )
            raise HomeAssistantError(ERROR_GETTING_RESPONSE) from err

        return ai_task.GenDataTaskResult(
            conversation_id=chat_log.conversation_id,
            data=data,
        )

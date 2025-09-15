from __future__ import annotations

import json
import re
import ast
from typing import TYPE_CHECKING, Any, AsyncIterator, AsyncGenerator

from openai import AsyncOpenAI
from openai import APIConnectionError, AuthenticationError, RateLimitError, BadRequestError

from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm
from homeassistant.helpers.entity import Entity
from homeassistant.helpers import device_registry as dr
from homeassistant.components import conversation

from .const import (
    DOMAIN,
    LOGGER,
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
    CONF_TEMPERATURE,
    CONF_TOP_P,
    RECOMMENDED_CHAT_MODEL,
    RECOMMENDED_MAX_TOKENS,
    RECOMMENDED_TEMPERATURE,
    RECOMMENDED_TOP_P,
    ERROR_GETTING_RESPONSE,
    ERROR_HANDOFF_FAILED,
    DEFAULT_LOCAL_AGENT,
    LOCAL_TAG_START,
    LOCAL_TAG_RE,
)

if TYPE_CHECKING:
    from . import GrokGenerativeAIConfigEntry


def _as_message_content(value: Any) -> str:
    """Convert value to message content string."""
    if isinstance(value, str) and value != "":
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return " "


def _format_tool_for_openai(tool: llm.Tool) -> dict[str, Any]:
    """Convert Home Assistant tool to OpenAI format."""
    tool_def = {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }

    if tool.parameters and tool.parameters.schema:
        from voluptuous_openapi import convert
        try:
            schema = convert(tool.parameters)
            tool_def["function"]["parameters"] = schema
        except Exception as err:
            LOGGER.warning("Failed to convert tool schema for %s: %s", tool.name, err)

    return tool_def


def _parse_handoff_payload(raw: str) -> tuple[str, str | None]:
    """Parse handoff payload from tag content."""
    raw = raw.strip()
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            text = str(obj.get("text", "")).strip()
            agent = obj.get("agent_id")
            agent = str(agent).strip() if isinstance(agent, str) else None
            return text, agent
    except Exception:
        pass

    try:
        obj = ast.literal_eval(raw)
        if isinstance(obj, dict):
            text = str(obj.get("text", "")).strip()
            agent = obj.get("agent_id")
            agent = str(agent).strip() if isinstance(agent, str) else None
            return text, agent
    except Exception:
        pass

    # Regex fallback
    m = re.search(r'"text"\s*:\s*"([^"]*)"', raw)
    text = m.group(1).strip() if m else ""
    m2 = re.search(r'"agent_id"\s*:\s*"([^"]*)"', raw)
    agent = m2.group(1).strip() if m2 else None
    return text, agent


class GrokGenerativeAILLMBaseEntity(Entity):
    """Base entity for Grok Generative AI integrations."""

    def __init__(
        self,
        entry: "GrokGenerativeAIConfigEntry",
        subentry: ConfigSubentry,
        default_model: str = RECOMMENDED_CHAT_MODEL,
    ) -> None:
        """Initialize the entity."""
        self.entry = entry
        self.subentry = subentry
        self._attr_name = subentry.title
        self._client: AsyncOpenAI = entry.runtime_data
        self._attr_unique_id = subentry.subentry_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="xAI",
            model=subentry.data.get(CONF_CHAT_MODEL, default_model),
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    def _build_openai_messages(self, chat_log: conversation.ChatLog) -> list[dict[str, Any]]:
        """Build OpenAI-compatible messages from chat log content."""
        messages = []
        for content in chat_log.content:
            if hasattr(content, 'role') and hasattr(content, 'content'):
                if getattr(content, 'role', None) not in ('tool', 'tool_result'):
                    messages.append({
                        "role": content.role,
                        "content": _as_message_content(content.content)
                    })
        return messages

    async def _process_tag_handoff(
        self,
        buffer: str,
        user_input: conversation.ConversationInput | None
    ) -> AsyncGenerator[conversation.AssistantContentDeltaDict, None]:
        """Process handoff tag and yield appropriate response."""
        LOGGER.debug("Processing handoff: %s", buffer[:50])

        match = LOCAL_TAG_RE.search(buffer.strip())
        if not match:
            LOGGER.warning("Malformed tag in buffer: %s", buffer[:50])
            yield {"content": ERROR_HANDOFF_FAILED}
            return

        payload = match.group(1)
        try:
            text, agent_id = _parse_handoff_payload(payload)
            if not text:
                yield {"content": ERROR_HANDOFF_FAILED}
                return

            language = getattr(user_input, "language", "en") if user_input else "en"

            # Step 1: Try Assist
            try:
                conversation_result = await self.hass.services.async_call(
                    "conversation", "process",
                    {
                        "text": text,
                        "language": language,
                        "agent_id": DEFAULT_LOCAL_AGENT,
                    },
                    blocking=True,
                    return_response=True,
                )

                # Parse result
                speech = None
                intent_success = False

                if hasattr(conversation_result, 'get'):
                    response = conversation_result.get("response", {})
                    speech = response.get("speech", {}).get("plain", {}).get("speech")
                    intent_success = response.get("response_type") != "error"

                if speech and intent_success:
                    yield {"content": speech}
                    return

            except Exception as e:
                LOGGER.warning("Assist processing failed: %s", e)

            # Step 2: Fallback with Tools
            LOGGER.debug("Trying tools fallback for: %s", text[:30])
            fallback_response = await self._async_fallback_with_tools(text, language)
            if fallback_response:
                yield {"content": fallback_response}
            else:
                LOGGER.warning("Tools fallback failed for: %s", text[:30])
                yield {"content": ERROR_HANDOFF_FAILED}

        except Exception as err:
            LOGGER.error("Error processing tag handoff: %s", err, exc_info=True)
            LOGGER.error("Tag handoff error - buffer: %s, payload: %s", buffer[:100], locals().get('payload', 'N/A'))
            yield {"content": ERROR_HANDOFF_FAILED}

    async def _async_fallback_with_tools(self, text: str, language: str | None) -> str | None:
        """Execute fallback using conversation entity's tools method."""
        try:
            conv_agent = conversation.async_get_agent(self.hass, self.entry.entry_id)
            if not conv_agent or not hasattr(conv_agent, 'async_fallback_with_tools'):
                return None
            return await conv_agent.async_fallback_with_tools(text, language)
        except Exception as err:
            LOGGER.error("Error in tools fallback: %s", err)
            return None

    async def _async_handle_chat_log(
        self,
        chat_log: conversation.ChatLog,
        structure: Any | None = None,
        *,
        user_input: conversation.ConversationInput | None = None,
        tools_control: bool | None = None,
    ) -> None:
        """Process chat log using standard HA pattern with custom tag pipeline."""
        options = self.subentry.data
        model_name = options.get(CONF_CHAT_MODEL, RECOMMENDED_CHAT_MODEL)
        temperature = options.get(CONF_TEMPERATURE, RECOMMENDED_TEMPERATURE)
        top_p = options.get(CONF_TOP_P, RECOMMENDED_TOP_P)
        max_tokens = options.get(CONF_MAX_TOKENS, RECOMMENDED_MAX_TOKENS)

        # Build messages from chat_log content using HA standard approach
        messages = self._build_openai_messages(chat_log)

        # Determine if tools should be used
        user_wants_tools = options.get(CONF_LLM_HASS_API, False)
        # Custom pipeline is always used EXCEPT when explicitly forcing tools (fallback mode)
        bypass_custom_pipeline = tools_control is True
        should_use_tools = tools_control if tools_control is not None else user_wants_tools

        async def _transform_stream(
            result: AsyncIterator[Any], user_input: conversation.ConversationInput | None
        ) -> AsyncGenerator[conversation.AssistantContentDeltaDict, None]:
            """Transform OpenAI stream to HA format with custom tag pipeline."""

            # Only bypass custom pipeline when explicitly in fallback mode
            if bypass_custom_pipeline:
                LOGGER.debug("Using direct tools mode (fallback)")
                yield {"role": "assistant"}
                async for event in result:
                    for choice in getattr(event, "choices", []) or []:
                        delta = getattr(choice, "delta", None)
                        if delta and delta.content:
                            yield {"content": delta.content}
                return

            # Custom tag pipeline - simple detection
            buffer = ""
            tag_detected = False

            yield {"role": "assistant"}

            try:
                async for event in result:
                    for choice in getattr(event, "choices", []) or []:
                        delta = getattr(choice, "delta", None)
                        if not delta or not delta.content:
                            continue

                        content_chunk = delta.content

                        if not tag_detected:
                            buffer += content_chunk
                            stripped_buffer = buffer.lstrip()

                            # Simple check: if starts with [[, it's a tag
                            if stripped_buffer.startswith("[["):
                                LOGGER.debug("Tag detected: %s", buffer[:50])
                                tag_detected = True
                                continue

                            # If we have any non-whitespace content that's not [[, it's conversation
                            elif stripped_buffer and not stripped_buffer.startswith("[["):
                                yield {"content": buffer}
                                tag_detected = None  # Mark as decided - regular conversation
                                buffer = ""
                        elif tag_detected is True:
                            # Accumulating tag content
                            buffer += content_chunk
                        else:
                            # Regular conversation mode
                            yield {"content": content_chunk}

                # Process accumulated tag content or remaining buffer
                if tag_detected is True and buffer:
                    async for delta in self._process_tag_handoff(buffer, user_input):
                        yield delta
                elif buffer:
                    yield {"content": buffer}

            except Exception as err:
                LOGGER.error("Error in stream transformation: %s", err, exc_info=True)
                LOGGER.error("Stream state - tag_detected: %s, buffer length: %d, buffer content: %s",
                           tag_detected, len(buffer), buffer[:100] if buffer else "empty")
                yield {"content": f"\n\nStream Error: {err}"}

        # Configure request
        request_kwargs: dict[str, Any] = dict(
            model=model_name,
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            stream=True,
            stop=None,
        )

        # Add tools if enabled and available
        if should_use_tools and chat_log.llm_api and chat_log.llm_api.tools:
            if bypass_custom_pipeline:
                LOGGER.debug("Adding %d tools to LLM request (fallback mode)", len(chat_log.llm_api.tools))
                request_kwargs["tools"] = [_format_tool_for_openai(tool) for tool in chat_log.llm_api.tools]
                request_kwargs["tool_choice"] = "auto"

        try:
            stream = await self._client.chat.completions.create(**request_kwargs)
        except (
            AuthenticationError,
            APIConnectionError,
            RateLimitError,
            BadRequestError,
            Exception,
        ) as err:
            LOGGER.error("Error calling xAI: %s", err)
            raise HomeAssistantError(ERROR_GETTING_RESPONSE) from err

        # Use HA's native streaming with our custom tag pipeline
        async for _ in chat_log.async_add_delta_content_stream(
            self.entity_id, _transform_stream(stream, user_input)
        ):
            pass
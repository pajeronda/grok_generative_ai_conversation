"""Constants for the Grok Generative AI Conversation integration."""

import logging
import re

from homeassistant.const import CONF_LLM_HASS_API

# General
LOGGER = logging.getLogger(__package__)
DOMAIN = "grok_generative_ai_conversation"
DEFAULT_TITLE = "Grok Generative AI"
TIMEOUT_MILLIS = 10000

# config_flow.py
CONF_PROMPT = "prompt"
CONF_CHAT_MODEL = "chat_model"
CONF_TEMPERATURE = "temperature"
CONF_TOP_P = "top_p"
CONF_MAX_TOKENS = "max_tokens"
CONF_API_ENDPOINT = "api_endpoint"
DEFAULT_API_ENDPOINT = "https://api.x.ai/v1"
RECOMMENDED_CHAT_MODEL = "grok-3-mini"
RECOMMENDED_TEMPERATURE = 0.0
RECOMMENDED_TOP_P = 1.0
RECOMMENDED_MAX_TOKENS = 2000

# conversation.py - Recommended defaults for Conversation subentry:
# - CONF_LLM_HASS_API defaults to False to use custom tag-based pipeline
# - When False: custom tag pipeline (LLM → tag detection → Assist → Tools fallback)
# - When True: direct HA LLM mode (LLM with direct tools integration)
RECOMMENDED_CONVERSATION_OPTIONS = {
    CONF_LLM_HASS_API: False,
}

# conversation.py - Default name for Conversation subentry
DEFAULT_CONVERSATION_NAME = "Grok Conversation"

# ai_task.py - Recommended defaults for AI Task subentry
DEFAULT_AI_TASK_NAME = "Grok AI Task"
RECOMMENDED_AI_TASK_OPTIONS = {
    CONF_CHAT_MODEL: RECOMMENDED_CHAT_MODEL,
    CONF_TEMPERATURE: RECOMMENDED_TEMPERATURE,
    CONF_TOP_P: RECOMMENDED_TOP_P,
    CONF_MAX_TOKENS: RECOMMENDED_MAX_TOKENS,
}

# entity.py
ERROR_GETTING_RESPONSE = "Sorry, there was a problem getting a response from Grok."
ERROR_HANDOFF_FAILED = "I was not able to handle your request. Please try rephrasing it."
DEFAULT_LOCAL_AGENT = "conversation.home_assistant"
LOCAL_TAG_START = "[["
LOCAL_TAG_RE = re.compile(r"\[\[HA_LOCAL:\s*(.*?)\s*\]\]", re.DOTALL)

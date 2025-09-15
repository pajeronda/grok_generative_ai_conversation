"""The Grok Generative AI Conversation integration."""

from __future__ import annotations

from functools import partial
from types import MappingProxyType

from openai import AsyncOpenAI
from openai import APIConnectionError, AuthenticationError, RateLimitError, BadRequestError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API, Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers import llm as ha_llm  # per migrazione opzione assist
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue  # noqa: F401  # kept for potential future notices
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_PROMPT,
    DEFAULT_AI_TASK_NAME,
    DEFAULT_TITLE,
    DOMAIN,
    LOGGER,
    RECOMMENDED_AI_TASK_OPTIONS,
    RECOMMENDED_CHAT_MODEL,
    TIMEOUT_MILLIS,
    CONF_API_ENDPOINT,
    DEFAULT_API_ENDPOINT,
)

SERVICE_GENERATE_CONTENT = "generate_content"

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = (
    Platform.AI_TASK,
    Platform.CONVERSATION,
)

type GrokGenerativeAIConfigEntry = ConfigEntry[AsyncOpenAI]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Grok Generative AI Conversation."""
    await async_migrate_integration(hass)

    async def generate_content(call: ServiceCall) -> ServiceResponse:
        """Generate content from a text prompt (attachments non supportati)."""
        prompt: str = call.data[CONF_PROMPT]

        # Recupera il client dalla prima entry caricata
        config_entry: GrokGenerativeAIConfigEntry = (
            hass.config_entries.async_loaded_entries(DOMAIN)[0]
        )
        client = config_entry.runtime_data

        try:
            resp = await client.chat.completions.create(
                model=RECOMMENDED_CHAT_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
        except AuthenticationError as err:
            raise HomeAssistantError(f"Autenticazione fallita: {err}") from err
        except (APIConnectionError, RateLimitError, BadRequestError, Exception) as err:
            raise HomeAssistantError(f"Errore generazione contenuto: {err}") from err

        text = (resp.choices[0].message.content if resp.choices else None) or ""
        if not text:
            raise HomeAssistantError("Errore sconosciuto generando il contenuto")

        return {"text": text}

    hass.services.async_register(
        DOMAIN,
        SERVICE_GENERATE_CONTENT,
        generate_content,
        schema=vol.Schema(
            {
                vol.Required(CONF_PROMPT): cv.string,
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: GrokGenerativeAIConfigEntry
) -> bool:
    """Set up Grok Generative AI Conversation from a config entry."""
    # Istanzia client OpenAI-compatibile puntando a X.ai
    api_endpoint = entry.data.get(CONF_API_ENDPOINT, DEFAULT_API_ENDPOINT)
    try:
        # Evita blocking call (caricamento certificati) nell'event loop
        client = await hass.async_add_executor_job(
            partial(
                AsyncOpenAI,
                api_key=entry.data[CONF_API_KEY],
                base_url=api_endpoint,
                timeout=TIMEOUT_MILLIS / 1000,
            )
        )
        # Verifica di base: elenco modelli
        await client.models.list()
    except AuthenticationError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except APIConnectionError as err:
        raise ConfigEntryNotReady(err) from err
    except Exception as err:
        raise ConfigEntryError(err) from err
    else:
        entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GrokGenerativeAIConfigEntry
) -> bool:
    """Unload GrokGenerativeAI."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    return True


async def async_update_options(
    hass: HomeAssistant, entry: GrokGenerativeAIConfigEntry
) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_integration(hass: HomeAssistant) -> None:
    """Migrate integration entry structure per rimozione STT/TTS."""
    # Migrazione da versioni precedenti: rimuovi subentry TTS/STT e consolida
    entries = sorted(
        hass.config_entries.async_entries(DOMAIN),
        key=lambda e: e.disabled_by is not None,
    )
    # Se non ci sono v1/v2 da migrare o nessuna entry, nulla da fare
    if not entries:
        return

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    for entry in entries:
        # Rimuovi eventuali subentry TTS/STT residuali
        for sub_id, sub in list(entry.subentries.items()):
            if sub.subentry_type in ("tts", "stt"):
                device = device_registry.async_get_device(
                    identifiers={(DOMAIN, sub.subentry_id)}
                )
                if device:
                    device_registry.async_update_device(
                        device.id,
                        remove_config_subentry_id=sub.subentry_id,
                    )
                hass.config_entries.async_remove_subentry(entry, sub_id)

        # Assicurati che esista un AI task subentry
        if not any(se.subentry_type == "ai_task_data" for se in entry.subentries.values()):
            hass.config_entries.async_add_subentry(
                entry,
                ConfigSubentry(
                    data=MappingProxyType(RECOMMENDED_AI_TASK_OPTIONS),
                    subentry_type="ai_task_data",
                    title=DEFAULT_AI_TASK_NAME,
                    unique_id=None,
                ),
            )


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migra entries di versione 0 alla versione 1 e normalizza le opzioni."""
    version = entry.version
    LOGGER.debug("Starting migration for entry %s, current version: %s", entry.entry_id, version)

    if version <= 1:
        data = dict(entry.data)
        options = dict(entry.options)

        # llm_hass_api poteva essere lista ([assist] o [LLM_API_ASSIST]) o bool o assente
        raw_val = options.get(CONF_LLM_HASS_API, data.get(CONF_LLM_HASS_API))
        if isinstance(raw_val, list):
            options[CONF_LLM_HASS_API] = (
                "assist" in raw_val or ha_llm.LLM_API_ASSIST in raw_val
            )
        elif isinstance(raw_val, bool):
            options[CONF_LLM_HASS_API] = raw_val
        elif raw_val is None:
            options.setdefault(CONF_LLM_HASS_API, False)
        else:
            options[CONF_LLM_HASS_API] = False

        # Se il prompt è presente ma vuoto/solo spazi, rimuovilo per permettere fallback al default runtime
        prompt = options.get(CONF_PROMPT)
        if isinstance(prompt, str) and not prompt.strip():
            options.pop(CONF_PROMPT, None)

        # Migrate subentries too
        updated_subentries = {}
        for subentry_id, subentry in entry.subentries.items():
            subentry_data = dict(subentry.data)
            raw_val = subentry_data.get(CONF_LLM_HASS_API)
            if isinstance(raw_val, list):
                subentry_data[CONF_LLM_HASS_API] = (
                    "assist" in raw_val or ha_llm.LLM_API_ASSIST in raw_val
                )
                updated_subentries[subentry_id] = subentry_data

        # Update entry with migrated subentries
        if updated_subentries:
            for subentry_id, new_data in updated_subentries.items():
                hass.config_entries.async_update_entry(
                    entry.subentries[subentry_id],
                    data=new_data
                )

        hass.config_entries.async_update_entry(entry, data=data, options=options, version=2)
        LOGGER.debug("Migration 0->1 completed for entry %s", entry.entry_id)
        return True

    LOGGER.debug("No migration needed for entry %s (version=%s)", entry.entry_id, version)
    return True

"""Config flow de l'intégration Pont d'Aquitaine."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_FEED_URL,
    CONF_KEYWORDS,
    CONF_SCAN_INTERVAL,
    CONF_TIMEZONE,
    DEFAULT_FEED_URL,
    DEFAULT_KEYWORDS,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DEFAULT_TIMEZONE,
    DOMAIN,
)


def _keywords_to_string(keywords: list[str]) -> str:
    return ", ".join(keywords)


def _string_to_keywords(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class AquitaineBridgeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_FEED_URL])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=user_input.get("name", DEFAULT_NAME),
                data={
                    CONF_FEED_URL: user_input[CONF_FEED_URL],
                    CONF_KEYWORDS: _string_to_keywords(user_input[CONF_KEYWORDS]),
                    CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                    CONF_TIMEZONE: user_input[CONF_TIMEZONE],
                },
            )

        data_schema = vol.Schema(
            {
                vol.Optional("name", default=DEFAULT_NAME): str,
                vol.Required(CONF_FEED_URL, default=DEFAULT_FEED_URL): str,
                vol.Required(CONF_KEYWORDS, default=_keywords_to_string(DEFAULT_KEYWORDS)): str,
                vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL_MINUTES): vol.All(
                    vol.Coerce(int), vol.Range(min=5, max=1440)
                ),
                vol.Required(
                    CONF_TIMEZONE, default=self.hass.config.time_zone or DEFAULT_TIMEZONE
                ): selector.TimeZoneSelector(),
            }
        )
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return AquitaineBridgeOptionsFlowHandler(config_entry)


class AquitaineBridgeOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES),
        )
        current_timezone = self.config_entry.options.get(
            CONF_TIMEZONE,
            self.config_entry.data.get(CONF_TIMEZONE, DEFAULT_TIMEZONE),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current_interval): vol.All(
                        vol.Coerce(int), vol.Range(min=5, max=1440)
                    ),
                    vol.Required(CONF_TIMEZONE, default=current_timezone): selector.TimeZoneSelector(),
                }
            ),
        )

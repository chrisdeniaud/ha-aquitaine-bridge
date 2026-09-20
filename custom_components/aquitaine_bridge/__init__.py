"""Intégration Pont d'Aquitaine : fermetures actuelles et à venir."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_FEED_URL,
    CONF_KEYWORDS,
    CONF_SCAN_INTERVAL,
    CONF_TIMEZONE,
    DEFAULT_FEED_URL,
    DEFAULT_KEYWORDS,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DEFAULT_TIMEZONE,
    DOMAIN,
)
from .coordinator import AquitaineBridgeCoordinator

PLATFORMS = ["sensor", "binary_sensor", "switch"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    feed_url = entry.data.get(CONF_FEED_URL, DEFAULT_FEED_URL)
    keywords = entry.data.get(CONF_KEYWORDS, DEFAULT_KEYWORDS)
    scan_interval_minutes = entry.options.get(
        CONF_SCAN_INTERVAL,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES),
    )
    display_timezone = entry.options.get(
        CONF_TIMEZONE,
        entry.data.get(CONF_TIMEZONE, DEFAULT_TIMEZONE),
    )

    coordinator = AquitaineBridgeCoordinator(
        hass,
        entry,
        feed_url=feed_url,
        keywords=keywords,
        display_timezone=display_timezone,
        update_interval=timedelta(minutes=scan_interval_minutes),
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded

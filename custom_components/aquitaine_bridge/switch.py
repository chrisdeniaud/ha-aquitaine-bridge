"""Switch pilotant l'affichage permanent du capteur de statut."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .coordinator import AquitaineBridgeCoordinator
from .entity import AquitaineBridgeEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: AquitaineBridgeCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AlwaysShowSwitch(coordinator, entry)])


class AlwaysShowSwitch(AquitaineBridgeEntity, SwitchEntity, RestoreEntity):
    """Quand activé, le capteur de statut reste disponible même sans fermeture prévue."""

    _attr_translation_key = "always_show"
    _attr_icon = "mdi:eye-check-outline"

    def __init__(self, coordinator: AquitaineBridgeCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "always_show")
        self._attr_is_on = False

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        self._attr_is_on = last_state is not None and last_state.state == "on"
        self.coordinator.always_show = self._attr_is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._attr_is_on = True
        self.coordinator.always_show = True
        self.async_write_ha_state()
        self.coordinator.async_update_listeners()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._attr_is_on = False
        self.coordinator.always_show = False
        self.async_write_ha_state()
        self.coordinator.async_update_listeners()

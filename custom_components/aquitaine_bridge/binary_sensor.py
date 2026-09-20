"""Capteur binaire indiquant si le pont est actuellement fermé."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AquitaineBridgeCoordinator
from .entity import AquitaineBridgeEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: AquitaineBridgeCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ClosedNowBinarySensor(coordinator, entry)])


class ClosedNowBinarySensor(AquitaineBridgeEntity, BinarySensorEntity):
    """Indique si une fermeture est en cours en ce moment."""

    _attr_translation_key = "closed_now"

    def __init__(self, coordinator: AquitaineBridgeCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "closed_now")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.is_closed

    @property
    def icon(self) -> str:
        return "mdi:bridge-lock" if self.is_on else "mdi:bridge"

    @property
    def extra_state_attributes(self):
        windows = self.coordinator.data.current_windows
        return {
            "fermetures_en_cours": [
                {"fin": w.end.isoformat(), "sens": w.label} for w in windows
            ],
        }

"""Capteurs de l'intégration Pont d'Aquitaine."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AquitaineBridgeCoordinator
from .entity import AquitaineBridgeEntity

_API_CHANGED_MESSAGE = "L'API a évolué, une mise à jour est nécessaire"
_NO_CLOSURE_MESSAGE = "Aucune fermeture du pont d'Aquitaine prévue"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: AquitaineBridgeCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            NextClosureSensor(coordinator, entry),
            LatestNewsSensor(coordinator, entry),
            StatusSensor(coordinator, entry),
        ]
    )


def _to_display_tz(dt: datetime, coordinator: AquitaineBridgeCoordinator) -> datetime:
    return dt.astimezone(coordinator.display_tz)


def _format_dt(dt: datetime, coordinator: AquitaineBridgeCoordinator) -> str:
    return _to_display_tz(dt, coordinator).strftime("%d/%m/%Y à %H:%M")


class NextClosureSensor(AquitaineBridgeEntity, SensorEntity):
    """Date/heure de la prochaine fermeture prévue."""

    _attr_translation_key = "next_closure"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:bridge"

    def __init__(self, coordinator: AquitaineBridgeCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "next_closure")

    @property
    def native_value(self):
        window = self.coordinator.data.next_window
        return window.start if window else None

    @property
    def extra_state_attributes(self):
        window = self.coordinator.data.next_window
        if window is None:
            return {"fermetures_a_venir": []}

        return {
            "fin": _to_display_tz(window.end, self.coordinator).isoformat(),
            "sens": window.label,
            "fermetures_a_venir": [
                {
                    "debut": _to_display_tz(w.start, self.coordinator).isoformat(),
                    "fin": _to_display_tz(w.end, self.coordinator).isoformat(),
                    "sens": w.label,
                }
                for w in self.coordinator.data.upcoming_windows
            ],
        }


class LatestNewsSensor(AquitaineBridgeEntity, SensorEntity):
    """Dernier communiqué DIR Atlantique concernant le pont."""

    _attr_translation_key = "latest_news"
    _attr_icon = "mdi:newspaper-variant"

    def __init__(self, coordinator: AquitaineBridgeCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "latest_news")

    @property
    def native_value(self):
        item = self.coordinator.data.latest_item
        return item.title if item else None

    @property
    def extra_state_attributes(self):
        item = self.coordinator.data.latest_item
        if item is None:
            return {}

        return {
            "lien": item.link,
            "publie_le": _to_display_tz(item.published, self.coordinator).isoformat(),
            "description": item.description,
            "nombre_fenetres_detectees": len(item.windows),
        }


class StatusSensor(AquitaineBridgeEntity, SensorEntity):
    """Résumé textuel de l'état du pont, pensé pour un affichage direct.

    Piloté par le switch "Toujours afficher" (`coordinator.always_show`) :
    - activé, sans fermeture prévue -> reste visible avec un message neutre.
    - désactivé, sans fermeture prévue -> l'entité devient indisponible pour
      ne pas encombrer un tableau de bord quand il n'y a rien à signaler.
    Une anomalie de structure du flux (`schema_changed`) est toujours
    signalée, quel que soit l'état du switch.
    """

    _attr_translation_key = "status"

    def __init__(self, coordinator: AquitaineBridgeCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "status")

    @property
    def _has_data(self) -> bool:
        data = self.coordinator.data
        return data.is_closed or data.next_window is not None

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        if self.coordinator.data.schema_changed:
            return True
        return self.coordinator.always_show or self._has_data

    @property
    def icon(self) -> str:
        if self.coordinator.data.schema_changed:
            return "mdi:alert-circle-outline"
        return "mdi:bridge-lock" if self.coordinator.data.is_closed else "mdi:bridge"

    @property
    def native_value(self) -> str | None:
        data = self.coordinator.data
        if data.schema_changed:
            return _API_CHANGED_MESSAGE

        if data.is_closed:
            window = data.current_windows[0]
            fin = _format_dt(window.end, self.coordinator)
            if window.label:
                return f"Fermeture en cours ({window.label}) jusqu'au {fin}"
            return f"Fermeture en cours jusqu'au {fin}"

        if data.next_window is not None:
            debut = _format_dt(data.next_window.start, self.coordinator)
            if data.next_window.label:
                return f"Prochaine fermeture le {debut} ({data.next_window.label})"
            return f"Prochaine fermeture le {debut}"

        return _NO_CLOSURE_MESSAGE

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data
        return {
            "api_a_evolue": data.schema_changed,
            "toujours_afficher": self.coordinator.always_show,
        }

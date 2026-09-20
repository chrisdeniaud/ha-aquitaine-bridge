"""Coordinator récupérant et filtrant le flux RSS des fermetures."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .parser import ClosureWindow, FeedItem, FeedStructureError, item_matches_keywords, parse_feed

_LOGGER = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 30


@dataclass
class AquitaineBridgeData:
    """Données consolidées exposées aux entités."""

    matched_items: list[FeedItem]
    current_windows: list[ClosureWindow]
    upcoming_windows: list[ClosureWindow]
    # True si le flux ne porte plus les champs attendus (title/link/date) :
    # signale que le module doit être mis à jour, sans faire planter le reste.
    schema_changed: bool = False

    @property
    def latest_item(self) -> FeedItem | None:
        return self.matched_items[0] if self.matched_items else None

    @property
    def next_window(self) -> ClosureWindow | None:
        return self.upcoming_windows[0] if self.upcoming_windows else None

    @property
    def is_closed(self) -> bool:
        return bool(self.current_windows)


class AquitaineBridgeCoordinator(DataUpdateCoordinator[AquitaineBridgeData]):
    """Récupère le flux RSS DIR Atlantique et en extrait les fermetures."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        feed_url: str,
        keywords: list[str],
        display_timezone: str,
        update_interval,
    ) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)
        self.entry = entry
        self.feed_url = feed_url
        self.keywords = keywords
        self.display_tz = ZoneInfo(display_timezone)
        # État du switch "Toujours afficher", piloté par switch.py et lu par
        # le capteur de statut ; ce n'est pas une donnée issue du flux RSS,
        # donc elle ne fait pas partie de AquitaineBridgeData.
        self.always_show = False

    async def _async_update_data(self) -> AquitaineBridgeData:
        session = async_get_clientsession(self.hass)

        try:
            async with asyncio.timeout(_REQUEST_TIMEOUT):
                response = await session.get(self.feed_url)
                response.raise_for_status()
                content = await response.read()
        except Exception as err:
            raise UpdateFailed(f"Erreur lors de la récupération du flux DIR Atlantique : {err}") from err

        try:
            items = parse_feed(content)
        except FeedStructureError as err:
            _LOGGER.warning("Structure du flux DIR Atlantique modifiée : %s", err)
            previous = self.data
            return AquitaineBridgeData(
                matched_items=previous.matched_items if previous else [],
                current_windows=previous.current_windows if previous else [],
                upcoming_windows=previous.upcoming_windows if previous else [],
                schema_changed=True,
            )
        except Exception as err:
            raise UpdateFailed(f"Erreur lors de l'analyse du flux DIR Atlantique : {err}") from err

        matched_items = [item for item in items if item_matches_keywords(item, self.keywords)]
        matched_items.sort(key=lambda item: item.published, reverse=True)

        now = dt_util.now()
        current_windows: list[ClosureWindow] = []
        upcoming_windows: list[ClosureWindow] = []

        for item in matched_items:
            for window in item.windows:
                if window.start <= now < window.end:
                    current_windows.append(window)
                elif window.start > now:
                    upcoming_windows.append(window)

        upcoming_windows.sort(key=lambda window: window.start)

        return AquitaineBridgeData(
            matched_items=matched_items,
            current_windows=current_windows,
            upcoming_windows=upcoming_windows,
        )

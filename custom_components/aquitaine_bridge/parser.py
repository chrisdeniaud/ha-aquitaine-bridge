"""Parsing du flux RSS DIR Atlantique et extraction des fenêtres de fermeture.

Le flux RSS ne fournit pas de dates de fermeture structurées : elles sont
écrites en texte libre dans la description de chaque article (ex. "du 19/09
à 22h au 20/09 à 13h (sens extérieur)"). L'extraction ci-dessous est donc
"best effort" : elle couvre les formulations observées sur le flux réel,
mais un article dont la description ne correspond à aucun motif connu est
tout de même conservé (sans fenêtre structurée) pour ne pas perdre
l'information brute.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

# Les dates écrites en texte libre dans le flux sont toujours en heure
# française (communiqués rédigés par la DIR Atlantique) : ce fuseau sert à
# l'interprétation des dates sources, indépendamment du fuseau d'affichage
# configuré par l'utilisateur.
SOURCE_TZ = ZoneInfo("Europe/Paris")

_DC_NAMESPACE = "{http://purl.org/dc/elements/1.1/}"

_MONTHS_FR = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5,
    "juin": 6, "juillet": 7, "août": 8, "aout": 8, "septembre": 9,
    "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12,
}
_WEEKDAY = r"(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+"

_SIDE_RE = re.compile(
    rf"(?:{_WEEKDAY})?"
    rf"(?:(?P<day_num>\d{{1,2}})/(?P<month_num>\d{{1,2}})"
    rf"|(?P<day_txt>\d{{1,2}})\s+(?P<month_txt>[a-zéûôàè]+))"
    rf"(?:\s+(?P<year>\d{{4}}))?"
    rf"\s*[\(à]?\s*(?P<hour>\d{{1,2}})\s*h\s*(?P<minute>\d{{2}})?",
    re.IGNORECASE,
)

_CLAUSE_RE = re.compile(
    r"du\s+(?P<start>.+?)\s+au\s+(?P<end>.+?)"
    r"(?:\s*\((?P<label>sens[^)]*)\))?"
    r"(?=\s*(?:,|;|\bet\b|\.|$))",
    re.IGNORECASE,
)

_SIMPLE_HOUR_RE = re.compile(
    r"de\s+(?P<h1>\d{1,2})\s*h\s*(?P<m1>\d{2})?\s*à\s*(?P<h2>\d{1,2})\s*h\s*(?P<m2>\d{2})?",
    re.IGNORECASE,
)

_LE_DATE_HOUR_RE = re.compile(
    r"Le\s+(?P<day_num>\d{1,2})/(?P<month_num>\d{1,2})\s+de\s+"
    r"(?P<h1>\d{1,2})\s*h\s*(?P<m1>\d{2})?\s*à\s*(?P<h2>\d{1,2})\s*h\s*(?P<m2>\d{2})?",
    re.IGNORECASE,
)

_UNTIL_RE = re.compile(
    rf"jusqu.au\s+(?:{_WEEKDAY})?"
    rf"(?:(?P<day_num>\d{{1,2}})/(?P<month_num>\d{{1,2}})"
    rf"|(?P<day_txt>\d{{1,2}})\s+(?P<month_txt>[a-zéûôàè]+))"
    rf"\s+(?P<year>\d{{4}})\s*à\s*(?P<hour>\d{{1,2}})\s*h\s*(?P<minute>\d{{2}})?",
    re.IGNORECASE,
)

_TITLE_DATE_RE = re.compile(
    rf"(?:{_WEEKDAY})?(?:(?P<day_num>\d{{1,2}})/(?P<month_num>\d{{1,2}})"
    rf"|(?P<day_txt>\d{{1,2}})\s+(?P<month_txt>[a-zéûôàè]+))"
    rf"(?:\s+(?P<year>\d{{4}}))?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ClosureWindow:
    """Une plage de fermeture extraite d'un article."""

    start: datetime
    end: datetime
    label: str | None


@dataclass(frozen=True)
class FeedItem:
    """Un article du flux RSS DIR Atlantique."""

    title: str
    link: str
    description: str
    published: datetime
    windows: list[ClosureWindow]


def _resolve_year(month: int, published: datetime) -> int:
    """Déduit l'année d'une date sans année à partir de la date de publication.

    Le flux n'indique jamais l'année pour les dates au format JJ/MM : on part
    du principe que l'événement est proche de la publication, en gérant le
    passage d'une année sur l'autre (ex. article de décembre pour une
    fermeture en janvier suivant).
    """
    year = published.year
    delta = month - published.month
    if delta < -6:
        year += 1
    elif delta > 6:
        year -= 1
    return year


def _month_from_groups(match: re.Match) -> int | None:
    if match.group("day_num"):
        return int(match.group("month_num"))
    month_name = match.group("month_txt").lower()
    return _MONTHS_FR.get(month_name)


def _day_from_groups(match: re.Match) -> int:
    return int(match.group("day_num") or match.group("day_txt"))


def _parse_side(text: str, published: datetime) -> datetime | None:
    match = _SIDE_RE.search(text)
    if not match:
        return None
    month = _month_from_groups(match)
    if month is None:
        return None
    day = _day_from_groups(match)
    year = int(match.group("year")) if match.group("year") else _resolve_year(month, published)
    hour = int(match.group("hour"))
    minute = int(match.group("minute") or 0)
    try:
        return datetime(year, month, day, hour, minute, tzinfo=SOURCE_TZ)
    except ValueError:
        return None


def _parse_title_date(title: str, published: datetime) -> datetime | None:
    match = _TITLE_DATE_RE.search(title)
    if not match:
        return None
    month = _month_from_groups(match)
    if month is None:
        return None
    day = _day_from_groups(match)
    year = int(match.group("year")) if match.group("year") else _resolve_year(month, published)
    try:
        return datetime(year, month, day, tzinfo=SOURCE_TZ)
    except ValueError:
        return None


def extract_closure_windows(title: str, description: str, published: datetime) -> list[ClosureWindow]:
    """Extrait les fenêtres de fermeture d'un article (best effort)."""
    windows: list[ClosureWindow] = []

    for match in _CLAUSE_RE.finditer(description):
        start = _parse_side(match.group("start"), published)
        end = _parse_side(match.group("end"), published)
        if start is None or end is None:
            continue
        label = match.group("label")
        windows.append(ClosureWindow(start, end, label.strip() if label else None))

    if windows:
        return windows

    until_match = _UNTIL_RE.search(description)
    if until_match:
        month = _month_from_groups(until_match)
        if month is not None:
            day = _day_from_groups(until_match)
            year = int(until_match.group("year"))
            hour = int(until_match.group("hour"))
            minute = int(until_match.group("minute") or 0)
            try:
                end = datetime(year, month, day, hour, minute, tzinfo=SOURCE_TZ)
                return [ClosureWindow(published, end, None)]
            except ValueError:
                pass

    le_match = _LE_DATE_HOUR_RE.search(description)
    if le_match:
        month = int(le_match.group("month_num"))
        day = int(le_match.group("day_num"))
        year = _resolve_year(month, published)
        h1, m1 = int(le_match.group("h1")), int(le_match.group("m1") or 0)
        h2, m2 = int(le_match.group("h2")), int(le_match.group("m2") or 0)
        try:
            start = datetime(year, month, day, h1, m1, tzinfo=SOURCE_TZ)
            end = datetime(year, month, day, h2, m2, tzinfo=SOURCE_TZ)
            return [ClosureWindow(start, end, None)]
        except ValueError:
            pass

    simple_match = _SIMPLE_HOUR_RE.search(description)
    if simple_match:
        base_date = _parse_title_date(title, published)
        if base_date is not None:
            h1, m1 = int(simple_match.group("h1")), int(simple_match.group("m1") or 0)
            h2, m2 = int(simple_match.group("h2")), int(simple_match.group("m2") or 0)
            start = base_date.replace(hour=h1, minute=m1)
            end = base_date.replace(hour=h2, minute=m2)
            windows.append(ClosureWindow(start, end, None))

    return windows


def _parse_pub_date(item: ElementTree.Element) -> datetime | None:
    dc_date = item.findtext(f"{_DC_NAMESPACE}date")
    if dc_date:
        try:
            return datetime.fromisoformat(dc_date.replace("Z", "+00:00")).astimezone(SOURCE_TZ)
        except ValueError:
            pass

    raw_date = item.findtext("date")
    if raw_date:
        try:
            return datetime.strptime(raw_date.strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=SOURCE_TZ)
        except ValueError:
            pass

    return None


class FeedStructureError(Exception):
    """Levée quand les champs utilisés par l'intégration ont disparu du flux.

    Ne réagit qu'aux champs effectivement exploités ici (title/link/date) :
    un flux qui évolue ailleurs (ajout/suppression d'autres balises,
    changement d'ordre, etc.) ne doit pas déclencher cette erreur.
    """


def validate_feed_structure(root: ElementTree.Element) -> None:
    """Vérifie que les champs exploités par le parseur sont toujours présents.

    Un flux ponctuellement vide (aucun `<item>`) n'est pas une anomalie de
    structure : ce n'est que si des articles existent mais qu'aucun d'entre
    eux ne porte plus les champs attendus que l'on considère que l'API a
    changé de forme.
    """
    items = list(root.iter("item"))
    if not items:
        return

    has_title = any((item_el.findtext("title") or "").strip() for item_el in items)
    has_link = any((item_el.findtext("link") or "").strip() for item_el in items)
    has_date = any(
        (item_el.findtext(f"{_DC_NAMESPACE}date") or item_el.findtext("date") or "").strip()
        for item_el in items
    )

    if not (has_title and has_link and has_date):
        missing = [
            name
            for name, present in (("title", has_title), ("link", has_link), ("date", has_date))
            if not present
        ]
        raise FeedStructureError(
            f"Champs attendus absents de tous les articles du flux : {', '.join(missing)}"
        )


def parse_feed(xml_content: bytes) -> list[FeedItem]:
    """Parse le flux RSS et retourne les articles avec leurs fenêtres extraites.

    Lève `FeedStructureError` si les champs utilisés (title/link/date) ont
    disparu de tous les articles, signe que la structure du flux a changé.
    """
    root = ElementTree.fromstring(xml_content)
    validate_feed_structure(root)
    items: list[FeedItem] = []

    for item_el in root.iter("item"):
        title = (item_el.findtext("title") or "").strip()
        link = (item_el.findtext("link") or "").strip()
        description = (item_el.findtext("description") or "").strip()
        published = _parse_pub_date(item_el)
        if not title or not link or published is None:
            continue

        windows = extract_closure_windows(title, description, published)
        items.append(FeedItem(title, link, description, published, windows))

    return items


def item_matches_keywords(item: FeedItem, keywords: list[str]) -> bool:
    """Vérifie si le titre ou le lien de l'article contient un des mots-clés."""
    haystack = f"{item.title} {item.link}".casefold()
    return any(keyword.casefold() in haystack for keyword in keywords)

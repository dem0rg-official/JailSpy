#!/usr/bin/env python3
"""JailSpy — server tracker for Roblox Jailbreak."""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import curses
import json
import locale
import logging
import os
import re
import select
import shutil
import signal
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
import urllib.error
import urllib.request
from urllib.parse import quote, urlencode

LOG_PATH = Path.home() / ".local" / "share" / "jailspy" / "jailspy.log"
log = logging.getLogger("jailspy")


def setup_logging() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)


SITE_URL = "https://jailbreakchangelogs.com/robberies"
__version__ = "0.2.3"
ROBLOX_PLACE_ID = "606849621"
MUFFIN_API = "https://api.muffinhook.site"
MUFFIN_TOKEN_PATH = Path.home() / ".local" / "share" / "jailspy" / "muffinhook-token"
MUFFIN_POLL_SECONDS = 5.0
MUFFIN_ROBBERIES = {
    "1": "Rising Bank", "2": "Jewelry Store", "3": "Museum", "4": "Power Plant",
    "5": "Passenger Train", "6": "Cargo Train", "7": "Cargo Ship", "8": "Cargo Plane",
    "12": "Bank Truck", "14": "Tomb", "15": "Casino", "16": "Mansion", "17": "Oil Rig",
}
CONFIG_PATH = Path.home() / ".config" / "jailspy" / "config.json"
DEFAULT_STATE = Path.home() / ".local" / "share" / "jailspy" / "storage-state.json"
REFRESH_SECONDS = 1.0
FEED_REFRESH_SECONDS = 60.0  # reload the page only if no WebSocket frame arrived for this long
INPUT_POLL_SECONDS = 0.02
RENDER_INTERVAL_SECONDS = 0.5
CLIENT_CHECK_SECONDS = 2.0
AUTO_RETRY_SECONDS = 5.0
EARLY_EXIT_SECONDS = 60.0
DEFAULT_PITY_DELAY = 210.0
DEFAULT_MAX_PLAYERS = 25
SERVER_ID_WIDTH = 36
RESTART_EXIT_CODE = 75
PROVIDERS = ("jailbreakchangelogs", "muffinhook")

# Physical-key mapping so hotkeys work on the Russian (ЙЦУКЕН) layout.
RU_TO_EN = dict(zip("йцукенгшщзхъфывапролджэячсмитьбю.", "qwertyuiop[]asdfghjkl;'zxcvbnm,./"))


def normalize_key(ch: str) -> str:
    low = ch.casefold()
    return RU_TO_EN.get(low, low)

TRANSLATIONS: dict[str, dict[str, str]] = {
    "ru": {
        "app_title": "JAILSPY",
        "tagline": "Трекер серверов для вашего фарма",
        "live": "LIVE",
        "connecting": "ПОДКЛЮЧЕНИЕ…",
        "active": "Активных",
        "updated": "Обновление",
        "filter": "Фильтр",
        "all_robberies": "все ограбления",
        "change": "изменить",
        "clear": "сбросить",
        "error": "Ошибка",
        "robbery": "Ограбление",
        "status": "Статус",
        "status_open": "Открыто",
        "status_active": "Активно",
        "status_unknown": "Неизвестно",
        "time": "Время",
        "server": "Сервер",
        "total": "Всего",
        "criminals": "Крим",
        "cops": "Копы",
        "region": "Регион",
        "full": "Полон",
        "yes": "Да",
        "no": "Нет",
        "no_id": "нет ID",
        "auto_off": "АВТО: выключено",
        "auto_running": "АВТО: {marker} · запуск #{launches} · процесс работает {elapsed}с · сервер {job}",
        "auto_state": "АВТО: {marker} · {phase}",
        "auto_error": "Авто-ошибка",
        "select": "выбор",
        "join": "подключиться",
        "auto": "авто",
        "full_filter": "полные",
        "open_filter": "готовые",
        "count_filter": "лимит игроков",
        "max_players": "макс. игроков",
        "pity": "pity",
        "delay": "задержка",
        "language": "язык",
        "on": "ВКЛ",
        "off": "ВЫКЛ",
        "status_open": "Открыто",
        "status_active": "Активно",
        "status_unknown": "Неизвестно",
        "status_closed": "Завершено",
        "set_max_players": "макс. игроков",
        "invalid_number": "Некорректное число",
        "filter_key": "фильтр",
        "reload": "обновить",
        "quit": "выход",
        "no_rows": "Нет активных ограблений",
        "no_candidate": "жду подходящий активный сервер",
        "refreshing": "обновляю список серверов перед подключением",
        "waiting_process": "Sober запущен, жду завершения",
        "process_done": "процесс завершён",
        "early_exit": "клиент закрыт раньше минуты, повторный запуск",
        "next_launch": "следующий запуск через",
        "launch_sent": "Подключение к {name} отправлено",
        "auto_enabled": "Автоцикл включён для {marker}",
        "auto_disabled": "Автоподключение остановлено",
        "no_selection": "Нет подходящего ограбления для автоподключения",
        "reconnect": "Переподключение запрошено",
        "no_server_id": "У записи нет server ID",
        "sober_missing": "Sober не найден: установите org.vinegarhq.Sober для автоподключения",
        "no_opener": "Не найден flatpak или xdg-open",
        "roblox_running": "запущен",
        "roblox_closed": "закрыт",
        "launches": "Запусков",
        "last_launch": "Последний запуск",
        "client": "Roblox-клиент",
        "never": "никогда",
        "filters": "Фильтры",
        "skip_full": "пропускать полные",
        "only_open": "только открытые",
        "max_players": "макс. игроков",
        "pity_on": "вкл",
        "pity_off": "выкл",
        "pity_status": "Pity cooldown",
        "wizard_title": "JailSpy — первоначальная настройка",
        "choose_language": "Выберите язык / Choose language",
        "russian": "Русский",
        "english": "English",
        "choose_provider": "Выберите источник данных",
        "provider_only": "Jailbreak Changelogs (WebSocket)",
        "provider_muffin": "MuffinHook (muffinhook.site)",
        "settings": "настройки",
        "source": "Источник",
        "token": "Токен",
        "change_token": "Сменить токен",
        "token_keep": "Пустой ввод + Enter оставит текущий токен.",
        "ok": "ОК",
        "back": "назад",
        "edit_value": "изменить",
        "ws_data_error": "ошибка данных WebSocket",
        "restart_note": "Источник или токен изменён, перезапускаю…",
        "muffin_howto": "1. Войдите через Discord на https://www.muffinhook.site в своём браузере.\n2. Откройте DevTools (F12) → Application/Storage → Local Storage → https://www.muffinhook.site.\n3. Скопируйте значение ключа muffin_auth_token.",
        "muffin_unauthorized": "MuffinHook отклонил токен (401). Запустите ./run.sh --setup и вставьте новый.",
        "auth_title": "Авторизация",
        "auth_success": "Сессия сохранена.",
        "auth_howto": "1. Войдите на {url} в своём браузере.\n2. Откройте DevTools (F12) → Application/Storage → Cookies → jailbreakchangelogs.com.\n3. Скопируйте значение cookie jbcl_token.",
        "auth_paste": "Вставьте токен (ввод скрыт), Enter — отмена: ",
        "auth_invalid": "Токен пустой или содержит пробелы, ничего не сохранено.",
        "auth_migrated": "Найдена сохранённая сессия, использую её.",
        "setup_done": "Настройка завершена. Запускаю dashboard…",
        "browser_unknown": "браузер по умолчанию",
        "login_required": "Сайт требует вход. Запустите настройку: ./run.sh --setup",
        "enter_value": "Введите значение",
        "seconds": "сек",
        "invalid_number": "Некорректное число",
    },
    "en": {
        "app_title": "JAILSPY",
        "tagline": "Server Tracker for Your Grind",
        "live": "LIVE",
        "connecting": "CONNECTING…",
        "active": "Active",
        "updated": "Updated",
        "filter": "Filter",
        "all_robberies": "all robberies",
        "change": "edit",
        "clear": "clear",
        "error": "Error",
        "robbery": "Robbery",
        "status": "Status",
        "time": "Time",
        "server": "Server",
        "total": "Total",
        "criminals": "Crim",
        "cops": "Cops",
        "region": "Region",
        "full": "Full",
        "yes": "Yes",
        "no": "No",
        "no_id": "no ID",
        "auto_off": "AUTO: off",
        "auto_running": "AUTO: {marker} · launch #{launches} · process running {elapsed}s · server {job}",
        "auto_state": "AUTO: {marker} · {phase}",
        "auto_error": "Auto error",
        "select": "select",
        "join": "join",
        "auto": "auto",
        "full_filter": "full",
        "open_filter": "ready",
        "count_filter": "player limit",
        "max_players": "max players",
        "pity": "pity",
        "delay": "delay",
        "language": "language",
        "on": "ON",
        "off": "OFF",
        "status_open": "Open",
        "status_active": "Active",
        "status_unknown": "Unknown",
        "status_closed": "Completed",
        "set_max_players": "max players",
        "invalid_number": "Invalid number",
        "filter_key": "filter",
        "reload": "reload",
        "quit": "quit",
        "no_rows": "No active robberies",
        "no_candidate": "waiting for a matching active server",
        "refreshing": "refreshing server list before joining",
        "waiting_process": "Sober launched, waiting for exit",
        "process_done": "process exited",
        "early_exit": "client closed within a minute, relaunching",
        "next_launch": "next launch in",
        "launch_sent": "Connection to {name} sent",
        "auto_enabled": "Auto cycle enabled for {marker}",
        "auto_disabled": "Auto-join stopped",
        "no_selection": "No matching robbery to auto-join",
        "reconnect": "Reconnect requested",
        "no_server_id": "The record has no server ID",
        "sober_missing": "Sober not found: install org.vinegarhq.Sober for auto-join",
        "no_opener": "Neither flatpak nor xdg-open was found",
        "roblox_running": "running",
        "roblox_closed": "closed",
        "launches": "Launches",
        "last_launch": "Last launch",
        "client": "Roblox client",
        "never": "never",
        "filters": "Filters",
        "skip_full": "skip full",
        "only_open": "open only",
        "max_players": "max players",
        "pity_on": "on",
        "pity_off": "off",
        "pity_status": "Pity cooldown",
        "wizard_title": "JailSpy — first-run setup",
        "choose_language": "Choose language / Выберите язык",
        "russian": "Русский",
        "english": "English",
        "choose_provider": "Choose data source",
        "provider_only": "Jailbreak Changelogs (WebSocket)",
        "provider_muffin": "MuffinHook (muffinhook.site)",
        "settings": "settings",
        "source": "Source",
        "token": "Token",
        "change_token": "Change token",
        "token_keep": "Empty input + Enter keeps the current token.",
        "ok": "OK",
        "back": "back",
        "edit_value": "edit",
        "ws_data_error": "WebSocket data error",
        "restart_note": "Source or token changed, restarting…",
        "muffin_howto": "1. Sign in with Discord at https://www.muffinhook.site in your own browser.\n2. Open DevTools (F12) → Application/Storage → Local Storage → https://www.muffinhook.site.\n3. Copy the value of the muffin_auth_token key.",
        "muffin_unauthorized": "MuffinHook rejected the token (401). Run ./run.sh --setup and paste a new one.",
        "auth_title": "Authentication",
        "auth_success": "Session saved.",
        "auth_howto": "1. Sign in at {url} in your own browser.\n2. Open DevTools (F12) → Application/Storage → Cookies → jailbreakchangelogs.com.\n3. Copy the value of the jbcl_token cookie.",
        "auth_paste": "Paste the token (input hidden), Enter to cancel: ",
        "auth_invalid": "Token is empty or contains spaces, nothing saved.",
        "auth_migrated": "Found a saved session, using it.",
        "setup_done": "Setup complete. Starting dashboard…",
        "browser_unknown": "default browser",
        "login_required": "The site requires sign-in. Run setup: ./run.sh --setup",
        "enter_value": "Enter value",
        "seconds": "sec",
        "invalid_number": "Invalid number",
    },
}


class Translator:
    def __init__(self, language: str):
        self.language = language if language in TRANSLATIONS else "ru"

    def __call__(self, key: str, **values: Any) -> str:
        text = TRANSLATIONS[self.language].get(key, TRANSLATIONS["en"].get(key, key))
        return text.format(**values) if values else text


@dataclass(frozen=True)
class Robbery:
    name: str
    marker: str
    status: str
    status_code: int
    opening_time: str
    job_id: str
    server_time: str
    players: str
    total_players: int | None
    criminals: int | None
    cops: int | None
    region: str
    server_full: bool
    timestamp: str
    raw: dict[str, Any]
    source_id: str = ""

    @property
    def joinable(self) -> bool:
        return bool(self.job_id)

    @property
    def timer(self) -> str:
        """Backward-compatible duration view for callers of the old feed model."""
        return _format_timer(self.raw)

    @property
    def location(self) -> str:
        return self.region

    @property
    def join_uri(self) -> str | None:
        if not self.job_id:
            return None
        return f"roblox://experiences/start?placeId={ROBLOX_PLACE_ID}&gameInstanceId={quote(self.job_id, safe='')}"


@dataclass
class JoinFilters:
    skip_full: bool = False
    only_open: bool = False
    player_count: bool = False
    max_players: int = DEFAULT_MAX_PLAYERS


@dataclass
class SessionTelemetry:
    launches: int = 0
    last_launch: float = 0.0


@dataclass
class AutoJoin:
    enabled: bool = False
    marker: str = ""
    process: subprocess.Popen[Any] | None = None
    current_job: str = ""
    last_job: str = ""
    phase: str = "off"
    last_error: str = ""
    retry_at: float = 0.0
    launches: int = 0
    started_at: float = 0.0
    pity_enabled: bool = False
    pity_delay: float = DEFAULT_PITY_DELAY
    filters: JoinFilters = field(default_factory=JoinFilters)

    def stop(self, phase: str = "off") -> None:
        if self.process is not None and self.process.poll() is None:
            try:
                self.process.terminate()
            except OSError:
                pass
        self.process = None
        self.current_job = ""
        self.enabled = False
        self.phase = phase
        self.retry_at = 0.0


def _first(obj: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        value = obj.get(key)
        if value not in (None, ""):
            return value
    return default


def _number(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return max(0, int(value))
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _nested_number(objects: list[Any], keys: tuple[str, ...]) -> int | None:
    for obj in objects:
        if isinstance(obj, dict):
            value = _first(obj, *keys, default=None)
            parsed = _number(value)
            if parsed is not None:
                return parsed
    return None


def _status(value: Any) -> tuple[str, int]:
    if isinstance(value, str):
        if value.strip().isdigit():
            value = int(value.strip())
        else:
            lowered = value.casefold()
            if lowered in {"open", "ready"}:
                value = 1
            elif lowered in {"active", "started", "ongoing"}:
                value = 2
            elif lowered in {"closed", "complete", "completed", "finished"}:
                value = 3
    code = int(value) if isinstance(value, (int, float)) else 0
    labels = {1: "Open", 2: "Active", 3: "Completed"}
    return labels.get(code, "Unknown"), code


def _localized_status(status_code: int, t: Translator) -> str:
    return {
        1: t("status_open"),
        2: t("status_active"),
        3: t("status_closed"),
    }.get(status_code, t("status_unknown"))


def _timestamp_sort_key(value: str) -> tuple[int, Any]:
    if not value:
        return (0, "")
    try:
        return (2, float(value))
    except ValueError:
        pass
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return (2, parsed.timestamp())
    except ValueError:
        return (1, value)


def _format_timer(raw: dict[str, Any]) -> str:
    for key in ("duration", "timer", "elapsed", "time_left", "remaining"):
        value = raw.get(key)
        if value not in (None, ""):
            if isinstance(value, (int, float)):
                seconds = max(0, int(value))
                return f"{seconds // 60:02d}:{seconds % 60:02d}"
            return str(value)
    value = raw.get("server_time")
    return str(value) if value not in (None, "") else "—"


def _format_opening_time(value: Any) -> str:
    if value in (None, ""):
        return "—"
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value)).strftime("%H:%M:%S")
        except (OverflowError, OSError, ValueError):
            return "—"
    text = str(value).strip()
    # Keep the clock displayed by the provider. Converting an ISO timestamp to
    # the local timezone would make the table jump between users' time zones.
    time_match = re.search(r"(?:T|\s)(\d{2}:\d{2}:\d{2})", text)
    if time_match:
        return time_match.group(1)
    if len(text) >= 8 and text[2] == ":" and text[5] == ":":
        return text[:8]
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.strftime("%H:%M:%S")
    except ValueError:
        return "—"


def _region(item: dict[str, Any], server: dict[str, Any]) -> str:
    data = item.get("region_data")
    if not isinstance(data, dict):
        data = server.get("region") if isinstance(server.get("region"), dict) else {}
    if isinstance(data, dict):
        parts = [
            _first(data, "city"),
            _first(data, "regionName", "region"),
            _first(data, "country", "country_code", "countryCode"),
        ]
        value = ", ".join(str(part) for part in parts if part)
        if value:
            return value
    return str(_first(item, "region", "region_name", "country_code", default=_first(server, "region_name", "country_code", default="—")) or "—")


def _is_server_full(criminals: int | None, cops: int | None) -> bool:
    if criminals is None or cops is None:
        return False
    # A criminal slot exists for each cop plus four baseline criminal slots.
    # The global criminal cap is 18.
    maximum_criminals = min(18, 4 * (cops + 1))
    return criminals >= maximum_criminals


def normalize_feed(items: Any) -> list[Robbery]:
    if isinstance(items, dict):
        for key in ("robberies", "items", "data", "results"):
            if isinstance(items.get(key), list):
                items = items[key]
                break
        else:
            items = []
    if not isinstance(items, list):
        return []

    result: list[Robbery] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_status = item.get("status")
        status, status_code = _status(raw_status)
        if status_code not in (1, 2):
            continue
        server = item.get("server") if isinstance(item.get("server"), dict) else {}
        teams = item.get("teams") if isinstance(item.get("teams"), dict) else {}
        team_counts = item.get("team_counts") if isinstance(item.get("team_counts"), dict) else {}
        server_teams = server.get("teams") if isinstance(server.get("teams"), dict) else {}
        count_objects = [item, server, teams, team_counts, server_teams]

        players_value = _first(server, "players", "player_count", "players_count", default=_first(item, "players", "player_count", "players_count"))
        total_players = len(players_value) if isinstance(players_value, list) else _number(players_value)
        criminals = _nested_number(count_objects, ("criminals", "criminal", "criminal_count", "criminals_count"))
        cops = _nested_number(count_objects, ("cops", "cop", "cop_count", "cops_count", "police"))
        if isinstance(players_value, list):
            teams_list = [str(p.get("team", "")).casefold() for p in players_value if isinstance(p, dict)]
            if teams_list:
                if criminals is None:
                    criminals = sum(1 for x in teams_list if x == "criminal")
                if cops is None:
                    cops = sum(1 for x in teams_list if x in ("cop", "police"))
        if total_players is None and criminals is not None and cops is not None:
            total_players = criminals + cops
        players = str(total_players) if total_players is not None else "—"

        job_id = str(_first(item, "job_id", "jobId", default=_first(server, "job_id", "jobId")))
        name = str(_first(item, "name", "display_name", "marker_name", default="—"))
        marker = str(_first(item, "marker_name", default=name))
        timestamp = str(_first(item, "timestamp", "opened_at", "open_time", "created_at", default=""))
        opening_value = _first(item, "opening_time", "opened_at", "open_time", "timestamp", default="")
        result.append(Robbery(
            name=name,
            marker=marker,
            status=status,
            status_code=status_code,
            opening_time=_format_opening_time(opening_value),
            job_id=job_id,
            server_time=str(_first(server, "server_time", default=_first(item, "server_time", default="—"))),
            players=players,
            total_players=total_players,
            criminals=criminals,
            cops=cops,
            region=_region(item, server),
            server_full=_is_server_full(criminals, cops),
            timestamp=timestamp,
            raw=item,
        ))
    return result


def _muffin_status(value: Any) -> tuple[str, int]:
    text = str(value or "").strip().casefold()
    if text.startswith("open"):
        return "Open", 1
    if text in ("in robbery", "robbery in progress"):
        return "Active", 2
    return "Unknown", 0


def normalize_muffin_feed(data: Any) -> list[Robbery]:
    """Turn the /export/servers payload into one row per open or active robbery."""
    top: dict[str, Any] = {}
    if isinstance(data, dict):
        top = data
        data = data.get("servers")
    if not isinstance(data, list):
        return []
    rows: list[Robbery] = []
    for server in data:
        if not isinstance(server, dict):
            continue
        info = server.get("ServerInfo") if isinstance(server.get("ServerInfo"), dict) else {}
        job_id = str(info.get("JobID") or "")
        robberies = server.get("RobberyData")
        if not job_id or not isinstance(robberies, dict):
            continue
        criminals = _number(info.get("CrimCount"))
        cops = _number(info.get("PoliceCount"))
        total = criminals + cops if criminals is not None and cops is not None else None
        updated = server.get("lastUpdated")
        if isinstance(updated, dict):
            updated = updated.get("$date")
        timestamp = str(updated or "")
        geo = server.get("RegionData")
        geo = geo.get("geolocation") if isinstance(geo, dict) else None
        region = ", ".join(str(geo[k]) for k in ("city", "regionName", "country") if isinstance(geo, dict) and geo.get(k)) or "—"
        source_id = str(server.get("_id") or "")
        for robbery_id, entry in robberies.items():
            entry = entry if isinstance(entry, dict) else {}
            descs = entry.get("Descs") if isinstance(entry.get("Descs"), dict) else {}
            status, code = _muffin_status(descs.get("Status"))
            if code not in (1, 2):
                continue
            name = str(entry.get("name") or MUFFIN_ROBBERIES.get(str(robbery_id), f"Robbery {robbery_id}"))
            rows.append(Robbery(
                name=name, marker=name, status=status, status_code=code,
                opening_time=_format_opening_time(timestamp), job_id=job_id, server_time="—",
                players=str(total) if total is not None else "—", total_players=total,
                criminals=criminals, cops=cops, region=region,
                server_full=_is_server_full(criminals, cops), timestamp=timestamp,
                raw=server, source_id=source_id,
            ))
    return rows


def muffin_request(token: str, server_id: str | None = None) -> Any:
    url = MUFFIN_API + "/export/servers" + (f"?{urlencode({'id': server_id})}" if server_id else "")
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json", "User-Agent": "JailSpy"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError("muffin_unauthorized" if exc.code in (401, 403) else f"MuffinHook HTTP {exc.code}") from exc
    except ValueError as exc:
        raise RuntimeError(f"MuffinHook: bad JSON ({exc})") from exc


def resolve_join_uri(row: Robbery, token: str = "") -> str | None:
    """Return the Roblox URI for a row. MuffinHook rows need a second request for the real job ID."""
    if not row.source_id:
        return row.join_uri
    info = muffin_request(token, row.source_id)
    if not isinstance(info, dict):
        return None
    place = quote(str(info.get("placeId") or ROBLOX_PLACE_ID), safe="")
    if info.get("launchData"):
        return f"roblox://experiences/start?placeId={place}&launchData={quote(str(info['launchData']), safe='')}"
    if info.get("private") and info.get("accessCode"):
        return f"roblox://navigation/share_links?code={quote(str(info['accessCode']), safe='')}&type=Server"
    if info.get("jobId"):
        return f"roblox://experiences/start?placeId={place}&gameInstanceId={quote(str(info['jobId']), safe='')}"
    return None


def latest_for_marker(rows: list[Robbery], marker: str, filters: JoinFilters | None = None, exclude_job: str = "") -> Robbery | None:
    candidates = [row for row in rows if row.marker == marker and row.joinable and not (exclude_job and row.job_id == exclude_job)]
    if filters is not None:
        candidates = [
            row for row in candidates
            if not (filters.skip_full and row.server_full)
            and not (filters.only_open and row.status_code != 1)
            and not (filters.player_count and (row.total_players is None or row.total_players > filters.max_players))
        ]
    return max(candidates, key=lambda row: _timestamp_sort_key(row.timestamp)) if candidates else None


def filtered_rows(rows: list[Robbery], filter_text: str) -> list[Robbery]:
    needle = filter_text.strip().casefold()
    if not needle:
        return rows
    return [row for row in rows if needle in row.name.casefold() or needle in row.marker.casefold()]


def _display_width(text: str) -> int:
    return len(text)


def _clip(text: Any, width: int) -> str:
    value = " ".join(str(text).replace("\n", " ").split())
    if width <= 0:
        return ""
    if _display_width(value) > width:
        return value[: max(1, width - 1)] + "…"
    return value.ljust(width)


def _safe_add(screen: Any, y: int, x: int, text: str, attr: int = 0, width: int | None = None) -> None:
    try:
        if width is not None:
            text = text[:width]
        screen.addstr(y, x, text, attr)
    except curses.error:
        pass


def _init_colors() -> dict[str, int]:
    colors = {"normal": curses.A_NORMAL, "title": curses.A_BOLD, "green": curses.A_BOLD, "yellow": curses.A_BOLD, "red": curses.A_BOLD, "cyan": curses.A_BOLD, "dim": curses.A_DIM, "selected": curses.A_REVERSE | curses.A_BOLD}
    if not curses.has_colors():
        return colors
    curses.start_color()
    curses.use_default_colors()
    pairs = [(1, curses.COLOR_CYAN), (2, curses.COLOR_GREEN), (3, curses.COLOR_YELLOW), (4, curses.COLOR_RED), (5, curses.COLOR_WHITE)]
    for pair, color in pairs:
        curses.init_pair(pair, color, -1)
    colors.update({"title": curses.color_pair(1) | curses.A_BOLD, "cyan": curses.color_pair(1) | curses.A_BOLD, "green": curses.color_pair(2) | curses.A_BOLD, "yellow": curses.color_pair(3) | curses.A_BOLD, "red": curses.color_pair(4) | curses.A_BOLD, "normal": curses.color_pair(5)})
    return colors


def _table_columns(t: Translator, width: int) -> list[tuple[str, int]]:
    columns = [
        ("№", 3), (t("robbery"), 20), (t("status"), 10), (t("time"), 8),
        (t("server"), SERVER_ID_WIDTH), (t("total"), 5), (t("criminals"), 5),
        (t("cops"), 5), (t("full"), 5),
    ]
    gap = 2 * (len(columns) - 1)
    # First squeeze everything except the full server ID, then let the ID shrink too.
    for minimums in ([2, 12, 6, 8, SERVER_ID_WIDTH, 3, 3, 3, 3], [2, 8, 6, 8, 8, 3, 3, 3, 3]):
        while sum(size for _, size in columns) + gap > max(1, width):
            candidates = [i for i, (_, size) in enumerate(columns) if size > minimums[i]]
            if not candidates:
                break
            index = max(candidates, key=lambda i: columns[i][1])
            title, size = columns[index]
            columns[index] = (title, size - 1)
    return columns


def _row_cells(t: Translator, row: Robbery) -> list[str]:
    return [
        "", row.name, _localized_status(row.status_code, t), row.opening_time,
        row.job_id or t("no_id"),
        str(row.total_players if row.total_players is not None else "—"),
        str(row.criminals if row.criminals is not None else "—"),
        str(row.cops if row.cops is not None else "—"),
        t("yes") if row.server_full else t("no"),
    ]


def render_ui(screen: Any, colors: dict[str, int], t: Translator, rows: list[Robbery], selected: int, filter_text: str, connected: bool, error: str | None, auto: AutoJoin, telemetry: SessionTelemetry, message: str, client_running: bool, prompt_label: str = "", prompt_buffer: str | None = None, status_note: str = "") -> None:
    height, width = screen.getmaxyx()
    screen.erase()
    visible = filtered_rows(rows, filter_text)
    selected = max(0, min(selected, max(0, len(visible) - 1)))
    state = t("live") if connected else t("connecting")
    state_attr = colors["green"] if connected else colors["yellow"]

    _safe_add(screen, 0, 0, f" {t('app_title')} — {t('tagline')} ", colors["title"], width)
    _safe_add(screen, 1, 1, f"{t('active')}: {len(visible)}/{len(rows)}   {t('updated')}: {time.strftime('%H:%M:%S')}", colors["dim"], width - 2)
    _safe_add(screen, 0, max(0, width - len(state) - 3), f" {state} ", state_attr, len(state) + 2)
    if status_note:
        _safe_add(screen, 0, max(0, width - len(state) - 6 - len(status_note)), f" {status_note} ", colors["yellow"], len(status_note) + 2)
    filter_label = filter_text or t("all_robberies")
    if prompt_buffer is not None:
        _safe_add(screen, 2, 1, f"{prompt_label}: {prompt_buffer}█   [Enter] OK   [Esc]", colors["yellow"], width - 2)
    else:
        _safe_add(screen, 2, 1, f"{t('filter')}: [{filter_label}]   [/] {t('change')}   [C] {t('clear')}", colors["cyan"], width - 2)
    if error:
        _safe_add(screen, 3, 1, f"{t('error')}: {error}", colors["red"], width - 2)

    top = 5
    bottom = max(top + 2, height - 10)
    columns = _table_columns(t, width)
    header = "  ".join(_clip(title, size) for title, size in columns)
    _safe_add(screen, top, 0, header, colors["title"], width)
    _safe_add(screen, top + 1, 0, "─" * min(width, len(header)), colors["dim"])
    max_rows = max(0, bottom - top - 1)
    start = max(0, min(selected - max_rows + 1, max(0, len(visible) - max_rows)))
    for line, row in enumerate(visible[start:start + max_rows], start):
        y = top + 2 + line - start
        attr = colors["selected"] if line == selected else colors["normal"]
        cells = _row_cells(t, row)
        cells[0] = str(line + 1)
        x = 0
        for index, ((_, column_width), cell) in enumerate(zip(columns, cells)):
            cell_attr = attr
            if line != selected and index == 2:
                cell_attr = colors["green"] if row.status_code == 1 else colors["yellow"]
            if line != selected and index == 8 and row.server_full:
                cell_attr = colors["red"]
            _safe_add(screen, y, x, _clip(cell, column_width), cell_attr, column_width)
            x += column_width + 2

    panel_y = max(top + 3, height - 9)
    _safe_add(screen, panel_y, 1, "─" * max(1, width - 2), colors["dim"])
    if auto.enabled:
        if auto.process is not None and auto.process.poll() is None:
            elapsed = int(time.monotonic() - auto.started_at)
            auto_text = t("auto_running", marker=auto.marker, launches=auto.launches, elapsed=elapsed, job=auto.current_job)
        else:
            auto_text = t("auto_state", marker=auto.marker, phase=t(auto.phase))
            remaining = auto.retry_at - time.monotonic()
            if auto.retry_at and remaining > 0:
                auto_text += f" · {t('next_launch')}: {int(remaining) + 1} {t('seconds')}"
        _safe_add(screen, panel_y + 1, 1, auto_text, colors["green"], width - 2)
    else:
        _safe_add(screen, panel_y + 1, 1, t("auto_off"), colors["dim"], width - 2)
    on, off = colors["green"], colors["dim"]
    count_on = auto.filters.player_count
    parts = [
        (f"[F] {t('skip_full')}: {'ON' if auto.filters.skip_full else 'OFF'}", auto.filters.skip_full),
        (f"[O] {t('only_open')}: {'ON' if auto.filters.only_open else 'OFF'}", auto.filters.only_open),
        (f"[N] {t('count_filter')}: {'≤' + str(auto.filters.max_players) if count_on else 'OFF'}", count_on),
    ]
    x = 1
    for text, active in parts:
        _safe_add(screen, panel_y + 2, x, text, on if active else off, max(1, width - x - 1))
        x += len(text) + 3
    if auto.last_error:
        _safe_add(screen, panel_y + 3, 1, f"{t('auto_error')}: {err_text(t, auto.last_error)}", colors["red"], width - 2)
    elif message:
        _safe_add(screen, panel_y + 3, 1, message, colors["cyan"], width - 2)
    client_state = t("roblox_running") if client_running else t("roblox_closed")
    last_launch = time.strftime("%H:%M:%S", time.localtime(telemetry.last_launch)) if telemetry.last_launch else t("never")
    telemetry_text = f"{t('client')}: {client_state} · {t('launches')}: {telemetry.launches} · {t('last_launch')}: {last_launch} · "
    _safe_add(screen, panel_y + 5, 1, telemetry_text, on if client_running else off, width - 2)
    pity_text = f"{t('pity_status')}: {t('pity_on') if auto.pity_enabled else t('pity_off')} ({int(auto.pity_delay)} {t('seconds')})"
    _safe_add(screen, panel_y + 5, 1 + len(telemetry_text), pity_text, on if auto.pity_enabled else off, max(1, width - len(telemetry_text) - 2))
    _safe_add(screen, height - 3, 1, "[↑↓] " + t("select") + "   [Enter] " + t("join") + "   [A] " + t("auto") + "   [P] " + t("pity") + "   [R] " + t("reload") + "   [S] " + t("settings") + "   [Q] " + t("quit"), colors["cyan"], width - 2)
    screen.refresh()


def read_command(timeout: float) -> str | None:
    ready, _, _ = select.select([sys.stdin], [], [], timeout)
    return sys.stdin.readline().strip().lower() if ready else None


LEGACY_STATE = Path.home() / ".local" / "share" / "hyperchrome-tracker" / "storage-state.json"


def read_muffin_token(path: Path = MUFFIN_TOKEN_PATH) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _write_private(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)


def save_token(provider: str, token: str, state_path: Path) -> None:
    """Store the pasted token: a cookie in the Playwright state, or a plain private file for MuffinHook."""
    if provider == "muffinhook":
        _write_private(MUFFIN_TOKEN_PATH, token)
        return
    cookies: list[dict[str, Any]] = []
    if state_path.exists():
        try:
            old = json.loads(state_path.read_text(encoding="utf-8"))
            cookies = [c for c in old.get("cookies", []) if c.get("name") != "jbcl_token"]
        except (OSError, ValueError):
            cookies = []
    cookies.append({
        "name": "jbcl_token", "value": token, "domain": ".jailbreakchangelogs.com",
        "path": "/", "expires": -1, "httpOnly": False, "secure": True, "sameSite": "Lax",
    })
    _write_private(state_path, json.dumps({"cookies": cookies, "origins": []}))


def has_session(provider: str, state_path: Path) -> bool:
    if provider == "muffinhook":
        return bool(read_muffin_token())
    if state_path.exists():
        return True
    if LEGACY_STATE.exists():
        state_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(LEGACY_STATE, state_path)
        state_path.chmod(0o600)
        return True
    return False


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) and data.get("setup_complete") else None
    except (OSError, ValueError):
        return None


def save_config(config: dict[str, Any], path: Path = CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


# ---------------------------------------------------------------- TUI screens

@contextlib.contextmanager
def tui_screen() -> Any:
    """Own the terminal for the setup wizard and for token prompts outside the dashboard."""
    os.environ.setdefault("ESCDELAY", "25")
    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error:
        pass
    screen = curses.initscr()
    try:
        curses.noecho()
        curses.cbreak()
        screen.keypad(True)
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        yield screen, _init_colors()
    finally:
        try:
            curses.nocbreak()
            screen.keypad(False)
            curses.echo()
            curses.endwin()
        except curses.error:
            pass


def _wrap_lines(text: str, width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        lines.extend(textwrap.wrap(paragraph, max(10, width)) or [""])
    return lines


def _draw_screen(screen: Any, colors: dict[str, int], t: Translator, title: str, body: str) -> tuple[int, int]:
    """Draw the common header, title and wrapped body. Returns the next free row and the screen width."""
    height, width = screen.getmaxyx()
    screen.erase()
    _safe_add(screen, 0, 0, f" {t('app_title')} — {t('tagline')} ", colors["title"], width)
    _safe_add(screen, 2, 2, title, colors["cyan"], width - 4)
    _safe_add(screen, 3, 2, "─" * max(1, width - 4), colors["dim"])
    y = 5
    for line in _wrap_lines(body, width - 4) if body else []:
        if y >= height - 2:
            break
        _safe_add(screen, y, 2, line, colors["normal"], width - 4)
        y += 1
    return y + (1 if body else 0), width


def tui_choice(screen: Any, colors: dict[str, int], t: Translator, title: str, options: list[str], body: str = "", index: int = 0) -> int | None:
    """Pick one option with arrows or digits. Enter confirms, Esc returns None."""
    index = max(0, min(index, len(options) - 1))
    screen.nodelay(False)
    while True:
        y, width = _draw_screen(screen, colors, t, title, body)
        height = screen.getmaxyx()[0]
        for number, option in enumerate(options):
            if y + number >= height - 2:
                break
            attr = colors["selected"] if number == index else colors["normal"]
            _safe_add(screen, y + number, 2, f" [{number + 1}] {option} ".ljust(max(1, width - 4)), attr, width - 4)
        _safe_add(screen, height - 1, 2, f"[↑↓] {t('select')}   [Enter] {t('ok')}   [Esc] {t('back')}", colors["dim"], width - 4)
        screen.refresh()
        try:
            key = screen.get_wch()
        except curses.error:
            continue
        if key == curses.KEY_UP or (isinstance(key, str) and normalize_key(key) == "k"):
            index = (index - 1) % len(options)
        elif key == curses.KEY_DOWN or (isinstance(key, str) and normalize_key(key) == "j"):
            index = (index + 1) % len(options)
        elif key in ("\n", "\r", curses.KEY_ENTER):
            return index
        elif key == "\x1b":
            return None
        elif isinstance(key, str) and key.isdigit() and 1 <= int(key) <= len(options):
            index = int(key) - 1


def tui_input(screen: Any, colors: dict[str, int], t: Translator, title: str, label: str, body: str = "", hidden: bool = False, initial: str = "", error: str = "") -> str | None:
    """Single-line input. Hidden mode shows dots. Enter confirms, Esc returns None."""
    buffer = initial
    screen.nodelay(False)
    while True:
        y, width = _draw_screen(screen, colors, t, title, body)
        height = screen.getmaxyx()[0]
        shown = ("•" * len(buffer)) if hidden else buffer
        room = max(1, width - 8 - len(label))
        _safe_add(screen, y, 2, f"{label}: ", colors["yellow"], width - 4)
        _safe_add(screen, y, 4 + len(label), shown[-room:] + "█", colors["normal"], room + 1)
        if hidden and buffer:
            _safe_add(screen, y + 1, 2, f"({len(buffer)})", colors["dim"], width - 4)
        if error:
            _safe_add(screen, y + 3, 2, error, colors["red"], width - 4)
        _safe_add(screen, height - 1, 2, f"[Enter] {t('ok')}   [Esc] {t('back')}", colors["dim"], width - 4)
        screen.refresh()
        try:
            key = screen.get_wch()
        except curses.error:
            continue
        if key in ("\n", "\r", curses.KEY_ENTER):
            return buffer.strip().strip('"\'')
        if key == "\x1b":
            return None
        if key in ("\x7f", "\b", curses.KEY_BACKSPACE):
            buffer = buffer[:-1]
        elif isinstance(key, str) and key.isprintable() and len(buffer) < 4096:
            buffer += key
        error = ""


def tui_token_step(screen: Any, colors: dict[str, int], t: Translator, provider: str, state_path: Path, can_keep: bool) -> str:
    """Ask for the token. Returns 'saved', 'kept' (empty input, existing token) or 'back' (Esc)."""
    if provider == "muffinhook":
        body = t("muffin_howto")
    else:
        body = t("auth_howto", url=SITE_URL)
    if can_keep:
        body += "\n\n" + t("token_keep")
    error = ""
    while True:
        value = tui_input(screen, colors, t, t("auth_title"), t("token"), body, hidden=True, error=error)
        if value is None:
            return "back"
        if not value:
            if can_keep:
                return "kept"
            error = t("auth_invalid")
            continue
        if any(ch.isspace() for ch in value):
            error = t("auth_invalid")
            continue
        save_token(provider, value, state_path)
        return "saved"


def provider_title(t: Translator, provider: str) -> str:
    return t("provider_muffin") if provider == "muffinhook" else t("provider_only")


def setup_wizard(screen: Any, colors: dict[str, int], existing: dict[str, Any], config_path: Path, state_path: Path) -> dict[str, Any] | None:
    """Language -> source -> token. Esc steps back; Esc on the first step cancels."""
    language = str(existing.get("language", "ru"))
    provider = str(existing.get("provider", PROVIDERS[0]))
    step = 0
    while True:
        t = Translator(language)
        if step == 0:
            picked = tui_choice(screen, colors, Translator("en"), f"{t('wizard_title')} · {t('choose_language')}", ["Русский", "English"], index=0 if language == "ru" else 1)
            if picked is None:
                return None
            language = ("ru", "en")[picked]
            step = 1
        elif step == 1:
            picked = tui_choice(screen, colors, t, f"{t('wizard_title')} · {t('choose_provider')}", [provider_title(t, p) for p in PROVIDERS], index=PROVIDERS.index(provider) if provider in PROVIDERS else 0)
            if picked is None:
                step = 0
                continue
            provider = PROVIDERS[picked]
            step = 2
        else:
            result = tui_token_step(screen, colors, t, provider, state_path, has_session(provider, state_path) and provider == existing.get("provider", provider))
            if result == "back":
                step = 1
                continue
            config = {
                "setup_complete": True,
                "language": language,
                "provider": provider,
                "state_path": str(state_path),
                "pity_cooldown_enabled": bool(existing.get("pity_cooldown_enabled", False)),
                "pity_delay": float(existing.get("pity_delay", DEFAULT_PITY_DELAY)),
            }
            save_config(config, config_path)
            return config


def run_setup(force: bool = False, config_path: Path = CONFIG_PATH, state_path: Path = DEFAULT_STATE) -> dict[str, Any]:
    existing = load_config(config_path)
    if existing and not force:
        return existing
    with tui_screen() as (screen, colors):
        config = setup_wizard(screen, colors, existing or {}, config_path, state_path)
    if config is None:
        if existing:
            return existing
        raise SystemExit(1)
    return config


def settings_menu(screen: Any, colors: dict[str, int], t: Translator, config: dict[str, Any], config_path: Path, state_path: Path, auto: AutoJoin) -> tuple[Translator, bool]:
    """Modal settings screen. Returns the (possibly new) translator and whether the data source must restart."""
    restart = False
    index = 0
    while True:
        language = str(config.get("language", "ru"))
        provider = str(config.get("provider", PROVIDERS[0]))
        items = [
            f"{t('language').capitalize()}: {'Русский' if language == 'ru' else 'English'}",
            f"{t('source')}: {provider_title(t, provider)}",
            f"{t('delay').capitalize()} ({t('seconds')}): {int(auto.pity_delay)}",
            t("change_token"),
            t("back").capitalize(),
        ]
        picked = tui_choice(screen, colors, t, t("settings").capitalize(), items, index=index)
        if picked is None or picked == 4:
            break
        index = picked
        if picked == 0:
            choice = tui_choice(screen, colors, t, t("language").capitalize(), ["Русский", "English"], index=0 if language == "ru" else 1)
            if choice is not None:
                config["language"] = ("ru", "en")[choice]
                save_config(config, config_path)
                t = Translator(config["language"])
        elif picked == 1:
            choice = tui_choice(screen, colors, t, t("source"), [provider_title(t, p) for p in PROVIDERS], index=PROVIDERS.index(provider) if provider in PROVIDERS else 0)
            if choice is None or PROVIDERS[choice] == provider:
                continue
            new_provider = PROVIDERS[choice]
            if not has_session(new_provider, state_path):
                if tui_token_step(screen, colors, t, new_provider, state_path, False) != "saved":
                    continue
            config["provider"] = new_provider
            save_config(config, config_path)
            restart = True
            break
        elif picked == 2:
            error = ""
            while True:
                value = tui_input(screen, colors, t, t("settings").capitalize(), f"{t('delay').capitalize()} ({t('seconds')})", initial=str(int(auto.pity_delay)), error=error)
                if value is None:
                    break
                if value.isdigit():
                    auto.pity_delay = float(int(value))
                    config["pity_delay"] = auto.pity_delay
                    save_config(config, config_path)
                    break
                error = t("invalid_number")
        elif picked == 3:
            if tui_token_step(screen, colors, t, provider, state_path, True) == "saved":
                restart = True
                break
    return t, restart


def _process_rows() -> list[tuple[int, str]]:
    try:
        result = subprocess.run(["ps", "-eo", "pid=,comm="], capture_output=True, text=True, timeout=3, check=False)
    except (OSError, subprocess.SubprocessError):
        return []
    rows: list[tuple[int, str]] = []
    names = {"sober", "robloxplayerbeta", "robloxplayer", "roblox"}
    for line in result.stdout.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and parts[1].casefold() in names:
            try:
                pid = int(parts[0])
            except ValueError:
                continue
            if pid != os.getpid():
                rows.append((pid, parts[1]))
    return rows


def roblox_client_running() -> bool:
    return bool(_process_rows())


def close_roblox_clients() -> int:
    processes = _process_rows()
    for pid, _ in processes:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            continue
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and _process_rows():
        time.sleep(0.1)
    for pid, _ in _process_rows():
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    return len(processes)


def err_text(t: Translator, error: Any) -> str:
    """Translate an error that carries a translation key; pass other text through."""
    text = str(error)
    return t(text) if text in TRANSLATIONS["en"] else text


def sober_available() -> bool:
    if not shutil.which("flatpak"):
        return False
    return subprocess.run(["flatpak", "info", "org.vinegarhq.Sober"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False).returncode == 0


def launch_sober(uri: str, require_sober: bool = False) -> subprocess.Popen[Any]:
    if sober_available():
        command = ["flatpak", "run", "org.vinegarhq.Sober", uri]
    elif require_sober:
        raise RuntimeError("sober_missing")
    else:
        opener = shutil.which("xdg-open")
        if not opener:
            raise RuntimeError("no_opener")
        command = [opener, uri]
    close_roblox_clients()
    return subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


async def run(args: argparse.Namespace) -> int:
    config_path = Path(args.config).expanduser()
    state_path_arg = Path(args.state).expanduser() if args.state else None
    config = run_setup(force=args.setup or args.login, config_path=config_path, state_path=state_path_arg or DEFAULT_STATE)
    language = str(config.get("language", "ru"))
    t = Translator(language)
    state_path = state_path_arg or Path(str(config.get("state_path", DEFAULT_STATE))).expanduser()
    log.info("start: state=%s exists=%s", state_path, state_path.exists())
    provider = str(config.get("provider", PROVIDERS[0]))
    muffin = provider == "muffinhook"
    if not has_session(provider, state_path):
        with tui_screen() as (setup_screen, setup_colors):
            token_result = tui_token_step(setup_screen, setup_colors, t, provider, state_path, False)
        if token_result != "saved":
            log.error("exit: no session")
            print(t("login_required"), f"(log: {LOG_PATH})")
            return 2
    muffin_token = read_muffin_token() if muffin else ""

    from playwright.async_api import BrowserContext, TimeoutError as PlaywrightTimeoutError, async_playwright

    async with async_playwright() as pw:
        browser = context = page = None
        if not muffin:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(storage_state=str(state_path) if state_path.exists() else None)
            page = await context.new_page()
        feed: list[Robbery] = []
        last_frame_at = time.monotonic()
        frame_seq = 0
        connected = False
        last_error: str | None = None

        async def handle_ws(ws: Any) -> None:
            nonlocal connected, last_error, feed
            if "jailbreakchangelogs" not in ws.url:
                return
            connected = True

            async def on_frame(payload: Any) -> None:
                nonlocal feed, last_error, last_frame_at, frame_seq
                try:
                    message = json.loads(payload if isinstance(payload, str) else payload.decode())
                    if message.get("action") == "recent_robberies" and message.get("data") is not None:
                        feed = normalize_feed(message["data"])
                        last_frame_at = time.monotonic()
                        frame_seq += 1
                        log.info("feed updated: %d active", len(feed))
                except (ValueError, UnicodeDecodeError, AttributeError) as exc:
                    last_error = f"{t('ws_data_error')}: {exc}"

            ws.on("framereceived", on_frame)

        if page is not None:
            page.on("websocket", lambda ws: asyncio.create_task(handle_ws(ws)))
        os.environ.setdefault("ESCDELAY", "25")
        try:
            locale.setlocale(locale.LC_ALL, "")
        except locale.Error:
            pass
        screen = curses.initscr()
        colors: dict[str, int] = {}
        auto = AutoJoin(
            pity_enabled=bool(config.get("pity_cooldown_enabled", False)),
            pity_delay=float(config.get("pity_delay", DEFAULT_PITY_DELAY)),
        )
        telemetry = SessionTelemetry()
        selected = 0
        filter_text = ""
        message = ""
        prompt_mode: str | None = None
        prompt_buffer = ""
        reload_task: asyncio.Task[None] | None = None
        auto_refresh_task: asyncio.Task[None] | None = None
        auto_refresh_seq = 0
        muffin_task: asyncio.Task[None] | None = None
        restart = False

        async def fetch_muffin() -> None:
            nonlocal feed, connected, last_error, last_frame_at, frame_seq
            try:
                data = await asyncio.to_thread(muffin_request, muffin_token)
                feed = normalize_muffin_feed(data)
                connected = True
                last_error = None
                last_frame_at = time.monotonic()
                frame_seq += 1
                log.info("muffinhook feed updated: %d active", len(feed))
            except (OSError, RuntimeError) as exc:
                connected = False
                text = str(exc)
                last_error = err_text(t, text)
                log.warning("muffinhook fetch failed: %s", exc)

        async def muffin_poller() -> None:
            while True:
                await asyncio.sleep(MUFFIN_POLL_SECONDS)
                await fetch_muffin()

        try:
            curses.noecho()
            curses.cbreak()
            screen.keypad(True)
            screen.nodelay(True)
            curses.curs_set(0)
            colors = _init_colors()
            render_ui(screen, colors, t, feed, 0, "", False, None, auto, telemetry, "", False)
            if muffin:
                await fetch_muffin()
                muffin_task = asyncio.create_task(muffin_poller())
                body = ""
            else:
                await page.goto(SITE_URL, wait_until="domcontentloaded", timeout=60000)
                deadline = time.monotonic() + 8.0
                while not feed and time.monotonic() < deadline:
                    await asyncio.sleep(0.1)
                body = await page.locator("body").inner_text()
            last_frame_at = time.monotonic()
            dirty = True
            last_render = 0.0
            last_client_check = -CLIENT_CHECK_SECONDS
            client_running = False
            log.info("page loaded: url=%s ws_connected=%s feed=%d body_head=%r", page.url if page else "muffinhook", connected, len(feed), body[:120])
            if not muffin and not connected and not feed and any(token in body for token in ("Login", "Log in", "Войти")):
                last_error = f"{t('login_required')} (log: {LOG_PATH})"
                log.warning("login wall: no websocket and login text on page")

            async def refresh_feed() -> None:
                nonlocal connected, last_error
                if muffin:
                    await fetch_muffin()
                    return
                connected = False
                seq_before = frame_seq
                try:
                    await page.reload(wait_until="domcontentloaded", timeout=15000)
                    deadline_at = time.monotonic() + 10.0
                    while frame_seq == seq_before and time.monotonic() < deadline_at:
                        await asyncio.sleep(0.1)
                except PlaywrightTimeoutError as exc:
                    last_error = f"refresh timeout: {exc}"
                    log.warning("refresh timeout: %s", exc)

            while True:
                visible = filtered_rows(feed, filter_text)
                selected = max(0, min(selected, max(0, len(visible) - 1)))
                now = time.monotonic()
                if now - last_client_check >= CLIENT_CHECK_SECONDS:
                    client_running = await asyncio.to_thread(roblox_client_running)
                    last_client_check = now
                if dirty or now - last_render >= RENDER_INTERVAL_SECONDS:
                    prompt_labels = {"filter": t("filter"), "delay": f"{t('delay')} ({t('seconds')})", "max_players": t("max_players")}
                    render_ui(screen, colors, t, feed, selected, filter_text, connected, last_error, auto, telemetry, message, client_running,
                              prompt_labels.get(prompt_mode or "", ""), prompt_buffer if prompt_mode else None,
                              t("reconnect") if reload_task is not None and not reload_task.done() else "")
                    message = ""
                    dirty = False
                    last_render = now
                if (
                    not auto.enabled
                    and now - last_frame_at >= FEED_REFRESH_SECONDS
                    and (reload_task is None or reload_task.done())
                ):
                    log.warning("no feed frame for %ds, reloading page", FEED_REFRESH_SECONDS)
                    last_frame_at = now
                    reload_task = asyncio.create_task(refresh_feed())

                if auto.enabled:
                    if auto.process is not None:
                        if auto.process.poll() is not None:
                            auto.process = None
                            if time.monotonic() - auto.started_at < EARLY_EXIT_SECONDS:
                                delay = AUTO_RETRY_SECONDS
                                auto.phase = "early_exit"
                                log.info("client closed after %.0fs (<%ds), relaunching without pity", time.monotonic() - auto.started_at, EARLY_EXIT_SECONDS)
                            else:
                                delay = auto.pity_delay if auto.pity_enabled else AUTO_RETRY_SECONDS
                                auto.phase = "process_done"
                            auto.retry_at = time.monotonic() + delay
                    elif auto_refresh_task is None and time.monotonic() >= auto.retry_at:
                        auto_refresh_seq = frame_seq
                        auto.phase = "refreshing"
                        auto_refresh_task = asyncio.create_task(refresh_feed())
                    elif auto_refresh_task is not None and auto_refresh_task.done():
                        auto_refresh_task = None
                        candidate = latest_for_marker(feed, auto.marker, auto.filters, auto.last_job) if frame_seq != auto_refresh_seq else None
                        if candidate is None:
                            auto.phase = "no_candidate"
                            auto.retry_at = time.monotonic() + AUTO_RETRY_SECONDS
                        elif not candidate.joinable:
                            auto.phase = "no_server_id"
                            auto.retry_at = time.monotonic() + AUTO_RETRY_SECONDS
                        else:
                            try:
                                uri = await asyncio.to_thread(resolve_join_uri, candidate, muffin_token)
                                if not uri:
                                    raise RuntimeError("no_server_id")
                                auto.process = launch_sober(uri, require_sober=True)
                                auto.current_job = candidate.job_id
                                auto.last_job = candidate.job_id
                                auto.started_at = time.monotonic()
                                auto.launches += 1
                                telemetry.launches += 1
                                telemetry.last_launch = time.time()
                                auto.phase = "waiting_process"
                                auto.last_error = ""
                            except (OSError, RuntimeError) as exc:
                                auto.last_error = str(exc)
                                auto.phase = "error"
                                auto.retry_at = time.monotonic() + AUTO_RETRY_SECONDS

                try:
                    raw_key = screen.get_wch()
                except curses.error:
                    await asyncio.sleep(INPUT_POLL_SECONDS)
                    continue
                dirty = True

                if prompt_mode is not None:
                    if raw_key in ("\n", "\r", curses.KEY_ENTER):
                        if prompt_mode == "filter":
                            filter_text = prompt_buffer.strip()
                            selected = 0
                        elif prompt_buffer.strip().isdigit():
                            number = int(prompt_buffer.strip())
                            if prompt_mode == "delay":
                                auto.pity_delay = float(number)
                                config["pity_delay"] = auto.pity_delay
                                save_config(config, config_path)
                            elif prompt_mode == "max_players":
                                auto.filters.max_players = number
                                auto.filters.player_count = True
                        elif prompt_buffer.strip():
                            message = t("invalid_number")
                        prompt_mode, prompt_buffer = None, ""
                    elif raw_key == "\x1b":
                        prompt_mode, prompt_buffer = None, ""
                    elif raw_key in ("\x7f", "\b", curses.KEY_BACKSPACE):
                        prompt_buffer = prompt_buffer[:-1]
                    elif isinstance(raw_key, str) and raw_key.isprintable() and len(prompt_buffer) < 40:
                        prompt_buffer += raw_key
                    continue

                if raw_key == curses.KEY_UP:
                    action = "up"
                elif raw_key == curses.KEY_DOWN:
                    action = "down"
                elif raw_key in ("\n", "\r", curses.KEY_ENTER):
                    action = "enter"
                elif raw_key == "\x1b":
                    action = "q"
                elif isinstance(raw_key, str):
                    action = normalize_key(raw_key)
                else:
                    action = ""

                if action == "q":
                    break
                if action in ("up", "k"):
                    selected = max(0, selected - 1)
                elif action in ("down", "j"):
                    selected = min(max(0, len(visible) - 1), selected + 1)
                elif action == "/":
                    prompt_mode, prompt_buffer = "filter", filter_text
                elif action == "c":
                    filter_text = ""
                    selected = 0
                elif action == "r":
                    if reload_task is None or reload_task.done():
                        reload_task = asyncio.create_task(refresh_feed())
                elif action == "a":
                    if auto.enabled:
                        if auto_refresh_task is not None:
                            auto_refresh_task.cancel()
                            auto_refresh_task = None
                        auto.stop()
                        message = t("auto_disabled")
                    elif visible:
                        auto.enabled = True
                        auto.marker = visible[selected].marker
                        auto.last_job = ""
                        auto.phase = "refreshing"
                        auto.last_error = ""
                        auto.retry_at = 0.0
                        message = t("auto_enabled", marker=auto.marker)
                    else:
                        message = t("no_selection")
                elif action == "f":
                    auto.filters.skip_full = not auto.filters.skip_full
                elif action == "o":
                    auto.filters.only_open = not auto.filters.only_open
                elif action == "n":
                    if auto.filters.player_count:
                        auto.filters.player_count = False
                    else:
                        prompt_mode, prompt_buffer = "max_players", str(auto.filters.max_players)
                elif action == "s":
                    screen.nodelay(False)
                    t, restart = await asyncio.to_thread(settings_menu, screen, colors, t, config, config_path, state_path, auto)
                    screen.nodelay(True)
                    language = t.language
                    dirty = True
                    if restart:
                        break
                elif action == "p":
                    auto.pity_enabled = not auto.pity_enabled
                    config["pity_cooldown_enabled"] = auto.pity_enabled
                    save_config(config, config_path)
                elif action == "enter":
                    if visible:
                        row = visible[selected]
                        if row.joinable:
                            try:
                                uri = await asyncio.to_thread(resolve_join_uri, row, muffin_token)
                                if not uri:
                                    raise RuntimeError("no_server_id")
                                await asyncio.to_thread(launch_sober, uri)
                                telemetry.launches += 1
                                telemetry.last_launch = time.time()
                                message = t("launch_sent", name=row.name)
                            except (OSError, RuntimeError) as exc:
                                message = err_text(t, exc)
                        else:
                            message = t("no_server_id")
        finally:
            for task in (reload_task, auto_refresh_task, muffin_task):
                if task is not None:
                    task.cancel()
            auto.stop()
            try:
                curses.nocbreak()
                screen.keypad(False)
                curses.echo()
                curses.endwin()
            except curses.error:
                pass
            if context is not None:
                await context.close()
            if browser is not None:
                await browser.close()
    return RESTART_EXIT_CODE if restart else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="JailSpy server tracker TUI")
    parser.add_argument("--version", action="version", version=f"JailSpy {__version__}")
    parser.add_argument("--setup", action="store_true", help="re-run the setup wizard")
    parser.add_argument("--login", action="store_true", help="compatibility alias for --setup")
    parser.add_argument("--config", default=str(CONFIG_PATH), help="path to the config file")
    parser.add_argument("--state", default=None, help="path to the Playwright storage state JSON")
    return parser.parse_args()


if __name__ == "__main__":
    setup_logging()
    try:
        arguments = parse_args()
        code = asyncio.run(run(arguments))
        while code == RESTART_EXIT_CODE:
            arguments.setup = arguments.login = False
            code = asyncio.run(run(arguments))
        log.info("exit code=%s", code)
        raise SystemExit(code)
    except KeyboardInterrupt:
        raise SystemExit(130)
    except SystemExit:
        raise
    except Exception:
        log.exception("fatal error")
        import traceback

        traceback.print_exc()
        print(f"\nLog: {LOG_PATH}", file=sys.stderr)
        raise SystemExit(1)

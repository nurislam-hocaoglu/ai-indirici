"""
Sonarr Webhook Listener (aiohttp server).

Sonarr sends a webhook POST when an episode download completes (eventType=Download).
Triggering order: Bazarr subtitle search -> Jellyfin library scan -> Telegram notification.
"""

import logging
from typing import Optional

from aiohttp import web

from config import settings
from services.bazarr_api import BazarrError, bazarr
from services.jellyfin_api import JellyfinError, jellyfin

logger = logging.getLogger(__name__)

# Injected by bot/main.py at startup
_bot = None
_admin_chat_id: Optional[int] = None
# sonarr_series_id -> telegram chat_id (populated when user triggers a download)
_pending: dict[int, int] = {}


def set_bot(bot, admin_chat_id: int) -> None:
    global _bot, _admin_chat_id
    _bot = bot
    _admin_chat_id = admin_chat_id


def register_pending(sonarr_series_id: int, chat_id: int) -> None:
    """Register a chat_id waiting for a specific series to finish downloading."""
    _pending[sonarr_series_id] = chat_id
    logger.info(
        "Registered pending notification: series %s -> chat %s",
        sonarr_series_id,
        chat_id,
    )


async def _notify(chat_id: int, text: str) -> None:
    if _bot and chat_id:
        try:
            await _bot.send_message(chat_id, text, parse_mode="HTML")
        except Exception as exc:
            logger.error("Failed to send Telegram notification: %s", exc)


async def handle_sonarr_webhook(request: web.Request) -> web.Response:
    """
    Receives Sonarr webhook events.
    Relevant: eventType='Download' (episode grabbed and moved to library).
    """
    try:
        body = await request.json()
    except Exception:
        logger.warning("Webhook received non-JSON payload")
        return web.Response(status=400, text="Invalid JSON")

    event_type = body.get("eventType", "")
    logger.info("Sonarr webhook received: eventType=%s", event_type)

    if event_type == "Test":
        return web.Response(status=200, text="OK")

    if event_type != "Download":
        return web.Response(status=200, text="Ignored")

    series = body.get("series", {})
    episodes = body.get("episodes", [])
    sonarr_series_id: Optional[int] = series.get("id")
    series_title: str = series.get("title", "Bilinmeyen Dizi")

    if not sonarr_series_id:
        logger.error("Webhook payload missing series.id")
        return web.Response(status=422, text="Missing series.id")

    chat_id = _pending.get(sonarr_series_id, _admin_chat_id)

    ep_info = (
        ", ".join(
            f"S{ep.get('seasonNumber', 0):02d}E{ep.get('episodeNumber', 0):02d}"
            for ep in episodes
        )
        or "bilinmeyen bölüm"
    )

    # 1. Bazarr subtitle search
    try:
        await bazarr.search_series_subtitles(
            sonarr_series_id, language=settings.SUBTITLE_LANGUAGE
        )
        logger.info("Bazarr subtitle search triggered for series %s", sonarr_series_id)
    except BazarrError as e:
        logger.error("Bazarr subtitle search failed: %s", e)
        await _notify(
            chat_id,
            f"⚠️ <b>Bazarr Hatası</b>\n"
            f"Dizi: {series_title}\n"
            f"HTTP {e.status_code}: <code>{e.detail[:300]}</code>",
        )

    # 2. Jellyfin library refresh
    try:
        await jellyfin.refresh_library()
        logger.info("Jellyfin library refresh triggered")
    except JellyfinError as e:
        logger.error("Jellyfin refresh failed: %s", e)
        await _notify(
            chat_id,
            f"⚠️ <b>Jellyfin Hatası</b>\n"
            f"HTTP {e.status_code}: <code>{e.detail[:300]}</code>",
        )

    # 3. Notify user
    await _notify(
        chat_id,
        f"✅ <b>{series_title}</b> izlemeye hazır!\n"
        f"📥 İndirilen: {ep_info}\n"
        f"🔤 Türkçe altyazı aranıyor...\n"
        f"🎬 Jellyfin kütüphanesi taranıyor.",
    )

    # Remove from pending after first notification (series fully registered)
    _pending.pop(sonarr_series_id, None)

    return web.Response(status=200, text="OK")


def create_webhook_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/webhook/sonarr", handle_sonarr_webhook)
    return app

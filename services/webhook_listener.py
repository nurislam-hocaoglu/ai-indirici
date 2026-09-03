"""
Radarr Webhook Listener (aiohttp server).

Radarr sends a webhook POST when a movie download completes (eventType=Download).
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
# radarr_movie_id -> telegram chat_id (populated when user triggers a download)
_pending: dict[int, int] = {}
# radarr_movie_id or sonarr_series_id -> telegram chat_id (used to map downloaded subtitles back to the requesting user)
_pending_subtitles: dict[int, int] = {}


def set_bot(bot, admin_chat_id: int) -> None:
    global _bot, _admin_chat_id
    _bot = bot
    _admin_chat_id = admin_chat_id


def register_pending(radarr_movie_id: int, chat_id: int) -> None:
    """Register a chat_id waiting for a specific movie to finish downloading."""
    _pending[radarr_movie_id] = chat_id
    logger.info(
        "Registered pending notification: movie %s -> chat %s",
        radarr_movie_id,
        chat_id,
    )


async def _notify(chat_id: int, text: str) -> None:
    if _bot and chat_id:
        try:
            await _bot.send_message(chat_id, text, parse_mode="HTML")
        except Exception as exc:
            logger.error("Failed to send Telegram notification: %s", exc)


async def handle_radarr_webhook(request: web.Request) -> web.Response:
    """
    Receives Radarr webhook events.
    Relevant: eventType='Download' (movie grabbed and moved to library).
    """
    try:
        body = await request.json()
    except Exception:
        logger.warning("Radarr webhook received non-JSON payload")
        return web.Response(status=400, text="Invalid JSON")

    event_type = body.get("eventType", "")
    logger.info("Radarr webhook received: eventType=%s", event_type)

    if event_type == "Test":
        return web.Response(status=200, text="OK")

    if event_type != "Download":
        return web.Response(status=200, text="Ignored")

    movie = body.get("movie", {})
    radarr_movie_id: Optional[int] = movie.get("id")
    movie_title: str = movie.get("title", "Bilinmeyen Film")
    movie_year = movie.get("year", "")
    movie_file = body.get("movieFile", {})
    quality = movie_file.get("quality", "")

    if not radarr_movie_id:
        logger.error("Webhook payload missing movie.id")
        return web.Response(status=422, text="Missing movie.id")

    chat_id = _pending.get(radarr_movie_id, _admin_chat_id)

    # Store in pending subtitles to keep track for Bazarr callback
    if radarr_movie_id and chat_id:
        _pending_subtitles[radarr_movie_id] = chat_id

    # 1. Bazarr: Assign 'stand' profile and search subtitles (Turkish & English)
    try:
        await bazarr.search_movie_subtitles(
            radarr_movie_id, profile_name=settings.SUBTITLE_PROFILE
        )
        logger.info(
            "Bazarr subtitle search triggered for movie %s (profile: %s)",
            radarr_movie_id,
            settings.SUBTITLE_PROFILE,
        )
    except Exception as e:
        logger.warning("Bazarr subtitle search error: %s", e)

    # 2. Jellyfin library refresh (safe - does not block notification)
    try:
        await jellyfin.refresh_library()
        logger.info("Jellyfin library refresh triggered for movies")
    except Exception as e:
        logger.warning("Jellyfin refresh error: %s", e)

    # 3. Notify user - Guaranteed to run
    try:
        year_str = f" ({movie_year})" if movie_year else ""
        quality_str = f"\n📊 Kalite: {quality}" if quality else ""

        await _notify(
            chat_id,
            f"✅ <b>{movie_title}{year_str}</b> indirildi ve izlemeye hazır!\n"
            f"🎬 Jellyfin Filmler kütüphanesine eklendi.{quality_str}\n"
            f"🔤 <b>'stand'</b> altyazı profili uygulandı:\n"
            f"   • Türkçe 🇹🇷 ve İngilizce 🇬🇧 altyazılar indiriliyor.\n"
            f"💡 <i>Jellyfin'de filmi açtığınızda altyazılar otomatik olarak görünecektir.</i>",
        )
    except Exception as e:
        logger.error("Failed to send Telegram notification: %s", e)

    # Remove from pending after notification
    _pending.pop(radarr_movie_id, None)

    return web.Response(status=200, text="OK")


async def handle_sonarr_webhook(request: web.Request) -> web.Response:
    """Legacy handler for Sonarr webhook events."""
    try:
        body = await request.json()
    except Exception:
        return web.Response(status=400, text="Invalid JSON")

    event_type = body.get("eventType", "")
    if event_type == "Test":
        return web.Response(status=200, text="OK")
    if event_type != "Download":
        return web.Response(status=200, text="Ignored")

    series = body.get("series", {})
    sonarr_series_id: Optional[int] = series.get("id")
    series_title: str = series.get("title", "Bilinmeyen Dizi")

    chat_id = _pending.get(sonarr_series_id, _admin_chat_id)

    if sonarr_series_id and chat_id:
        _pending_subtitles[sonarr_series_id] = chat_id

    try:
        await jellyfin.refresh_library()
    except Exception as e:
        logger.error("Jellyfin refresh failed: %s", e)

    await _notify(
        chat_id,
        f"✅ <b>{series_title}</b> izlemeye hazır!\n"
        f"🎬 Jellyfin kütüphanesi güncellendi.",
    )
    _pending.pop(sonarr_series_id, None)
    return web.Response(status=200, text="OK")


async def handle_bazarr_webhook(request: web.Request) -> web.Response:
    """
    Receives Bazarr webhook events (supports both GET and POST).
    Fires when subtitles are downloaded.
    Refreshes Jellyfin library and notifies the user via Telegram.
    """
    path_param = request.query.get("path")
    body: dict = {}
    if request.can_read_body:
        try:
            body = await request.json()
        except Exception:
            pass

    logger.info("Bazarr webhook received (method=%s, path=%s, body=%s)", request.method, path_param, body)

    # Determine movie title from path or body
    movie_title = body.get("movie_title")
    series_title = body.get("series_title")
    lang_code = body.get("language_code", "")
    lang_name = body.get("language_name", "")

    if not movie_title and path_param:
        import os
        movie_title = os.path.basename(path_param.rstrip("/\\"))

    title = movie_title or series_title or "Film"

    # 1. Trigger Jellyfin library refresh immediately so new subtitles are indexed
    try:
        await jellyfin.refresh_library()
        logger.info("Jellyfin library refresh triggered by Bazarr webhook for %s", title)
    except Exception as e:
        logger.warning("Jellyfin refresh error from Bazarr webhook: %s", e)

    # 2. Identify target chat
    chat_id = _admin_chat_id
    radarr_movie_id_str = body.get("radarr_movie_id")
    if radarr_movie_id_str and str(radarr_movie_id_str).isdigit():
        radarr_id = int(radarr_movie_id_str)
        chat_id = _pending_subtitles.get(radarr_id, _admin_chat_id)

    # 3. Notify user via Telegram
    if chat_id:
        lang_lower = lang_code.lower() if lang_code else ""
        if "tr" in lang_lower or "tur" in lang_lower:
            lang_display = "Türkçe 🇹🇷"
        elif "en" in lang_lower or "eng" in lang_lower:
            lang_display = "İngilizce 🇬🇧"
        else:
            lang_display = "Türkçe 🇹🇷 & İngilizce 🇬🇧"

        try:
            await _notify(
                chat_id,
                f"🔤 <b>{title}</b> için <b>{lang_display}</b> altyazı indirildi!\n"
                f"🎬 Jellyfin'e entegre edildi, videoyu açtığınızda altyazı seçeneği hazır.",
            )
        except Exception as e:
            logger.error("Failed to send Bazarr subtitle notification: %s", e)

    return web.Response(status=200, text="OK")


def create_webhook_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/webhook/radarr", handle_radarr_webhook)
    app.router.add_post("/webhook/sonarr", handle_sonarr_webhook)
    app.router.add_get("/webhook/bazarr", handle_bazarr_webhook)
    app.router.add_post("/webhook/bazarr", handle_bazarr_webhook)
    return app

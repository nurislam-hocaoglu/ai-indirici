"""
Bot entry point.

Runs two concurrent async tasks:
  1. aiogram Dispatcher (Telegram long-polling)
  2. aiohttp server (Radarr webhook listener)
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to sys.path so config and services can be imported regardless of execution path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings
from bot.handlers import router
from services.jellyfin_api import jellyfin
from services.webhook_listener import create_webhook_app, set_bot


def _configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


async def _run_webhook_server() -> None:
    """Start the aiohttp webhook server."""
    app = create_webhook_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=settings.WEBHOOK_HOST, port=settings.WEBHOOK_PORT)
    await site.start()
    logging.getLogger(__name__).info(
        "Webhook server listening on %s:%s", settings.WEBHOOK_HOST, settings.WEBHOOK_PORT
    )
    # Keep running indefinitely
    while True:
        await asyncio.sleep(3600)


async def main() -> None:
    _configure_logging()
    logger = logging.getLogger(__name__)

    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Inject bot reference into webhook listener so it can send Telegram messages
    set_bot(bot, settings.ADMIN_CHAT_ID)

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    logger.info("Starting AI İndirici bot...")

    # Automatically configure Jellyfin users to show subtitles when playing
    try:
        await jellyfin.configure_auto_subtitles(preferred_language="tur", subtitle_mode="Always")
    except Exception as e:
        logger.warning("Could not auto-configure Jellyfin subtitles: %s", e)

    # Notify admin on startup
    try:
        await bot.send_message(
            settings.ADMIN_CHAT_ID,
            "🟢 <b>AI Film İndirici Bot başlatıldı (Radarr, Bazarr & Jellyfin).</b>",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning("Could not send startup notification: %s", e)

    # Run polling and webhook server concurrently
    await asyncio.gather(
        dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types()),
        _run_webhook_server(),
    )


if __name__ == "__main__":
    asyncio.run(main())

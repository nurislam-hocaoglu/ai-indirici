"""
aiogram v3 handlers module.
All bot command and callback handlers are registered here.
"""

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.filters import AllowedUserFilter
from bot.keyboards import (
    confirm_series_keyboard,
    monitor_mode_keyboard,
    series_selection_keyboard,
)
from bot.states import DownloadFlow
from config import settings
from services.jellyfin_api import JellyfinError, jellyfin
from services.sonarr_api import SonarrError, sonarr
from services.tmdb_api import TMDBError, tmdb
from services.webhook_listener import register_pending

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(AllowedUserFilter())


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

async def _safe_edit(callback: CallbackQuery, text: str, **kwargs) -> None:
    """Edit a callback message, suppressing 'message not modified' errors."""
    try:
        await callback.message.edit_text(text, **kwargs)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


async def _log_error(bot, text: str) -> None:
    """Send an error log to ADMIN_CHAT_ID."""
    try:
        await bot.send_message(settings.ADMIN_CHAT_ID, f"🔴 <b>HATA LOG</b>\n{text}", parse_mode="HTML")
    except Exception as exc:
        logger.error("Failed to send admin log: %s", exc)


# ---------------------------------------------------------------------------
# /start  /yardim
# ---------------------------------------------------------------------------

@router.message(Command("start", "yardim"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "🎬 <b>AI İndirici Bot</b>\n\n"
        "<b>Komutlar:</b>\n"
        "/indir &lt;dizi adı&gt; — Dizi indir\n"
        "/durum — Servis durumlarını kontrol et\n"
        "/iptal — Aktif işlemi iptal et\n"
        "/yardim — Bu mesajı göster",
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# /durum — ping all services
# ---------------------------------------------------------------------------

@router.message(Command("durum"))
async def cmd_status(message: Message) -> None:
    msg = await message.answer("⏳ Servisler kontrol ediliyor...")

    lines: list[str] = ["📡 <b>Servis Durumları</b>\n"]

    # Jellyfin
    try:
        await jellyfin.get_libraries()
        lines.append("✅ Jellyfin: çalışıyor")
    except JellyfinError as e:
        lines.append(f"❌ Jellyfin: HTTP {e.status_code}")
    except Exception as e:
        lines.append(f"❌ Jellyfin: {e}")

    # Sonarr
    try:
        await sonarr.get_root_folders()
        lines.append("✅ Sonarr: çalışıyor")
    except SonarrError as e:
        lines.append(f"❌ Sonarr: HTTP {e.status_code}")
    except Exception as e:
        lines.append(f"❌ Sonarr: {e}")

    await msg.edit_text("\n".join(lines), parse_mode="HTML")


# ---------------------------------------------------------------------------
# /iptal — clear FSM state
# ---------------------------------------------------------------------------

@router.message(Command("iptal"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    await state.clear()
    if current:
        await message.answer("🚫 İşlem iptal edildi.")
    else:
        await message.answer("ℹ️ Aktif işlem yok.")


# ---------------------------------------------------------------------------
# /indir <dizi adı>  — Step 1: TMDB search
# ---------------------------------------------------------------------------

@router.message(Command("indir"))
async def cmd_download(message: Message, state: FSMContext) -> None:
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip():
        await message.answer("❗ Kullanım: /indir <i>Dizi Adı</i>", parse_mode="HTML")
        return

    query = args[1].strip()
    await state.set_state(DownloadFlow.searching)
    msg = await message.answer(f"🔍 <b>{query}</b> aranıyor...", parse_mode="HTML")

    try:
        results = await tmdb.search_tv(query)
    except TMDBError as e:
        await msg.edit_text(
            f"❌ TMDB hatası: HTTP {e.status_code}\n<code>{e.detail[:200]}</code>",
            parse_mode="HTML",
        )
        await _log_error(
            message.bot,
            f"TMDB search failed for '{query}'\nHTTP {e.status_code}: {e.detail}",
        )
        await state.clear()
        return

    if not results:
        await msg.edit_text(f"🔎 '<b>{query}</b>' için sonuç bulunamadı.", parse_mode="HTML")
        await state.clear()
        return

    await state.update_data(tmdb_results=results)
    await state.set_state(DownloadFlow.selecting)

    keyboard = series_selection_keyboard(results)
    await msg.edit_text(
        f"🎬 <b>{len(results[:10])}</b> sonuç bulundu. Hangisini indirmek istiyorsunuz?",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


# ---------------------------------------------------------------------------
# Callback: series selection (sel:<tmdb_id>)  — Step 2: Show detail + confirm
# ---------------------------------------------------------------------------

@router.callback_query(DownloadFlow.selecting, F.data.startswith("sel:"))
async def cb_select_series(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    tmdb_id = int(callback.data.split(":")[1])

    await _safe_edit(callback, "⏳ Dizi bilgileri alınıyor...", parse_mode="HTML")

    try:
        details = await tmdb.get_tv_details(tmdb_id)
    except TMDBError as e:
        await _safe_edit(
            callback,
            f"❌ TMDB hatası: HTTP {e.status_code}\n<code>{e.detail[:200]}</code>",
            parse_mode="HTML",
        )
        await _log_error(
            callback.bot,
            f"TMDB detail fetch failed tmdb_id={tmdb_id}\nHTTP {e.status_code}: {e.detail}",
        )
        await state.clear()
        return

    await state.update_data(selected_tmdb_id=tmdb_id, tmdb_details=details)
    await state.set_state(DownloadFlow.confirming)

    name = details.get("name", "?")
    year = (details.get("first_air_date") or "")[:4] or "?"
    overview = (details.get("overview") or "Açıklama yok.")[:300]
    seasons = details.get("number_of_seasons", "?")
    episodes = details.get("number_of_episodes", "?")
    tvdb_id = details.get("external_ids", {}).get("tvdb_id", "Bilinmiyor")

    text = (
        f"📺 <b>{name}</b> ({year})\n"
        f"📅 Sezon: {seasons} | 🎞 Bölüm: {episodes}\n"
        f"🔑 TVDB ID: <code>{tvdb_id}</code>\n\n"
        f"📝 {overview}\n\n"
        f"İndir ve monitöre al?"
    )

    await _safe_edit(callback, text, parse_mode="HTML", reply_markup=confirm_series_keyboard(tmdb_id))


# ---------------------------------------------------------------------------
# Callback: confirm (confirm:<tmdb_id>)  — Step 3: Choose monitor mode
# ---------------------------------------------------------------------------

@router.callback_query(DownloadFlow.confirming, F.data.startswith("confirm:"))
async def cb_confirm_series(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    tmdb_id = int(callback.data.split(":")[1])

    await state.set_state(DownloadFlow.choosing_monitor)
    await _safe_edit(
        callback,
        "📂 Hangi bölümleri izlemek istiyorsunuz?",
        parse_mode="HTML",
        reply_markup=monitor_mode_keyboard(tmdb_id),
    )


# ---------------------------------------------------------------------------
# Callback: monitor mode (monitor:<tmdb_id>:<mode>)  — Step 4: Add to Sonarr
# ---------------------------------------------------------------------------

@router.callback_query(DownloadFlow.choosing_monitor, F.data.startswith("monitor:"))
async def cb_choose_monitor(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    parts = callback.data.split(":")
    tmdb_id = int(parts[1])
    monitor_mode = parts[2]

    data = await state.get_data()
    details: dict = data.get("tmdb_details", {})
    await state.clear()

    name = details.get("name", "?")
    year = int((details.get("first_air_date") or "0000")[:4] or 0)
    tvdb_id: int = details.get("external_ids", {}).get("tvdb_id")
    images = details.get("poster_path") and [
        {
            "coverType": "poster",
            "url": tmdb.poster_url(details.get("poster_path")),
        }
    ] or []
    # Build seasons list: all seasons monitored
    seasons = [
        {"seasonNumber": s.get("season_number", 0), "monitored": True}
        for s in details.get("seasons", [])
    ]

    if not tvdb_id:
        await _safe_edit(
            callback,
            "❌ Bu dizinin TVDB ID'si bulunamadı. Sonarr bu dizi için çalışamaz.",
            parse_mode="HTML",
        )
        return

    await _safe_edit(callback, f"⏳ <b>{name}</b> Sonarr'a ekleniyor...", parse_mode="HTML")

    try:
        series_obj = await sonarr.add_series(
            tvdb_id=tvdb_id,
            title=name,
            year=year,
            images=images,
            seasons=seasons,
            root_folder_path=settings.SONARR_ROOT_FOLDER,
            quality_profile_id=settings.SONARR_QUALITY_PROFILE_ID,
            language_profile_id=settings.SONARR_LANGUAGE_PROFILE_ID,
            monitor_type=monitor_mode,
            search_for_missing=True,
        )
    except SonarrError as e:
        # 400 can mean the series already exists — handle gracefully
        if e.status_code == 400 and "already been added" in e.detail.lower():
            await _safe_edit(
                callback,
                f"ℹ️ <b>{name}</b> zaten Sonarr'da mevcut. Arama başlatılıyor...",
                parse_mode="HTML",
            )
            # Lookup existing series in Sonarr
            try:
                lookup = await sonarr.lookup_series(name)
                existing = next(
                    (s for s in lookup if s.get("tvdbId") == tvdb_id and s.get("id")), None
                )
                if existing:
                    sonarr_series_id = existing["id"]
                    await sonarr.command_search_series(sonarr_series_id)
                    register_pending(sonarr_series_id, callback.from_user.id)
            except SonarrError as inner_e:
                await _log_error(
                    callback.bot,
                    f"Sonarr existing series search failed: {inner_e}",
                )
            return
        else:
            error_text = (
                f"❌ <b>Sonarr Hatası</b>\n"
                f"Dizi: {name}\n"
                f"HTTP {e.status_code}: <code>{e.detail[:300]}</code>"
            )
            await _safe_edit(callback, error_text, parse_mode="HTML")
            await _log_error(callback.bot, f"Sonarr add_series failed for {name}:\n{e}")
            return

    sonarr_series_id: int = series_obj.get("id")
    register_pending(sonarr_series_id, callback.from_user.id)

    await _safe_edit(
        callback,
        f"🚀 <b>{name}</b> Sonarr'a eklendi!\n"
        f"📡 Sonarr arka planda torrent arıyor...\n"
        f"📲 İndirme tamamlandığında buradan bildirim alacaksınız.",
        parse_mode="HTML",
    )

    logger.info(
        "Series added: %s (tvdbId=%s, sonarrId=%s, monitor=%s) for user=%s",
        name, tvdb_id, sonarr_series_id, monitor_mode, callback.from_user.id,
    )


# ---------------------------------------------------------------------------
# Callback: cancel
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await _safe_edit(callback, "🚫 İşlem iptal edildi.")


# ---------------------------------------------------------------------------
# Catch-all: unauthorized user
# ---------------------------------------------------------------------------

@router.message()
async def msg_unauthorized(message: Message) -> None:
    if settings.ALLOWED_USER_IDS and (
        message.from_user is None
        or message.from_user.id not in settings.ALLOWED_USER_IDS
    ):
        logger.warning(
            "Unauthorized access attempt from user_id=%s username=%s",
            message.from_user.id if message.from_user else "?",
            message.from_user.username if message.from_user else "?",
        )
        await message.answer("⛔ Bu botu kullanma yetkiniz yok.")

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
    confirm_movie_keyboard,
    movie_selection_keyboard,
)
from bot.states import DownloadFlow
from config import settings
from services.jellyfin_api import JellyfinError, jellyfin
from services.radarr_api import RadarrError, radarr
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
        "🎬 <b>AI Film İndirici Bot</b>\n\n"
        "<b>Komutlar:</b>\n"
        "/indir &lt;film adı&gt; — Film ara ve indir\n"
        "/durum — Servis durumlarını kontrol et (Radarr & Jellyfin)\n"
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

    # Radarr
    try:
        await radarr.get_root_folders()
        lines.append("✅ Radarr: çalışıyor")
    except RadarrError as e:
        lines.append(f"❌ Radarr: HTTP {e.status_code}")
    except Exception as e:
        lines.append(f"❌ Radarr: {e}")

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
# /indir <film adı>  — Step 1: TMDB movie search
# ---------------------------------------------------------------------------

@router.message(Command("indir"))
async def cmd_download(message: Message, state: FSMContext) -> None:
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip():
        await message.answer("❗ Kullanım: /indir <i>Film Adı</i>", parse_mode="HTML")
        return

    query = args[1].strip()
    await state.set_state(DownloadFlow.searching)
    msg = await message.answer(f"🔍 <b>{query}</b> aranıyor...", parse_mode="HTML")

    try:
        results = await tmdb.search_movie(query)
    except TMDBError as e:
        await msg.edit_text(
            f"❌ TMDB hatası: HTTP {e.status_code}\n<code>{e.detail[:200]}</code>",
            parse_mode="HTML",
        )
        await _log_error(
            message.bot,
            f"TMDB movie search failed for '{query}'\nHTTP {e.status_code}: {e.detail}",
        )
        await state.clear()
        return

    if not results:
        await msg.edit_text(f"🔎 '<b>{query}</b>' için sonuç bulunamadı.", parse_mode="HTML")
        await state.clear()
        return

    await state.update_data(tmdb_results=results)
    await state.set_state(DownloadFlow.selecting)

    keyboard = movie_selection_keyboard(results)
    await msg.edit_text(
        f"🎬 <b>{len(results[:10])}</b> sonuç bulundu. Hangisini indirmek istiyorsunuz?",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


# ---------------------------------------------------------------------------
# Callback: movie selection (sel:<tmdb_id>)  — Step 2: Show detail + confirm
# ---------------------------------------------------------------------------

@router.callback_query(DownloadFlow.selecting, F.data.startswith("sel:"))
async def cb_select_movie(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    tmdb_id = int(callback.data.split(":")[1])

    await _safe_edit(callback, "⏳ Film bilgileri alınıyor...", parse_mode="HTML")

    try:
        details = await tmdb.get_movie_details(tmdb_id)
    except TMDBError as e:
        await _safe_edit(
            callback,
            f"❌ TMDB hatası: HTTP {e.status_code}\n<code>{e.detail[:200]}</code>",
            parse_mode="HTML",
        )
        await _log_error(
            callback.bot,
            f"TMDB movie detail fetch failed tmdb_id={tmdb_id}\nHTTP {e.status_code}: {e.detail}",
        )
        await state.clear()
        return

    await state.update_data(selected_tmdb_id=tmdb_id, tmdb_details=details)
    await state.set_state(DownloadFlow.confirming)

    title = details.get("title") or details.get("name", "?")
    orig_title = details.get("original_title", "")
    year = (details.get("release_date") or "")[:4] or "?"
    overview = (details.get("overview") or "Açıklama bulunmuyor.")[:350]
    vote = details.get("vote_average", 0)
    runtime = details.get("runtime")
    genres = ", ".join(g.get("name", "") for g in details.get("genres", []))

    info_lines = [f"🎬 <b>{title}</b> ({year})"]
    if orig_title and orig_title.lower() != title.lower():
        info_lines.append(f"<i>Orijinal Adı: {orig_title}</i>")
    if vote:
        info_lines.append(f"⭐ Puan: {vote:.1f}/10")
    if runtime:
        info_lines.append(f"⏱️ Süre: {runtime} dakika")
    if genres:
        info_lines.append(f"🎭 Tür: {genres}")
    info_lines.append(f"🔑 TMDB ID: <code>{tmdb_id}</code>")
    info_lines.append(f"\n📝 {overview}")
    info_lines.append("\nFilmi Radarr ile indirip Jellyfin'e eklemek istiyor musunuz?")

    text = "\n".join(info_lines)
    await _safe_edit(callback, text, parse_mode="HTML", reply_markup=confirm_movie_keyboard(tmdb_id))


# ---------------------------------------------------------------------------
# Callback: confirm (confirm:<tmdb_id>)  — Step 3: Add to Radarr & start search
# ---------------------------------------------------------------------------

@router.callback_query(DownloadFlow.confirming, F.data.startswith("confirm:"))
async def cb_confirm_movie(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    parts = callback.data.split(":")
    tmdb_id = int(parts[1])

    data = await state.get_data()
    details: dict = data.get("tmdb_details", {})
    await state.clear()

    title = details.get("title") or details.get("name", "?")
    year_str = (details.get("release_date") or "0000")[:4]
    year = int(year_str) if year_str.isdigit() else 0

    images = []
    if details.get("poster_path"):
        images.append({
            "coverType": "poster",
            "url": tmdb.poster_url(details.get("poster_path")),
        })

    await _safe_edit(callback, f"⏳ <b>{title}</b> Radarr'a ekleniyor...", parse_mode="HTML")

    # Determine root folder (fall back to Radarr's configured folders if needed)
    root_folder = settings.RADARR_ROOT_FOLDER
    try:
        radarr_folders = await radarr.get_root_folders()
        folder_paths = [f.get("path") for f in radarr_folders if f.get("path")]
        if folder_paths and root_folder not in folder_paths:
            # Prefer folder containing jellyfin if available
            root_folder = next((p for p in folder_paths if "jellyfin" in p.lower()), folder_paths[0])
    except Exception as exc:
        logger.warning("Could not check Radarr root folders dynamically: %s", exc)

    try:
        movie_obj = await radarr.add_movie(
            tmdb_id=tmdb_id,
            title=title,
            year=year,
            images=images,
            root_folder_path=root_folder,
            quality_profile_id=settings.RADARR_QUALITY_PROFILE_ID,
            monitored=True,
            search_for_movie=True,
        )
    except RadarrError as e:
        # Check if movie is already added in Radarr
        if e.status_code == 400 and ("already been added" in e.detail.lower() or "exists" in e.detail.lower()):
            await _safe_edit(
                callback,
                f"ℹ️ <b>{title}</b> zaten Radarr'da mevcut. Torrent araması tetikleniyor...",
                parse_mode="HTML",
            )
            try:
                all_movies = await radarr.get_all_movies()
                existing = next(
                    (m for m in all_movies if m.get("tmdbId") == tmdb_id and m.get("id")), None
                )
                if existing:
                    radarr_movie_id = existing["id"]
                    await radarr.command_search_movie(radarr_movie_id)
                    register_pending(radarr_movie_id, callback.from_user.id)
            except Exception as inner_e:
                await _log_error(
                    callback.bot,
                    f"Radarr existing movie search failed: {inner_e}",
                )
            return
        else:
            error_text = (
                f"❌ <b>Radarr Hatası</b>\n"
                f"Film: {title}\n"
                f"HTTP {e.status_code}: <code>{e.detail[:300]}</code>"
            )
            await _safe_edit(callback, error_text, parse_mode="HTML")
            await _log_error(callback.bot, f"Radarr add_movie failed for {title}:\n{e}")
            return

    radarr_movie_id: int = movie_obj.get("id")
    if radarr_movie_id:
        register_pending(radarr_movie_id, callback.from_user.id)

    await _safe_edit(
        callback,
        f"🚀 <b>{title}</b> Radarr'a eklendi!\n"
        f"📡 Radarr torrent aramaya başladı...\n"
        f"📥 Film indiğinde Jellyfin kütüphanesine aktarılacak ve size bildirim gönderilecek.",
        parse_mode="HTML",
    )

    logger.info(
        "Movie added: %s (tmdbId=%s, radarrId=%s) for user=%s",
        title, tmdb_id, radarr_movie_id, callback.from_user.id,
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

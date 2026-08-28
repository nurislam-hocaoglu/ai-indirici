"""
Reusable inline keyboard builders.
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def series_selection_keyboard(results: list[dict], page_prefix: str = "sel") -> InlineKeyboardMarkup:
    """
    Build a keyboard from a list of TMDB search results.
    Each button's callback_data encodes: {page_prefix}:{tmdb_id}
    Max 10 results displayed.
    """
    builder = InlineKeyboardBuilder()
    for item in results[:10]:
        tmdb_id = item.get("id")
        name = item.get("name", "?")
        year = (item.get("first_air_date") or "")[:4] or "?"
        builder.button(
            text=f"{name} ({year})",
            callback_data=f"{page_prefix}:{tmdb_id}",
        )
    builder.button(text="❌ İptal", callback_data="cancel")
    builder.adjust(1)
    return builder.as_markup()


def confirm_series_keyboard(tmdb_id: int) -> InlineKeyboardMarkup:
    """Confirm / reject keyboard shown before adding to Sonarr."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Onayla & İndir", callback_data=f"confirm:{tmdb_id}")
    builder.button(text="❌ İptal", callback_data="cancel")
    builder.adjust(2)
    return builder.as_markup()


def monitor_mode_keyboard(tmdb_id: int) -> InlineKeyboardMarkup:
    """Let user choose which seasons/episodes to monitor."""
    builder = InlineKeyboardBuilder()
    options = [
        ("📺 Tüm Sezonlar", "all"),
        ("🆕 Sadece Gelecek Bölümler", "future"),
        ("1️⃣ Sadece 1. Sezon", "firstSeason"),
        ("🔝 Son Sezon", "latestSeason"),
    ]
    for label, mode in options:
        builder.button(text=label, callback_data=f"monitor:{tmdb_id}:{mode}")
    builder.button(text="❌ İptal", callback_data="cancel")
    builder.adjust(1)
    return builder.as_markup()

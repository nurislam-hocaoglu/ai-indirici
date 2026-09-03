"""
Reusable inline keyboard builders.
"""

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def movie_selection_keyboard(results: list[dict], page_prefix: str = "sel") -> InlineKeyboardMarkup:
    """
    Build a keyboard from a list of TMDB movie search results.
    Each button's callback_data encodes: {page_prefix}:{tmdb_id}
    Max 10 results displayed.
    """
    builder = InlineKeyboardBuilder()
    for item in results[:10]:
        tmdb_id = item.get("id")
        title = item.get("title") or item.get("name", "?")
        year = (item.get("release_date") or item.get("first_air_date") or "")[:4] or "?"
        vote = item.get("vote_average", 0)
        vote_str = f" ⭐ {vote:.1f}" if vote else ""
        builder.button(
            text=f"🎬 {title} ({year}){vote_str}",
            callback_data=f"{page_prefix}:{tmdb_id}",
        )
    builder.button(text="❌ İptal", callback_data="cancel")
    builder.adjust(1)
    return builder.as_markup()


def confirm_movie_keyboard(tmdb_id: int) -> InlineKeyboardMarkup:
    """Confirm / reject keyboard shown before adding to Radarr."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Onayla & İndir", callback_data=f"confirm:{tmdb_id}")
    builder.button(text="❌ İptal", callback_data="cancel")
    builder.adjust(2)
    return builder.as_markup()


# Aliases for backward compatibility
series_selection_keyboard = movie_selection_keyboard
confirm_series_keyboard = confirm_movie_keyboard

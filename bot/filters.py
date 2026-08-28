"""
Custom aiogram filters.
"""

from aiogram.filters import BaseFilter
from aiogram.types import Message

from config import settings


class AllowedUserFilter(BaseFilter):
    """
    Passes only if ALLOWED_USER_IDS is empty (allow all)
    or the user's ID is in the list.
    """

    async def __call__(self, message: Message) -> bool:
        if not settings.ALLOWED_USER_IDS:
            return True
        return message.from_user is not None and message.from_user.id in settings.ALLOWED_USER_IDS

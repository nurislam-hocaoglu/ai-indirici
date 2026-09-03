"""
Jellyfin API service module.
Handles library refresh commands via Jellyfin REST API.
"""

import logging
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)


class JellyfinError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Jellyfin {status_code}: {detail}")


class JellyfinAPI:
    def __init__(self):
        self.base_url = settings.JELLYFIN_URL.rstrip("/")
        self.api_key = settings.JELLYFIN_API_KEY
        self.headers = {
            "Authorization": f'MediaBrowser Token="{self.api_key}"',
            "Content-Type": "application/json",
        }

    async def _post(self, endpoint: str, payload: Optional[dict] = None) -> None:
        url = f"{self.base_url}/{endpoint}"
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, headers=self.headers, json=payload or {})
            if resp.status_code >= 400:
                raise JellyfinError(resp.status_code, resp.text)

    async def _get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        url = f"{self.base_url}/{endpoint}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=self.headers, params=params)
            if resp.status_code >= 400:
                raise JellyfinError(resp.status_code, resp.text)
            return resp.json()

    async def refresh_library(self) -> None:
        """Trigger a full library scan on Jellyfin."""
        logger.info("Triggering Jellyfin full library refresh")
        await self._post("Library/Refresh")

    async def get_libraries(self) -> list[dict]:
        """Return all configured media libraries."""
        result = await self._get("Library/VirtualFolders")
        return result  # type: ignore[return-value]

    async def configure_auto_subtitles(
        self, preferred_language: str = "tur", subtitle_mode: str = "Always"
    ) -> None:
        """
        Configure all Jellyfin users to automatically display subtitles when a video starts.
        Sets SubtitleMode='Always' and SubtitleLanguagePreference='tur'.
        """
        try:
            users = await self._get("Users")
            if isinstance(users, list):
                for u in users:
                    uid = u.get("Id")
                    conf = u.get("Configuration", {})
                    conf["SubtitleMode"] = subtitle_mode
                    conf["SubtitleLanguagePreference"] = preferred_language
                    conf["RememberSubtitleSelections"] = True
                    await self._post(f"Users/{uid}/Configuration", payload=conf)
                    logger.info("Configured automatic subtitles for Jellyfin user: %s", u.get("Name"))
        except Exception as exc:
            logger.warning("Could not auto-configure Jellyfin subtitle preferences: %s", exc)


jellyfin = JellyfinAPI()

"""
Bazarr API service module.
Handles subtitle search and status queries via Bazarr REST API.
"""

import logging
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)


class BazarrError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Bazarr {status_code}: {detail}")


class BazarrAPI:
    def __init__(self):
        self.base_url = settings.BAZARR_URL.rstrip("/")
        self.api_key = settings.BAZARR_API_KEY
        self.headers = {"X-Api-Key": self.api_key}

    async def _get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        url = f"{self.base_url}/api/{endpoint}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=self.headers, params=params)
            if resp.status_code >= 400:
                raise BazarrError(resp.status_code, resp.text)
            return resp.json()

    async def _post(self, endpoint: str, params: Optional[dict] = None) -> dict:
        url = f"{self.base_url}/api/{endpoint}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=self.headers, params=params or {})
            if resp.status_code >= 400:
                raise BazarrError(resp.status_code, resp.text)
            # Bazarr returns 204 No Content on some endpoints
            if resp.status_code == 204 or not resp.content:
                return {"status": "ok"}
            return resp.json()

    async def search_series_subtitles(
        self, sonarr_series_id: int, language: str = "tr"
    ) -> dict:
        """
        Trigger a manual subtitle search for all episodes of a series.
        Bazarr maps series by sonarrSeriesId.
        """
        logger.info(
            "Triggering Bazarr subtitle search: series=%s lang=%s",
            sonarr_series_id,
            language,
        )
        return await self._post(
            "episodes/subtitles",
            params={
                "seriesid": sonarr_series_id,
                "language": language,
                "action": "search",
            },
        )

    async def search_episode_subtitles(
        self,
        sonarr_series_id: int,
        sonarr_episode_id: int,
        language: str = "tr",
    ) -> dict:
        """Trigger subtitle search for a single episode."""
        logger.info(
            "Triggering Bazarr subtitle search: episode=%s lang=%s",
            sonarr_episode_id,
            language,
        )
        return await self._post(
            "episodes/subtitles",
            params={
                "seriesid": sonarr_series_id,
                "episodeid": sonarr_episode_id,
                "language": language,
                "action": "search",
            },
        )

    async def get_wanted_episodes(
        self, sonarr_series_id: Optional[int] = None
    ) -> dict:
        """Return episodes missing subtitles, optionally filtered by series."""
        params: dict = {"start": 0, "length": 100}
        if sonarr_series_id:
            params["seriesid"] = sonarr_series_id
        return await self._get("episodes/wanted", params=params)

    async def get_series(self, sonarr_series_id: int) -> dict:
        """Fetch Bazarr's record for a series."""
        return await self._get("series", params={"seriesid": sonarr_series_id})


bazarr = BazarrAPI()

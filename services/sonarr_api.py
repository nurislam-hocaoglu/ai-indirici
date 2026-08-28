"""
Sonarr API service module.
Handles all communication with the Sonarr v3 REST API.
"""

import logging
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)


class SonarrError(Exception):
    """Raised when Sonarr API returns an error response."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Sonarr {status_code}: {detail}")


class SonarrAPI:
    def __init__(self):
        self.base_url = settings.SONARR_URL.rstrip("/")
        self.api_key = settings.SONARR_API_KEY
        self.headers = {"X-Api-Key": self.api_key}

    async def _get(self, endpoint: str, params: Optional[dict] = None) -> dict | list:
        url = f"{self.base_url}/api/v3/{endpoint}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=self.headers, params=params)
            if resp.status_code >= 400:
                raise SonarrError(resp.status_code, resp.text)
            return resp.json()

    async def _post(self, endpoint: str, payload: dict) -> dict:
        url = f"{self.base_url}/api/v3/{endpoint}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=self.headers, json=payload)
            if resp.status_code >= 400:
                raise SonarrError(resp.status_code, resp.text)
            return resp.json()

    async def lookup_series(self, term: str) -> list[dict]:
        """Search Sonarr's metadata provider for a TV series by name."""
        results = await self._get("series/lookup", params={"term": term})
        return results  # type: ignore[return-value]

    async def get_root_folders(self) -> list[dict]:
        """Return configured root folders in Sonarr."""
        return await self._get("rootfolder")  # type: ignore[return-value]

    async def get_quality_profiles(self) -> list[dict]:
        """Return available quality profiles."""
        return await self._get("qualityprofile")  # type: ignore[return-value]

    async def get_language_profiles(self) -> list[dict]:
        """Return available language profiles (Sonarr v3)."""
        return await self._get("languageprofile")  # type: ignore[return-value]

    async def add_series(
        self,
        tvdb_id: int,
        title: str,
        year: int,
        images: list,
        seasons: list,
        root_folder_path: str,
        quality_profile_id: int,
        language_profile_id: int,
        monitor_type: str = "all",
        search_for_missing: bool = True,
    ) -> dict:
        """
        Add a series to Sonarr and trigger an automatic search.
        Returns the created series object.
        """
        payload = {
            "tvdbId": tvdb_id,
            "title": title,
            "year": year,
            "images": images,
            "seasons": seasons,
            "rootFolderPath": root_folder_path,
            "qualityProfileId": quality_profile_id,
            "languageProfileId": language_profile_id,
            "monitored": True,
            "addOptions": {
                "monitor": monitor_type,
                "searchForMissingEpisodes": search_for_missing,
                "searchForCutoffUnmetEpisodes": False,
            },
        }
        logger.info("Adding series to Sonarr: %s (tvdbId=%s)", title, tvdb_id)
        return await self._post("series", payload)

    async def get_series(self, series_id: int) -> dict:
        """Fetch a single series by its Sonarr internal ID."""
        return await self._get(f"series/{series_id}")  # type: ignore[return-value]

    async def get_episodes(self, series_id: int) -> list[dict]:
        """Return all episodes for a series."""
        return await self._get("episode", params={"seriesId": series_id})  # type: ignore[return-value]

    async def command_search_series(self, series_id: int) -> dict:
        """Trigger a series-wide search command in Sonarr."""
        payload = {"name": "SeriesSearch", "seriesId": series_id}
        return await self._post("command", payload)


sonarr = SonarrAPI()

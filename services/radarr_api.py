"""
Radarr API service module.
Handles all communication with the Radarr v3 REST API.
"""

import logging
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)


class RadarrError(Exception):
    """Raised when Radarr API returns an error response."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Radarr {status_code}: {detail}")


class RadarrAPI:
    def __init__(self):
        self.base_url = settings.RADARR_URL.rstrip("/")
        self.api_key = settings.RADARR_API_KEY
        self.headers = {"X-Api-Key": self.api_key}

    async def _get(self, endpoint: str, params: Optional[dict] = None) -> dict | list:
        url = f"{self.base_url}/api/v3/{endpoint}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=self.headers, params=params)
            if resp.status_code >= 400:
                raise RadarrError(resp.status_code, resp.text)
            return resp.json()

    async def _post(self, endpoint: str, payload: dict) -> dict:
        url = f"{self.base_url}/api/v3/{endpoint}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=self.headers, json=payload)
            if resp.status_code >= 400:
                raise RadarrError(resp.status_code, resp.text)
            return resp.json()

    async def lookup_movie(self, term: str) -> list[dict]:
        """Search Radarr's metadata provider for a movie by name."""
        results = await self._get("movie/lookup", params={"term": term})
        return results  # type: ignore[return-value]

    async def lookup_movie_by_tmdb(self, tmdb_id: int) -> dict:
        """Lookup movie in Radarr by TMDB ID."""
        results = await self._get("movie/lookup/tmdb", params={"tmdbId": tmdb_id})
        return results  # type: ignore[return-value]

    async def get_root_folders(self) -> list[dict]:
        """Return configured root folders in Radarr."""
        return await self._get("rootfolder")  # type: ignore[return-value]

    async def get_quality_profiles(self) -> list[dict]:
        """Return available quality profiles."""
        return await self._get("qualityprofile")  # type: ignore[return-value]

    async def add_movie(
        self,
        tmdb_id: int,
        title: str,
        year: int,
        root_folder_path: str,
        quality_profile_id: int,
        images: Optional[list] = None,
        monitored: bool = True,
        search_for_movie: bool = True,
        title_slug: Optional[str] = None,
    ) -> dict:
        """
        Add a movie to Radarr and trigger an automatic search.
        Returns the created movie object.
        """
        payload: dict = {
            "title": title,
            "tmdbId": tmdb_id,
            "year": year,
            "qualityProfileId": quality_profile_id,
            "rootFolderPath": root_folder_path,
            "monitored": monitored,
            "addOptions": {
                "searchForMovie": search_for_movie,
            },
        }
        if images:
            payload["images"] = images
        if title_slug:
            payload["titleSlug"] = title_slug

        logger.info("Adding movie to Radarr: %s (tmdbId=%s)", title, tmdb_id)
        return await self._post("movie", payload)

    async def get_movie(self, movie_id: int) -> dict:
        """Fetch a single movie by its Radarr internal ID."""
        return await self._get(f"movie/{movie_id}")  # type: ignore[return-value]

    async def get_all_movies(self) -> list[dict]:
        """Fetch all movies managed by Radarr."""
        return await self._get("movie")  # type: ignore[return-value]

    async def command_search_movie(self, movie_id: int) -> dict:
        """Trigger an automatic search for a movie in Radarr."""
        payload = {"name": "MoviesSearch", "movieIds": [movie_id]}
        return await self._post("command", payload)


radarr = RadarrAPI()


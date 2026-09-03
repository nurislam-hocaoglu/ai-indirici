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
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=self.headers, params=params)
            if resp.status_code >= 400:
                raise BazarrError(resp.status_code, resp.text)
            return resp.json()

    async def _post(self, endpoint: str, params: Optional[dict] = None) -> dict:
        url = f"{self.base_url}/api/{endpoint}"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, headers=self.headers, params=params or {})
            if resp.status_code >= 400:
                raise BazarrError(resp.status_code, resp.text)
            # Bazarr returns 204 No Content on some endpoints
            if resp.status_code == 204 or not resp.content:
                return {"status": "ok"}
            return resp.json()

    async def _patch(self, endpoint: str, params: Optional[dict] = None) -> dict:
        url = f"{self.base_url}/api/{endpoint}"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.patch(url, headers=self.headers, params=params or {})
            if resp.status_code >= 400:
                raise BazarrError(resp.status_code, resp.text)
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

    async def get_language_profiles(self) -> list[dict]:
        """Fetch all configured language profiles in Bazarr."""
        return await self._get("system/languages/profiles")  # type: ignore[return-value]

    async def get_profile_id_by_name(self, name: str = "stand") -> int:
        """Find a language profile ID by name (case-insensitive). Defaults to 1."""
        try:
            profiles = await self.get_language_profiles()
            for p in profiles:
                if p.get("name", "").strip().lower() == name.strip().lower():
                    return int(p.get("profileId", 1))
        except Exception as exc:
            logger.warning("Could not fetch Bazarr language profiles: %s", exc)
        return 1

    async def sync_movies(self) -> dict:
        """Trigger Bazarr to sync movies with Radarr."""
        logger.info("Triggering Bazarr movies sync with Radarr")
        return await self._patch("movies", params={"action": "sync"})

    async def assign_movie_profile(self, radarr_movie_id: int, profile_id: int) -> dict:
        """Assign a language profile to a movie in Bazarr."""
        logger.info(
            "Assigning language profile %s to movie %s in Bazarr",
            profile_id,
            radarr_movie_id,
        )
        return await self._post(
            "movies",
            params={"radarrid": radarr_movie_id, "profileid": profile_id},
        )

    async def scan_movie_disk(self, radarr_movie_id: int) -> dict:
        """Trigger Bazarr to scan disk for a movie."""
        return await self._patch(
            "movies",
            params={"radarrid": radarr_movie_id, "action": "scan-disk"},
        )

    async def search_movie_subtitles(
        self, radarr_movie_id: int, profile_name: str = "stand"
    ) -> dict:
        """
        Assign language profile ('stand') to the movie and trigger
        missing subtitles search (Turkish & English).
        """
        # 1. Sync movies so Bazarr has the newest movie entry from Radarr
        try:
            await self.sync_movies()
        except Exception as exc:
            logger.warning("Bazarr sync failed (ignoring): %s", exc)

        # 2. Find profile ID for profile_name (e.g. 'stand')
        profile_id = await self.get_profile_id_by_name(profile_name)

        # 3. Assign the profile to the movie
        try:
            await self.assign_movie_profile(radarr_movie_id, profile_id)
        except Exception as exc:
            logger.warning("Could not assign profile %s to movie %s: %s", profile_id, radarr_movie_id, exc)

        # 4. Scan disk so Bazarr detects the downloaded movie file
        try:
            await self.scan_movie_disk(radarr_movie_id)
        except Exception as exc:
            logger.warning("Bazarr scan-disk failed (ignoring): %s", exc)

        # 5. Trigger search for missing subtitles (stand profile covers tr and en)
        logger.info(
            "Triggering Bazarr search-missing subtitles: movie=%s profile=%s(id=%s)",
            radarr_movie_id,
            profile_name,
            profile_id,
        )
        return await self._patch(
            "movies",
            params={"radarrid": radarr_movie_id, "action": "search-missing"},
        )

    async def get_movie(self, radarr_movie_id: int) -> dict:
        """Fetch Bazarr's record for a movie."""
        return await self._get("movies", params={"radarrid[]": [radarr_movie_id]})

    async def get_wanted_movies(self) -> dict:
        """Return movies missing subtitles."""
        return await self._get("movies/wanted", params={"start": 0, "length": 100})

    async def get_series(self, sonarr_series_id: int) -> dict:
        """Fetch Bazarr's record for a series."""
        return await self._get("series", params={"seriesid": sonarr_series_id})


bazarr = BazarrAPI()

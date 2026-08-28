"""
TMDB API service module.
Used for series validation and poster fetching before adding to Sonarr.
"""

import logging
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG_BASE = "https://image.tmdb.org/t/p/w500"


class TMDBError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"TMDB {status_code}: {detail}")


class TMDBAPI:
    def __init__(self):
        self.api_key = settings.TMDB_API_KEY

    async def search_tv(self, query: str, language: str = "tr-TR") -> list[dict]:
        """Search TMDB for TV shows by name."""
        params = {
            "api_key": self.api_key,
            "query": query,
            "language": language,
            "include_adult": False,
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{TMDB_BASE}/search/tv", params=params)
            if resp.status_code >= 400:
                raise TMDBError(resp.status_code, resp.text)
            data = resp.json()
            return data.get("results", [])

    async def get_tv_details(self, tmdb_id: int, language: str = "tr-TR") -> dict:
        """Get full details + external IDs (tvdb_id) for a TV show."""
        params = {
            "api_key": self.api_key,
            "language": language,
            "append_to_response": "external_ids",
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{TMDB_BASE}/tv/{tmdb_id}", params=params)
            if resp.status_code >= 400:
                raise TMDBError(resp.status_code, resp.text)
            return resp.json()

    def poster_url(self, poster_path: Optional[str]) -> Optional[str]:
        if not poster_path:
            return None
        return f"{TMDB_IMG_BASE}{poster_path}"


tmdb = TMDBAPI()

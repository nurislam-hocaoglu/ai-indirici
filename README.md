# AI Indirici

Telegram-based movie automation bot for managing Radarr, Bazarr, Jellyfin, and TMDB workflows from a single chat interface.

This project listens for Radarr webhook events, queries metadata from TMDB, and lets an admin trigger media operations from Telegram using a lightweight Python bot.

## Features

- Telegram bot interface for media management
- Radarr integration for movie search and automation
- Bazarr integration for subtitle management
- Jellyfin integration for media library queries
- TMDB metadata lookup
- Webhook listener for automated updates
- Dockerized deployment with Compose
- Centralized environment-based configuration

## Architecture

- `bot/` — Telegram bot logic, handlers, filters, keyboards, and state flow
- `services/` — API adapters for TMDB, Radarr, Bazarr, Jellyfin, and webhook processing
- `config.py` — Pydantic settings for environment configuration
- `docker-compose.yml` — full stack orchestration for media services
- `Dockerfile` — bot container build definition
- `.env.example` — sample environment variables

## Tech Stack

- Python 3
- python-telegram-bot
- Pydantic + pydantic-settings
- aiohttp
- Docker / Docker Compose
- Radarr
- Bazarr
- Jellyfin
- qBittorrent
- TMDB API

## Required Services

The bot is designed to work together with:

- qBittorrent
- Radarr
- Bazarr
- Jellyfin
- Telegram Bot API
- TMDB API key

## Configuration

Copy the example environment file and update the values:

```bash
cp .env.example .env
```

Then fill in your Telegram token, admin chat ID, API credentials, and service URLs in `.env`.

## Run with Docker Compose

```bash
docker compose up --build -d
```

## Project Layout

```text
ai-indirici/
├── .env.example
├── .gitignore
├── Dockerfile
├── config.py
├── docker-compose.yml
├── requirements.txt
├── bot/
│   ├── __init__.py
│   ├── filters.py
│   ├── handlers.py
│   ├── keyboards.py
│   ├── main.py
│   └── states.py
├── services/
│   ├── __init__.py
│   ├── bazarr_api.py
│   ├── jellyfin_api.py
│   ├── radarr_api.py
│   ├── tmdb_api.py
│   └── webhook_listener.py
└── README.md
```

## Notes

This repository is intended for local or self-hosted media automation and relies on services running in the same Docker network or accessible over the configured hostnames.

## License

This project does not currently declare a license in the repository. If you plan to redistribute or publish this project, add a license file explicitly.

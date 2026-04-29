"""
Configuration module for Discord Music Bot
Loads settings from environment variables with fallbacks
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

class Config:
    """Central configuration class"""
    
    # Discord
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
    # Validate only when actually running the bot, not during imports
    if not DISCORD_TOKEN and not os.getenv("PYTEST_CURRENT_TEST"):
        # Token is optional during testing, but raise if running the actual bot
        pass
    
    # YouTube
    YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

    # Spotify
    SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
    SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
    
    # Genius (Lyrics)
    GENIUS_ACCESS_TOKEN = os.getenv("GENIUS_ACCESS_TOKEN")
    
    # LRCLIB (Lyrics fallback)
    LRCLIB_BASE_URL = os.getenv("LRCLIB_BASE_URL", "https://lrclib.net")
    
    # Bot Settings
    DEFAULT_VOLUME = int(os.getenv("DEFAULT_VOLUME", "50"))
    DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "en")
    
    PRIMARY_SOURCE = os.getenv("PRIMARY_SOURCE", "youtube").lower()
    SUPPORTED_SOURCES = [
        source.strip().lower()
        for source in os.getenv("SUPPORTED_SOURCES", "youtube,spotify").split(",")
        if source.strip()
    ]
    # Cache
    CACHE_DIR = Path(os.getenv("CACHE_DIR", "./cache"))
    CACHE_DIR.mkdir(exist_ok=True)

    # Logs
    LOG_DIR = Path(os.getenv("LOG_DIR", "./logs"))
    LOG_DIR.mkdir(exist_ok=True)
    LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", "7"))
    
    # Voice Configuration
    VOICE_TIMEOUT = int(os.getenv("VOICE_TIMEOUT", "300"))
    IDLE_DISCONNECT_TIME = int(os.getenv("IDLE_DISCONNECT_TIME", "600"))
    
    # Debug
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"


# Localization strings
LOCALIZATION = {
    "en": {
        "now_playing": "Now Playing",
        "queue": "Queue",
        "no_queue": "Queue is empty",
        "skip": "Skipped",
        "paused": "Paused",
        "resumed": "Resumed",
        "stopped": "Stopped",
        "volume_set": "Volume set to",
        "error": "An error occurred",
        "bot_joined": "Bot joined voice channel",
        "bot_left": "Bot left voice channel",
        "not_connected": "Bot is not connected to a voice channel",
        "no_track_playing": "No track is currently playing",
    },
    "es": {
        "now_playing": "Reproduciendo ahora",
        "queue": "Cola",
        "no_queue": "La cola está vacía",
        "skip": "Omitido",
        "paused": "En pausa",
        "resumed": "Reanudado",
        "stopped": "Detenido",
        "volume_set": "Volumen establecido en",
        "error": "Ocurrió un error",
        "bot_joined": "Bot se unió al canal de voz",
        "bot_left": "Bot salió del canal de voz",
        "not_connected": "El bot no está conectado a un canal de voz",
        "no_track_playing": "No hay pista reproduciéndose",
    },
    "fr": {
        "now_playing": "Lecture en cours",
        "queue": "File d'attente",
        "no_queue": "La file d'attente est vide",
        "skip": "Ignoré",
        "paused": "En pause",
        "resumed": "Repris",
        "stopped": "Arrêté",
        "volume_set": "Volume défini sur",
        "error": "Une erreur s'est produite",
        "bot_joined": "Bot a rejoint le canal vocal",
        "bot_left": "Bot a quitté le canal vocal",
        "not_connected": "Le bot n'est pas connecté à un canal vocal",
        "no_track_playing": "Aucune piste n'est en cours de lecture",
    },
}

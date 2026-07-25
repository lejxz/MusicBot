"""Embed manager for dynamic and consistent music UI cards."""
import discord
from typing import Optional
from .queue import Track
from datetime import datetime


# Standard embed colors
PRIMARY_COLOR = discord.Color.blurple()
SUCCESS_COLOR = discord.Color.green()
ERROR_COLOR = discord.Color.red()
INFO_COLOR = discord.Color.blue()


def _format_duration(seconds: int) -> str:
    if not seconds:
        return "—"
    seconds = int(seconds)
    hrs, rem = divmod(seconds, 3600)
    mins, secs = divmod(rem, 60)
    if hrs:
        return f"{hrs}:{mins:02d}:{secs:02d}"
    return f"{mins}:{secs:02d}"


class MusicEmbedManager:
    """Manages embeds for music player UI with a consistent style."""

    @staticmethod
    def create_now_playing_embed(
        track: Optional[Track],
        current_time: int = 0,
        queue_size: int = 0,
        loop_mode: int = 0,
        playback_state: Optional[str] = None,
    ) -> discord.Embed:
        """Create a now playing embed with clear fields and consistent styling."""
        state_str = str(playback_state.value if hasattr(playback_state, "value") else (playback_state or "playing")).lower()

        if not track or state_str == "idle":
            embed = discord.Embed(
                title="🎵 Now Playing",
                description="No track is currently playing.",
                color=ERROR_COLOR,
            )
            embed.timestamp = datetime.now()
            embed.set_footer(text="Discord Music Bot")
            return embed

        loop_text = {
            0: "No Loop",
            1: "Track Repeat",
            2: "Queue Repeat",
        }.get(loop_mode, "Unknown")

        source_val = getattr(track, 'source', None)
        source_str = str(source_val if source_val is not None else "unknown").capitalize()

        embed = discord.Embed(
            title="🎵 Now Playing",
            description=f"**{track.title}**\nby *{track.artist or 'Unknown'}*",
            color=PRIMARY_COLOR,
            url=getattr(track, 'url', None),
        )

        if getattr(track, 'thumbnail', None):
            embed.set_thumbnail(url=track.thumbnail)

        embed.add_field(name="Status", value=state_str.title(), inline=True)
        embed.add_field(name="Duration", value=_format_duration(track.duration), inline=True)
        embed.add_field(name="Position", value=str(queue_size), inline=True)
        embed.add_field(name="Progress", value=f"{_format_duration(current_time)} / {_format_duration(track.duration)}", inline=False)
        embed.add_field(name="Loop", value=loop_text, inline=True)
        embed.add_field(name="Source", value=source_str, inline=True)
        embed.add_field(name="Added by", value=getattr(track, 'added_by_name', 'Unknown'), inline=True)

        embed.set_footer(text="Discord Music Bot | Multi-source player")
        embed.timestamp = datetime.now()

        return embed

    @staticmethod
    def create_queue_embed(tracks: list, page: int = 1, per_page: int = 10) -> discord.Embed:
        """Create a paginated queue embed with human-friendly durations."""
        total_pages = max(1, (len(tracks) + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))

        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page

        embed = discord.Embed(
            title=f"📋 Queue ({len(tracks)} tracks)",
            color=PRIMARY_COLOR,
        )

        if not tracks:
            embed.description = "Queue is empty"
            embed.timestamp = datetime.now()
            embed.set_footer(text="Discord Music Bot")
            return embed

        for i, track in enumerate(tracks[start_idx:end_idx], start=start_idx + 1):
            embed.add_field(
                name=f"{i}. {track.title}",
                value=f"{track.artist or 'Unknown'} • {_format_duration(track.duration)} ({getattr(track, 'platform_badge', '')})",
                inline=False,
            )

        total_seconds = sum(int(t.duration or 0) for t in tracks)
        embed.set_footer(text=f"Page {page}/{total_pages} • Total: {_format_duration(total_seconds)}")
        embed.timestamp = datetime.now()

        return embed

    @staticmethod
    def create_search_result_embed(tracks: list) -> discord.Embed:
        """Create a concise search results embed (up to 10 results)."""
        embed = discord.Embed(
            title="🔍 Search Results",
            color=SUCCESS_COLOR,
            description="Select a track to play (use the selection buttons).",
        )

        for i, track in enumerate(tracks[:10], 1):
            embed.add_field(
                name=f"{i}. {track.title}",
                value=f"{track.artist or 'Unknown'} • {_format_duration(track.duration)} ({getattr(track, 'platform_badge', '')})",
                inline=False,
            )

        embed.set_footer(text="Showing up to 10 results")
        embed.timestamp = datetime.now()

        return embed

    @staticmethod
    def create_error_embed(error_msg: str) -> discord.Embed:
        """Create a standardized error embed."""
        embed = discord.Embed(
            title="❌ Error",
            description=error_msg,
            color=ERROR_COLOR,
        )
        embed.timestamp = datetime.now()
        embed.set_footer(text="Discord Music Bot")
        return embed

    @staticmethod
    def create_info_embed(title: str, description: str, color: discord.Color = INFO_COLOR) -> discord.Embed:
        """Create a standardized info embed with optional color."""
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
        )
        embed.timestamp = datetime.now()
        embed.set_footer(text="Discord Music Bot")
        return embed

"""
Unit tests for /np and /nowplaying command parity, embeds, and robust rendering.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord

from index import MusicBot
from commands.utility import UtilityCommands
from src.embeds import MusicEmbedManager
from src.player import PlaybackState, PlaybackSnapshot
from src.queue import Track


@pytest.mark.asyncio
async def test_command_registry_parity():
    bot = MagicMock()
    cog = MusicBot(bot)
    app_commands = {cmd.name: cmd for cmd in cog.__cog_app_commands__}

    assert "np" in app_commands
    assert "nowplaying" in app_commands

    cmd_np = app_commands["np"]
    cmd_nowplaying = app_commands["nowplaying"]

    assert cmd_np.description == "Show currently playing track"
    assert "alias for /np" in cmd_nowplaying.description


@pytest.mark.asyncio
async def test_utility_now_playing_delegation_parity():
    interaction_np = AsyncMock(spec=discord.Interaction)
    interaction_np.guild_id = 123
    interaction_np.response.defer = AsyncMock()
    interaction_np.followup.send = AsyncMock()

    interaction_nowplaying = AsyncMock(spec=discord.Interaction)
    interaction_nowplaying.guild_id = 123
    interaction_nowplaying.response.defer = AsyncMock()
    interaction_nowplaying.followup.send = AsyncMock()

    track = Track(title="Song", url="http://url", duration=200, source="youtube", artist="Artist")
    snapshot = PlaybackSnapshot(state=PlaybackState.PLAYING, track=track, queue_size=3, loop_mode=0, position=10.0)

    player = AsyncMock()
    player.snapshot = AsyncMock(return_value=snapshot)

    music_player = MagicMock()
    music_player.get_player.return_value = player

    await UtilityCommands.now_playing(interaction_np, music_player)
    await UtilityCommands.now_playing(interaction_nowplaying, music_player)

    assert interaction_np.followup.send.called
    assert interaction_nowplaying.followup.send.called

    embed_np = interaction_np.followup.send.call_args[1]["embed"]
    embed_nowplaying = interaction_nowplaying.followup.send.call_args[1]["embed"]

    assert embed_np.title == embed_nowplaying.title
    assert embed_np.description == embed_nowplaying.description


def test_create_now_playing_embed_idle():
    embed = MusicEmbedManager.create_now_playing_embed(
        track=None,
        playback_state=PlaybackState.IDLE,
        queue_size=0,
        loop_mode=0,
    )
    assert embed.title == "🎵 Now Playing"
    assert "No track is currently playing" in embed.description


def test_create_now_playing_embed_states():
    track = Track(title="Song", url="http://url", duration=180, source="youtube", artist="Artist")

    for state in PlaybackState:
        embed = MusicEmbedManager.create_now_playing_embed(
            track=track if state != PlaybackState.IDLE else None,
            playback_state=state,
            queue_size=2,
            loop_mode=1,
        )
        assert embed is not None
        if state == PlaybackState.IDLE:
            assert "No track" in embed.description
        else:
            assert "Song" in embed.description
            status_fields = [f for f in embed.fields if f.name == "Status"]
            assert len(status_fields) == 1
            assert status_fields[0].value == state.value.title()


def test_create_now_playing_embed_unknown_and_null_fields():
    # Track with None fields
    track = Track(title="Minimal", url="http://url", duration=None, source=None, artist=None)
    track.thumbnail = None

    embed = MusicEmbedManager.create_now_playing_embed(
        track=track,
        playback_state="unknown_state",
        queue_size=0,
        loop_mode=99,
    )

    assert embed is not None
    assert "Minimal" in embed.description
    loop_fields = [f for f in embed.fields if f.name == "Loop"]
    assert loop_fields[0].value == "Unknown"

    source_fields = [f for f in embed.fields if f.name == "Source"]
    assert source_fields[0].value == "Unknown"

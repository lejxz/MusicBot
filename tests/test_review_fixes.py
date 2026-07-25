"""Regression tests for the post-review fixes to issue #4."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.player import GuildPlayer, MusicPlayer, PlaybackState
from src.queue import Track
from src.embeds import MusicEmbedManager
from commands.queue import QueueCommands


def _player():
    return GuildPlayer(guild_id=1, music_player=MagicMock(spec=MusicPlayer))


def _track(duration=100):
    return Track(title="T", url="u", duration=duration, source="yt", artist="A")


@pytest.mark.asyncio
async def test_play_start_ts_initialized_before_first_play():
    """A fresh player must expose the clock attribute without a hasattr guard."""
    player = _player()
    assert player._play_start_ts is None
    snapshot = await player.snapshot()
    assert snapshot.position == 0.0


@pytest.mark.asyncio
async def test_position_advances_while_recovering():
    """RECOVERING still has audio flowing, so the clock must not freeze."""
    player = _player()
    player.current_track = _track()
    player._state = PlaybackState.RECOVERING

    with patch("time.monotonic") as clock:
        clock.return_value = 10.0
        player._play_start_ts = 10.0
        clock.return_value = 17.0
        snapshot = await player.snapshot()

    assert snapshot.position == 7.0


@pytest.mark.asyncio
async def test_position_zero_when_no_track():
    """Stale elapsed time must not leak after stop/skip clears current_track."""
    player = _player()
    player._elapsed_before_pause = 42.0
    player._state = PlaybackState.IDLE
    player.current_track = None

    snapshot = await player.snapshot()
    assert snapshot.position == 0.0


@pytest.mark.asyncio
async def test_pause_clears_start_ts_so_double_pause_does_not_double_count():
    player = _player()
    player.current_track = _track()
    player._state = PlaybackState.PLAYING
    vc = MagicMock()
    vc.is_playing.return_value = True
    player.voice_client = vc

    with patch("time.monotonic") as clock:
        clock.return_value = 10.0
        player._play_start_ts = 10.0
        clock.return_value = 15.0
        await player.pause()

        assert player._play_start_ts is None
        assert player._elapsed_before_pause == 5.0

        # A second pause must be a no-op, not another += of the same interval.
        clock.return_value = 30.0
        await player.pause()
        assert player._elapsed_before_pause == 5.0


def test_now_playing_embed_keeps_added_by():
    """The /np reply must not lose requester attribution."""
    track = _track()
    track.added_by_name = "Nathaniel"
    embed = MusicEmbedManager.create_now_playing_embed(track)
    assert any(f.name == "Added by" and f.value == "Nathaniel" for f in embed.fields)


def test_now_playing_embed_reports_real_state():
    """A paused track must not render as 'Playing'."""
    embed = MusicEmbedManager.create_now_playing_embed(
        _track(), playback_state=PlaybackState.PAUSED
    )
    status = next(f.value for f in embed.fields if f.name == "Status")
    assert status == "Paused"


def test_format_duration_unknown_is_dash():
    from src.embeds import _format_duration
    assert _format_duration(0) == "—"
    assert _format_duration(None) == "—"
    assert _format_duration(213) == "3:33"


@pytest.mark.asyncio
async def test_loop_out_of_range_mode_does_not_crash():
    """/loop with a bogus value must clamp, not raise IndexError."""
    interaction = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    player = _player()
    music_player = MagicMock()
    music_player.get_player.return_value = player

    await QueueCommands.loop(interaction, music_player, mode=7)

    assert player.queue.loop_mode == 2
    embed = interaction.followup.send.call_args.kwargs["embed"]
    assert "Queue Repeat" in embed.description
    assert "Error" not in embed.title


@pytest.mark.asyncio
async def test_loop_negative_mode_reports_what_was_actually_set():
    interaction = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    player = _player()
    music_player = MagicMock()
    music_player.get_player.return_value = player

    await QueueCommands.loop(interaction, music_player, mode=-1)

    assert player.queue.loop_mode == 0
    embed = interaction.followup.send.call_args.kwargs["embed"]
    assert "Off" in embed.description

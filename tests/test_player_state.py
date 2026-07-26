"""
Unit tests for PlaybackState, PlaybackSnapshot, and GuildPlayer state transitions.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from src.player import PlaybackState, PlaybackSnapshot, GuildPlayer, MusicPlayer
from src.queue import Track


def test_playback_state_values():
    assert PlaybackState.IDLE.value == "idle"
    assert PlaybackState.PREPARING.value == "preparing"
    assert PlaybackState.PLAYING.value == "playing"
    assert PlaybackState.PAUSED.value == "paused"
    assert PlaybackState.RECOVERING.value == "recovering"
    assert PlaybackState.STOPPING.value == "stopping"


def test_playback_snapshot_invariants():
    track = Track(title="T", url="http://u", duration=100, source="youtube", artist="A")

    s_idle = PlaybackSnapshot(state=PlaybackState.IDLE, track=None, queue_size=0, loop_mode=0, position=0.0)
    assert not s_idle.is_playing
    assert not s_idle.is_paused

    s_prep = PlaybackSnapshot(state=PlaybackState.PREPARING, track=track, queue_size=1, loop_mode=0, position=0.0)
    assert s_prep.is_playing
    assert not s_prep.is_paused

    s_play = PlaybackSnapshot(state=PlaybackState.PLAYING, track=track, queue_size=1, loop_mode=0, position=0.0)
    assert s_play.is_playing
    assert not s_play.is_paused

    s_pause = PlaybackSnapshot(state=PlaybackState.PAUSED, track=track, queue_size=1, loop_mode=0, position=0.0)
    assert s_pause.is_playing
    assert s_pause.is_paused

    s_rec = PlaybackSnapshot(state=PlaybackState.RECOVERING, track=track, queue_size=1, loop_mode=0, position=0.0)
    assert s_rec.is_playing
    assert not s_rec.is_paused

    s_stop = PlaybackSnapshot(state=PlaybackState.STOPPING, track=track, queue_size=0, loop_mode=0, position=0.0)
    assert not s_stop.is_playing
    assert not s_stop.is_paused


class FakeVoiceClient:
    def __init__(self):
        self._playing = False
        self._paused = False
        self.stopped = False
        self.disconnected = False
        self.played_sources = []
        self.after_callback = None

    def is_playing(self):
        return self._playing

    def is_paused(self):
        return self._paused

    def play(self, source, after=None):
        self._playing = True
        self._paused = False
        self.played_sources.append(source)
        self.after_callback = after

    def pause(self):
        if self._playing:
            self._playing = False
            self._paused = True

    def resume(self):
        if self._paused:
            self._paused = True
            self._playing = True
            self._paused = False

    def stop(self):
        self.stopped = True
        self._playing = False
        self._paused = False

    async def disconnect(self):
        self.disconnected = True
        self.stop()


@pytest.mark.asyncio
async def test_guild_player_initial_state():
    mp = MagicMock(spec=MusicPlayer)
    player = GuildPlayer(guild_id=1, music_player=mp)

    snapshot = await player.snapshot()
    assert snapshot.state == PlaybackState.IDLE
    assert snapshot.track is None
    assert not player.is_playing
    assert not player.is_paused


@pytest.mark.asyncio
async def test_guild_player_pause_resume():
    mp = MagicMock(spec=MusicPlayer)
    player = GuildPlayer(guild_id=1, music_player=mp)
    vc = FakeVoiceClient()
    player.voice_client = vc

    # Cannot pause when idle
    assert not await player.pause()

    # Simulate playing state
    player._state = PlaybackState.PLAYING
    vc._playing = True

    assert await player.pause()
    assert player._state == PlaybackState.PAUSED
    assert player.is_paused
    assert player.is_playing

    assert await player.resume()
    assert player._state == PlaybackState.PLAYING
    assert not player.is_paused
    assert player.is_playing


@pytest.mark.asyncio
async def test_guild_player_stop():
    mp = MagicMock(spec=MusicPlayer)
    player = GuildPlayer(guild_id=1, music_player=mp)
    vc = FakeVoiceClient()
    player.voice_client = vc

    track = Track(title="T", url="http://u", duration=100, source="youtube", artist="A")
    await player.queue.add(track)
    player.current_track = track
    player._state = PlaybackState.PLAYING
    vc._playing = True

    gen_before = player._generation
    await player.stop()

    assert player._generation > gen_before
    assert vc.stopped
    assert player._state == PlaybackState.IDLE
    assert player.current_track is None
    assert await player.queue.size() == 1


@pytest.mark.asyncio
async def test_guild_player_disconnect_while_paused():
    mp = MagicMock(spec=MusicPlayer)
    player = GuildPlayer(guild_id=1, music_player=mp)
    vc = FakeVoiceClient()
    player.voice_client = vc

    player._state = PlaybackState.PAUSED
    player.current_track = Track(title="T", url="http://u", duration=100, source="youtube", artist="A")
    vc._paused = True

    await player.disconnect()

    assert player._state == PlaybackState.IDLE
    assert not player.is_paused
    assert not player.is_playing
    assert player.current_track is None
    assert player.voice_client is None


@pytest.mark.asyncio
async def test_guild_player_seek_does_not_advance_clock_until_playback_starts():
    mp = MagicMock(spec=MusicPlayer)
    player = GuildPlayer(guild_id=1, music_player=mp)
    vc = FakeVoiceClient()
    player.voice_client = vc

    player.current_track = Track(title="T", url="http://u", duration=100, source="youtube", artist="A")
    player._state = PlaybackState.PLAYING
    player._play_start_ts = 123.0
    player._elapsed_before_pause = 5.0

    with patch.object(player, "_create_audio_source", new=AsyncMock(return_value=MagicMock())) as mock_source, \
         patch.object(player, "_cleanup_current_source") as mock_cleanup:
        mock_source.return_value.cleanup = MagicMock()
        player._source = MagicMock()
        success = await player.seek(30)

    assert success is True
    assert player._play_start_ts is not None
    assert player._play_start_ts != 123.0
    mock_cleanup.assert_called_once()

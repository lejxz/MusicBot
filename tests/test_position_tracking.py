"""
Unit tests for position tracking.
"""
import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

from src.player import PlaybackState, PlaybackSnapshot, GuildPlayer, MusicPlayer
from src.queue import Track


class FakeVoiceClient:
    def __init__(self):
        self._playing = False
        self._paused = False

    def is_playing(self):
        return self._playing

    def is_paused(self):
        return self._paused

    def play(self, source, after=None):
        self._playing = True
        self._paused = False

    def pause(self):
        if self._playing:
            self._playing = False
            self._paused = True

    def resume(self):
        if self._paused:
            self._paused = False
            self._playing = True


@pytest.mark.asyncio
async def test_position_advances_during_playback():
    mp = MagicMock(spec=MusicPlayer)
    player = GuildPlayer(guild_id=1, music_player=mp)
    vc = FakeVoiceClient()
    player.voice_client = vc

    track = Track(title="T", url="u", duration=100, source="yt", artist="A")
    player.current_track = track
    player._state = PlaybackState.PLAYING
    
    with patch("time.monotonic") as mock_time:
        mock_time.return_value = 10.0
        player._play_start_ts = 10.0
        player._elapsed_before_pause = 0.0
        
        mock_time.return_value = 15.0
        snapshot = await player.snapshot()
        assert snapshot.position == 5.0


@pytest.mark.asyncio
async def test_position_freezes_on_pause():
    mp = MagicMock(spec=MusicPlayer)
    player = GuildPlayer(guild_id=1, music_player=mp)
    vc = FakeVoiceClient()
    player.voice_client = vc
    vc.play(None)

    track = Track(title="T", url="u", duration=100, source="yt", artist="A")
    player.current_track = track
    player._state = PlaybackState.PLAYING
    
    with patch("time.monotonic") as mock_time:
        mock_time.return_value = 10.0
        player._play_start_ts = 10.0
        player._elapsed_before_pause = 0.0
        
        mock_time.return_value = 15.0
        await player.pause()
        
        mock_time.return_value = 25.0
        snapshot = await player.snapshot()
        assert snapshot.position == 5.0


@pytest.mark.asyncio
async def test_position_resumes_correctly():
    mp = MagicMock(spec=MusicPlayer)
    player = GuildPlayer(guild_id=1, music_player=mp)
    vc = FakeVoiceClient()
    player.voice_client = vc
    vc.play(None)

    track = Track(title="T", url="u", duration=100, source="yt", artist="A")
    player.current_track = track
    player._state = PlaybackState.PLAYING
    
    with patch("time.monotonic") as mock_time:
        mock_time.return_value = 10.0
        player._play_start_ts = 10.0
        player._elapsed_before_pause = 0.0
        
        mock_time.return_value = 15.0
        await player.pause()
        
        mock_time.return_value = 25.0
        await player.resume()
        
        mock_time.return_value = 30.0
        snapshot = await player.snapshot()
        assert snapshot.position == 10.0


@pytest.mark.asyncio
async def test_position_clamped_to_duration():
    mp = MagicMock(spec=MusicPlayer)
    player = GuildPlayer(guild_id=1, music_player=mp)
    vc = FakeVoiceClient()
    player.voice_client = vc

    track = Track(title="T", url="u", duration=10, source="yt", artist="A")
    player.current_track = track
    player._state = PlaybackState.PLAYING
    
    with patch("time.monotonic") as mock_time:
        mock_time.return_value = 10.0
        player._play_start_ts = 10.0
        player._elapsed_before_pause = 0.0
        
        mock_time.return_value = 25.0
        snapshot = await player.snapshot()
        assert snapshot.position == 10.0

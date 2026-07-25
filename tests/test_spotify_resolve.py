import pytest
from unittest.mock import AsyncMock, MagicMock
import discord

from commands.play import PlayCommand
from src.queue import Track

@pytest.mark.asyncio
async def test_spotify_resolve_failure_prevents_queue():
    # Setup mocks
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user.voice = True
    interaction.guild_id = 123
    interaction.channel = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    
    music_player = MagicMock()
    player = MagicMock()
    player.voice_client = True
    music_player.get_player.return_value = player
    player.queue.add = AsyncMock()
    
    music_player.spotify.get_track_info = AsyncMock(return_value=Track(
        title="Test Song", 
        artist="Test Artist", 
        url="spotify:track:123",
        duration=0,
        source="spotify"
    ))
    
    # Mock resolve to return None
    original_resolve = PlayCommand._resolve_youtube_audio
    PlayCommand._resolve_youtube_audio = AsyncMock(return_value=None)
    
    try:
        await PlayCommand.play(interaction, "https://open.spotify.com/track/123", music_player)
        
        # Should not queue
        player.queue.add.assert_not_called()
        
        # Should send error
        interaction.followup.send.assert_called_once()
        args = interaction.followup.send.call_args[1]
        assert "embed" in args
        assert "Could not resolve playable track from Spotify" in str(args["embed"].description)
    finally:
        PlayCommand._resolve_youtube_audio = original_resolve


@pytest.mark.asyncio
async def test_spotify_resolve_success_passes_target_duration():
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user.voice = True
    interaction.guild_id = 123
    interaction.channel = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    
    music_player = MagicMock()
    player = MagicMock()
    player.voice_client = True
    player.is_playing = True # prevent play_next
    music_player.get_player.return_value = player
    player.queue.add = AsyncMock()
    
    # Track with duration 180s
    spotify_track = Track(
        title="Test Song", 
        artist="Test Artist", 
        url="spotify:track:123",
        duration=180,
        source="spotify"
    )
    music_player.spotify.get_track_info = AsyncMock(return_value=spotify_track)
    
    # Mock resolve to check if it gets target_duration
    mock_resolve = AsyncMock(return_value=Track(
        title="Test Song",
        artist="Test Artist",
        url="https://youtube.com/watch?v=123",
        duration=185,
        source="youtube"
    ))
    
    original_resolve = PlayCommand._resolve_youtube_audio
    PlayCommand._resolve_youtube_audio = mock_resolve
    
    try:
        await PlayCommand.play(interaction, "https://open.spotify.com/track/123", music_player)
        
        # Should queue
        player.queue.add.assert_called_once()
        queued_track = player.queue.add.call_args[0][0]
        
        assert queued_track.url == "https://youtube.com/watch?v=123"
        assert queued_track.source == "youtube"
        assert queued_track.duration == 180 # Should keep Spotify duration (or whatever the mock returns for Spotify track since track is modified in place, wait, track.duration isn't modified in the code, so it carries Spotify duration)
        
        # Ensure target_duration was passed for scoring
        mock_resolve.assert_called_once_with(music_player, "Test Song", "Test Artist", 180)
        
    finally:
        PlayCommand._resolve_youtube_audio = original_resolve

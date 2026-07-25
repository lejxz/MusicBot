import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from commands.audio import AudioCommands

@pytest.mark.asyncio
async def test_lyrics_explicit_song_fallback():
    """Test that explicit song param is used for LRCLIB when provided."""
    interaction = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    
    music_player = MagicMock()
    player = MagicMock()
    player.current_track.title = "Current Track"
    player.current_track.artist = "Current Artist"
    music_player.get_player.return_value = player
    
    # ponytail: mock lyrics fetchers
    with patch("commands.audio.LyricsManager.fetch_from_genius", new_callable=AsyncMock) as mock_genius:
        with patch("commands.audio.LyricsManager.fetch_from_lrclib", new_callable=AsyncMock) as mock_lrclib:
            # mock failure on genius to force lrclib fallback
            mock_genius.return_value = None
            mock_lrclib.return_value = "Test Lyrics"
            
            with patch("config.Config.GENIUS_ACCESS_TOKEN", "mock_token"):
                await AudioCommands.lyrics(interaction, music_player, song="Explicit Song Title")
                
                mock_lrclib.assert_called_once_with("Explicit Song Title", "")

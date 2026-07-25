import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.providers import SpotifyProvider
from src.queue import Track
from commands.play import PlayCommand

@pytest.mark.asyncio
async def test_spotify_fallback_order():
    provider = SpotifyProvider("dummy", "dummy")
    
    with patch.object(provider, '_get_spotipy_client', return_value=None), \
         patch.object(provider, '_get_access_token', new_callable=AsyncMock) as mock_token, \
         patch.object(provider, '_fetch_oembed_metadata', new_callable=AsyncMock) as mock_oembed, \
         patch('aiohttp.ClientSession.get') as mock_get:
        
        # Test Web API succeeds -> oEmbed not called
        mock_token.return_value = "dummy_token"
        
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json.return_value = {
            'name': 'API Track',
            'duration_ms': 120000,
            'artists': [{'name': 'API Artist'}],
            'album': {'images': [{'url': 'api_url'}]}
        }
        
        mock_get.return_value.__aenter__.return_value = mock_resp
        
        track = await provider.get_track_info("https://open.spotify.com/track/123")
        
        assert track.title == "API Track"
        mock_token.assert_called_once()
        mock_oembed.assert_not_called()
        
        # Test Web API fails -> oEmbed is called
        mock_token.reset_mock()
        mock_get.reset_mock()
        mock_oembed.reset_mock()
        
        mock_resp.status = 404
        mock_oembed.return_value = {
            'title': 'oEmbed Track',
            'author_name': 'oEmbed Artist',
            'thumbnail_url': 'oembed_url'
        }
        
        track = await provider.get_track_info("https://open.spotify.com/track/123")
        
        assert track.title == "oEmbed Track"
        mock_token.assert_called_once()
        mock_oembed.assert_called_once()


def test_merge_resolved():
    # Test duration 0 -> adopts YT duration
    track = Track(
        title="Spotify Track",
        url="spotify_url",
        duration=0,
        source="spotify",
        artist="Spotify Artist",
        thumbnail="spotify_thumb"
    )
    
    yt_track = Track(
        title="YT Track",
        url="yt_url",
        duration=180,
        source="youtube",
        artist="YT Artist",
        thumbnail="yt_thumb"
    )
    
    PlayCommand._merge_resolved(track, yt_track)
    
    assert track.url == "yt_url"
    assert track.source == "youtube"
    assert track.thumbnail == "yt_thumb"
    assert track.duration == 180

    # Test duration > 0 -> keeps Spotify duration
    track2 = Track(
        title="Spotify Track",
        url="spotify_url",
        duration=200,
        source="spotify",
        artist="Spotify Artist"
    )
    
    PlayCommand._merge_resolved(track2, yt_track)
    assert track2.duration == 200

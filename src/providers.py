"""
Music providers for YouTube and Spotify with error handling and source selection
"""
import asyncio
import aiohttp
import logging
from typing import List, Optional, Tuple, Literal
from urllib.parse import urlparse, parse_qs, quote_plus
from .queue import Track
from .stream_cache import StreamCache
import yt_dlp
from config import Config

try:
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials
except Exception:  # pragma: no cover - optional dependency guard
    spotipy = None
    SpotifyClientCredentials = None


logger = logging.getLogger(__name__)


class YouTubeProvider:
    """YouTube music provider with caching and error handling"""
    
    def __init__(self):
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch',
            'socket_timeout': 30,
            'extract_flat': False,  # Get full info
        }
        self.stream_cache = StreamCache(ttl_hours=24)
        self.search_cache = {}  # Basic search result cache

    @staticmethod
    def _is_youtube_url(url: str) -> bool:
        """Check whether the input is a YouTube-family URL."""
        parsed = urlparse(url)
        host = parsed.netloc.lower().split(":")[0]
        return host in {
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
            "music.youtube.com",
            "youtu.be",
            "www.youtu.be",
            "youtube-nocookie.com",
            "www.youtube-nocookie.com",
        }

    @staticmethod
    def _normalize_youtube_url(url: str) -> str:
        """Normalize YouTube Music links to standard YouTube watch URLs when possible."""
        parsed = urlparse(url)
        host = parsed.netloc.lower().split(":")[0]

        if host == "music.youtube.com":
            params = parse_qs(parsed.query)
            video_id = params.get("v", [None])[0]
            if video_id:
                return f"https://www.youtube.com/watch?v={video_id}"

        return url
    
    async def search(self, query: str, limit: int = 1, source: Optional[Literal['youtube', 'youtube_music']] = None) -> List[Track]:
        """
        Search YouTube for tracks with optional source preference
        
        Args:
            query: Search query
            limit: Number of results
            source: Preferred source ('youtube' or 'youtube_music'), tries both if None
        
        Returns:
            List of Track objects
        """
        # If the input is already a YouTube URL, resolve it directly instead of treating it as a search query.
        if self._is_youtube_url(query):
            direct_track = await self.get_track_from_url(query)
            if direct_track:
                return [direct_track]
            return []

        # YouTube Music search (better for music content)
        if source == 'youtube_music' or (source is None and 'music.youtube.com' in query.lower()):
            yt_music_results = await self._search_youtube_music(query, limit)
            if yt_music_results:
                logger.info(f"YouTube Music search found {len(yt_music_results)} results")
                return yt_music_results
        
        # Regular YouTube search via API or yt-dlp
        if Config.YOUTUBE_API_KEY and source != 'youtube_music':
            api_results = await self._search_with_youtube_api(query, limit)
            if api_results:
                logger.info(f"YouTube search found {len(api_results)} results via API")
                return api_results

        loop = asyncio.get_event_loop()
        
        def _search():
            try:
                with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                    search_query = f"ytsearch{limit}:{query}"
                    results = ydl.extract_info(search_query, download=False)
                    tracks = []
                    
                    for entry in results.get('entries', []):
                        if not entry:
                            continue
                        
                        # Skip live streams and age-restricted content
                        if entry.get('is_live') or entry.get('age_limit', 0) > 13:
                            logger.debug(f"Skipping live/age-restricted: {entry.get('title')}")
                            continue
                        
                        track = Track(
                            title=entry.get('title', 'Unknown'),
                            url=entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}",
                            duration=entry.get('duration', 0),
                            source='youtube',
                            artist=entry.get('uploader', 'Unknown'),
                            thumbnail=entry.get('thumbnail', ''),
                            platform_badge='🎥 YouTube',
                        )
                        tracks.append(track)
                    return tracks
            except yt_dlp.utils.DownloadError as e:
                logger.warning(f"YouTube search download error: {str(e)[:100]}")
                return []
            except Exception as e:
                logger.exception("YouTube search error")
                return []
        
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(None, _search),
                timeout=15.0
            )
        except asyncio.TimeoutError:
            logger.warning("YouTube search timed out")
            return []

    async def get_track_from_url(self, url: str) -> Optional[Track]:
        """Extract metadata for a direct YouTube video URL."""
        normalized_url = self._normalize_youtube_url(url)

        loop = asyncio.get_event_loop()

        def _extract_track():
            try:
                with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                    info = ydl.extract_info(normalized_url, download=False)

                    if not info or info.get("_type") == "playlist" or info.get("entries"):
                        return None

                    title = info.get("title", "Unknown")
                    uploader = info.get("uploader") or info.get("channel") or "Unknown"
                    video_url = info.get("webpage_url") or info.get("url") or normalized_url
                    source = "youtube_music" if "music.youtube.com" in url.lower() else "youtube"

                    return Track(
                        title=title,
                        url=video_url,
                        duration=info.get("duration", 0) or 0,
                        source=source,
                        artist=uploader,
                        thumbnail=info.get("thumbnail", ""),
                        platform_badge="🎵 YouTube Music" if source == "youtube_music" else "🎥 YouTube",
                    )
            except Exception as e:
                logger.warning(f"Failed to resolve direct YouTube URL: {str(e)[:100]}")
                return None

        try:
            return await asyncio.wait_for(
                loop.run_in_executor(None, _extract_track),
                timeout=20.0,
            )
        except asyncio.TimeoutError:
            logger.warning(f"Direct YouTube URL resolution timed out for {normalized_url}")
            return None

    async def _search_youtube_music(self, query: str, limit: int = 1) -> List[Track]:
        """Search YouTube Music via yt-dlp
        
        YouTube Music provides better music-specific results than regular YouTube
        """
        loop = asyncio.get_event_loop()
        
        def _search_music():
            try:
                # YouTube Music search options
                ydl_opts_music = self.ydl_opts.copy()
                ydl_opts_music['default_search'] = 'ytsearchmusic'  # Music-specific search
                
                with yt_dlp.YoutubeDL(ydl_opts_music) as ydl:
                    search_query = f"ytsearchmusic{limit}:{query}"
                    results = ydl.extract_info(search_query, download=False)
                    tracks = []
                    
                    for entry in results.get('entries', []):
                        if not entry:
                            continue
                        
                        track = Track(
                            title=entry.get('title', 'Unknown'),
                            url=entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}",
                            duration=entry.get('duration', 0),
                            source='youtube_music',
                            artist=entry.get('uploader', 'Unknown'),
                            thumbnail=entry.get('thumbnail', ''),
                            platform_badge='🎵 YouTube Music',
                        )
                        tracks.append(track)
                    
                    return tracks
            except Exception as e:
                logger.warning(f"YouTube Music search failed: {str(e)[:100]}")
                return []
        
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(None, _search_music),
                timeout=15.0
            )
        except asyncio.TimeoutError:
            logger.warning("YouTube Music search timed out")
            return []

    async def _search_with_youtube_api(self, query: str, limit: int = 1) -> List[Track]:
        """Search YouTube using the Data API v3"""
        params = {
            "part": "snippet",
            "type": "video",
            "maxResults": limit,
            "q": query,
            "key": Config.YOUTUBE_API_KEY,
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://www.googleapis.com/youtube/v3/search",
                params=params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    return []

                data = await resp.json()
                tracks = []
                for item in data.get("items", []):
                    snippet = item.get("snippet", {})
                    video_id = item.get("id", {}).get("videoId")
                    if not video_id:
                        continue

                    tracks.append(
                        Track(
                            title=snippet.get("title", "Unknown"),
                            url=f"https://www.youtube.com/watch?v={video_id}",
                            duration=0,
                            source="youtube",
                            artist=snippet.get("channelTitle", "Unknown"),
                            thumbnail=snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                            platform_badge="🎥 YouTube",
                        )
                    )

                return tracks

    async def get_playlist_tracks(self, url: str) -> List[Track]:
        """Extract tracks from a YouTube playlist URL with error handling"""
        loop = asyncio.get_event_loop()

        def _extract_playlist():
            try:
                with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    tracks = []
                    entries = info.get("entries", []) or []
                    
                    logger.info(f"YouTube playlist: found {len(entries)} entries")

                    for i, entry in enumerate(entries):
                        if not entry:
                            continue
                        
                        # Skip deleted/unavailable videos
                        if entry.get('availability') == 'needs_auth':
                            logger.debug(f"Skipping private video at index {i}")
                            continue

                        tracks.append(
                            Track(
                                title=entry.get("title", "Unknown"),
                                url=entry.get("webpage_url") or entry.get("url") or f"https://www.youtube.com/watch?v={entry.get('id')}",
                                duration=entry.get("duration", 0),
                                source="youtube",
                                artist=entry.get("uploader", "Unknown"),
                                thumbnail=entry.get("thumbnail", ""),
                                platform_badge="🎥 YouTube",
                            )
                        )

                    return tracks
            except yt_dlp.utils.DownloadError as e:
                logger.error(f"YouTube playlist download error: {str(e)[:150]}")
                return []
            except Exception as e:
                logger.exception("YouTube playlist extraction error")
                return []

        try:
            return await asyncio.wait_for(
                loop.run_in_executor(None, _extract_playlist),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            logger.warning("YouTube playlist extraction timed out")
            return []
    
    async def get_stream_url(self, url: str) -> Optional[str]:
        """Get direct stream URL from YouTube link (with caching)
        
        Supports: youtube.com, youtu.be, music.youtube.com
        """
        # Normalize YouTube Music URLs to regular YouTube URLs
        normalized_url = self._normalize_youtube_url(url)
        if normalized_url != url:
            logger.info(f"Converted YouTube Music URL to: {normalized_url}")
        
        # Check cache first
        cached_url = await self.stream_cache.get(normalized_url)
        if cached_url:
            logger.info(f"Using cached stream URL for {normalized_url[:50]}")
            return cached_url
        
        loop = asyncio.get_event_loop()
        
        def _get_url():
            try:
                with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                    info = ydl.extract_info(normalized_url, download=False)
                    stream_url = info.get('url')
                    
                    # Check for errors in response
                    if not stream_url:
                        logger.error(f"No stream URL found in yt-dlp response for {normalized_url}")
                        return None
                    
                    return stream_url
            except yt_dlp.utils.ExtractorError as e:
                error_msg = str(e)
                if 'private' in error_msg.lower():
                    logger.warning(f"Cannot access private video: {normalized_url}")
                elif 'age_gate' in error_msg.lower() or 'age' in error_msg.lower():
                    logger.warning(f"Age-restricted video: {normalized_url}")
                else:
                    logger.warning(f"Extractor error for {normalized_url}: {error_msg[:100]}")
                return None
            except Exception as e:
                logger.exception(f"YouTube stream URL error for {normalized_url}")
                return None
        
        try:
            stream_url = await asyncio.wait_for(
                loop.run_in_executor(None, _get_url),
                timeout=20.0
            )
            
            if stream_url:
                # Cache the result
                await self.stream_cache.set(normalized_url, stream_url)
                logger.info(f"Resolved stream URL for {normalized_url[:50]} (duration: <20s)")
            
            return stream_url
        except asyncio.TimeoutError:
            logger.warning(f"Stream URL resolution timed out for {url}")
            return None


class SpotifyProvider:
    """Spotify music provider"""
    
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token: Optional[str] = None
        self.token_expires_at = 0
        self._spotipy_client = None

    @staticmethod
    def _normalize_spotify_url(spotify_url: str) -> str:
        """Strip locale prefixes and query fragments from Spotify URLs."""
        try:
            if spotify_url.startswith("spotify:"):
                return spotify_url

            parsed = urlparse(spotify_url)
            parts = [part for part in parsed.path.split('/') if part]
            if parts and parts[0].startswith("intl-"):
                parts = parts[1:]

            if len(parts) >= 2:
                return f"https://open.spotify.com/{parts[0]}/{parts[1]}"
        except Exception:
            pass

        return spotify_url

    def _parse_spotify_url(self, spotify_url: str) -> Tuple[Optional[str], Optional[str]]:
        """Parse Spotify URL and return (resource_type, resource_id)."""
        try:
            spotify_url = self._normalize_spotify_url(spotify_url)

            if spotify_url.startswith("spotify:"):
                parts = [part for part in spotify_url.split(":") if part]
                if len(parts) >= 3:
                    return parts[1], parts[2]

            parsed = urlparse(spotify_url)
            parts = [part for part in parsed.path.split('/') if part]
            if parts and parts[0].startswith("intl-"):
                parts = parts[1:]

            if len(parts) >= 2:
                return parts[0], parts[1]
        except Exception:
            return None, None

        return None, None

    def _get_spotipy_client(self):
        """Build or return a cached spotipy client if credentials are available."""
        if self._spotipy_client is not None:
            return self._spotipy_client

        if not self.client_id or not self.client_secret or spotipy is None or SpotifyClientCredentials is None:
            return None

        try:
            credentials = SpotifyClientCredentials(
                client_id=self.client_id,
                client_secret=self.client_secret,
            )
            self._spotipy_client = spotipy.Spotify(client_credentials_manager=credentials)
            return self._spotipy_client
        except Exception as e:
            logger.warning(f"Could not initialize spotipy client: {e}")
            return None

    async def _fetch_oembed_metadata(self, spotify_url: str) -> Optional[dict]:
        """Fetch basic Spotify metadata without authentication."""
        encoded_url = quote_plus(spotify_url)
        endpoint = f"https://open.spotify.com/oembed?url={encoded_url}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(endpoint, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        return None
                    return await resp.json()
        except Exception as e:
            logger.debug(f"Spotify oEmbed lookup failed: {e}")
            return None
    
    async def _get_access_token(self) -> Optional[str]:
        """Get Spotify access token with error handling"""
        import time
        import base64
        
        current_time = time.time()
        if self.access_token and current_time < self.token_expires_at:
            return self.access_token
        
        try:
            auth_str = f"{self.client_id}:{self.client_secret}"
            auth_bytes = base64.b64encode(auth_str.encode()).decode()
            
            async with aiohttp.ClientSession() as session:
                headers = {
                    'Authorization': f'Basic {auth_bytes}',
                    'Content-Type': 'application/x-www-form-urlencoded',
                }
                data = {'grant_type': 'client_credentials'}
                
                async with session.post(
                    'https://accounts.spotify.com/api/token',
                    headers=headers,
                    data=data,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        json_data = await resp.json()
                        self.access_token = json_data['access_token']
                        self.token_expires_at = current_time + json_data['expires_in']
                        logger.debug("Spotify access token refreshed")
                        return self.access_token
                    else:
                        logger.error(f"Spotify token error: HTTP {resp.status}")
                        return None
        except Exception as e:
            logger.exception("Spotify token acquisition failed")
            return None
    
    async def search(self, query: str, limit: int = 1) -> List[Track]:
        """Search Spotify for tracks with error handling"""
        token = await self._get_access_token()
        if not token:
            logger.warning("Cannot search Spotify: no access token")
            return []
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    'Authorization': f'Bearer {token}',
                }
                params = {
                    'q': query,
                    'type': 'track',
                    'limit': limit,
                }
                
                async with session.get(
                    'https://api.spotify.com/v1/search',
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        tracks = []
                        for item in data.get('tracks', {}).get('items', []):
                            track = Track(
                                title=item.get('name', 'Unknown'),
                                url=item.get('external_urls', {}).get('spotify', ''),
                                duration=item.get('duration_ms', 0) // 1000,
                                source='spotify',
                                artist=', '.join([artist['name'] for artist in item.get('artists', [])]),
                                thumbnail=item.get('album', {}).get('images', [{}])[0].get('url', ''),
                                platform_badge='🎵 Spotify',
                            )
                            tracks.append(track)
                        logger.debug(f"Spotify search found {len(tracks)} tracks")
                        return tracks
                    elif resp.status == 401:
                        logger.warning("Spotify search: invalid token")
                        self.access_token = None  # Force token refresh
                        return []
                    else:
                        logger.error(f"Spotify search error: HTTP {resp.status}")
                        return []
        except asyncio.TimeoutError:
            logger.warning("Spotify search timed out")
            return []
        except Exception as e:
            logger.exception("Spotify search failed")
            return []
    
    async def get_track_info(self, spotify_url: str) -> Optional[Track]:
        """Extract metadata from Spotify link"""
        resource_type, track_id = self._parse_spotify_url(spotify_url)
        if resource_type != "track" or not track_id:
            return None
        
        client = self._get_spotipy_client()
        if client is not None:
            try:
                item = client.track(track_id)
                return Track(
                    title=item.get('name', 'Unknown'),
                    url=spotify_url,
                    duration=item.get('duration_ms', 0) // 1000,
                    source='spotify',
                    artist=', '.join([artist['name'] for artist in item.get('artists', [])]),
                    thumbnail=item.get('album', {}).get('images', [{}])[0].get('url', ''),
                    platform_badge='🎵 Spotify',
                )
            except Exception as e:
                logger.warning(f"spotipy track lookup failed for {spotify_url}: {e}")

        metadata = await self._fetch_oembed_metadata(spotify_url)
        if metadata:
            title = metadata.get('title', 'Unknown')
            artist = metadata.get('author_name', 'Unknown')
            thumbnail = metadata.get('thumbnail_url', '')
            return Track(
                title=title,
                url=spotify_url,
                duration=0,
                source='spotify',
                artist=artist,
                thumbnail=thumbnail,
                platform_badge='🎵 Spotify',
            )

        token = await self._get_access_token()
        if not token:
            return None
        
        async with aiohttp.ClientSession() as session:
            headers = {
                'Authorization': f'Bearer {token}',
            }
            
            async with session.get(
                f'https://api.spotify.com/v1/tracks/{track_id}',
                headers=headers
            ) as resp:
                if resp.status == 200:
                    item = await resp.json()
                    track = Track(
                        title=item.get('name', 'Unknown'),
                        url=spotify_url,
                        duration=item.get('duration_ms', 0) // 1000,
                        source='spotify',
                        artist=', '.join([artist['name'] for artist in item.get('artists', [])]),
                        thumbnail=item.get('album', {}).get('images', [{}])[0].get('url', ''),
                        platform_badge='🎵 Spotify',
                    )
                    return track
        
        return None

    async def get_playlist_tracks(self, spotify_url: str, limit: int = 100) -> List[Track]:
        """Extract track metadata from a Spotify playlist link
        
        Falls back to YouTube playlist search if Spotify API access fails (e.g., free account)
        """
        resource_type, playlist_id = self._parse_spotify_url(spotify_url)
        if resource_type != "playlist" or not playlist_id:
            return []

        client = self._get_spotipy_client()
        if client is None:
            token = await self._get_access_token()
            if not token:
                logger.warning("Spotify playlist lookup unavailable: no API credentials")
                return []

        tracks: List[Track] = []

        if client is not None:
            try:
                offset = 0
                while len(tracks) < limit:
                    page = client.playlist_items(
                        playlist_id,
                        fields="items(track(name, duration_ms, id, external_urls, artists(name), album(images))),next",
                        limit=min(100, limit - len(tracks)),
                        offset=offset,
                    )
                    items = page.get('items', []) or []
                    if not items:
                        break

                    for item in items:
                        track_data = item.get('track') or {}
                        if not track_data:
                            continue

                        track_url = track_data.get('external_urls', {}).get('spotify')
                        if not track_url and track_data.get('id'):
                            track_url = f"https://open.spotify.com/track/{track_data['id']}"

                        tracks.append(
                            Track(
                                title=track_data.get('name', 'Unknown'),
                                url=track_url or spotify_url,
                                duration=track_data.get('duration_ms', 0) // 1000,
                                source='spotify',
                                artist=', '.join([artist['name'] for artist in track_data.get('artists', [])]),
                                thumbnail=track_data.get('album', {}).get('images', [{}])[0].get('url', ''),
                                platform_badge='🎵 Spotify',
                            )
                        )

                    if not page.get('next'):
                        break
                    offset += len(items)
                return tracks
            except Exception as e:
                error_str = str(e).lower()
                if 'premium' in error_str or '403' in error_str:
                    logger.info(
                        f"Spotify playlist access denied (free account detected). "
                        f"Attempting alternative methods to fetch tracks..."
                    )
                    # Try to get tracks via direct API endpoint without spotipy library
                    api_tracks = await self._fetch_playlist_tracks_via_api(playlist_id, limit)
                    if api_tracks:
                        logger.info(f"Successfully fetched {len(api_tracks)} tracks via alternative API method")
                        return api_tracks
                    
                    # Fallback: get playlist name via oEmbed and search YouTube
                    metadata = await self._fetch_oembed_metadata(spotify_url)
                    if metadata and 'title' in metadata:
                        playlist_name = metadata['title']
                        logger.info(f"Falling back to YouTube search for playlist: {playlist_name}")
                        yt_tracks = await self._search_youtube_playlist_by_name(playlist_name, limit)
                        if yt_tracks:
                            return yt_tracks
                else:
                    logger.warning(f"spotipy playlist lookup failed for {spotify_url}: {e}")
                tracks = []

        if tracks:
            return tracks

        token = await self._get_access_token()
        if not token:
            return []

        headers = {
            'Authorization': f'Bearer {token}',
        }

        tracks: List[Track] = []
        offset = 0
        page_size = min(100, max(1, limit))

        async with aiohttp.ClientSession() as session:
            while len(tracks) < limit:
                params = {
                    'limit': min(page_size, limit - len(tracks)),
                    'offset': offset,
                }
                async with session.get(
                    f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks',
                    headers=headers,
                    params=params,
                ) as resp:
                    if resp.status != 200:
                        break

                    data = await resp.json()
                    items = data.get('items', [])
                    if not items:
                        break

                    for item in items:
                        track_data = item.get('track') or {}
                        if not track_data:
                            continue

                        track_url = track_data.get('external_urls', {}).get('spotify')
                        if not track_url and track_data.get('id'):
                            track_url = f"https://open.spotify.com/track/{track_data['id']}"

                        tracks.append(
                            Track(
                                title=track_data.get('name', 'Unknown'),
                                url=track_url or spotify_url,
                                duration=track_data.get('duration_ms', 0) // 1000,
                                source='spotify',
                                artist=', '.join([artist['name'] for artist in track_data.get('artists', [])]),
                                thumbnail=track_data.get('album', {}).get('images', [{}])[0].get('url', ''),
                                platform_badge='🎵 Spotify',
                            )
                        )

                    if not data.get('next'):
                        break
                    offset += len(items)

        return tracks
    
    async def _search_youtube_playlist_by_name(self, playlist_name: str, limit: int = 100) -> List[Track]:
        """Search YouTube for a playlist matching the given name and extract its tracks"""
        loop = asyncio.get_event_loop()
        
        def _search_youtube_playlist():
            try:
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'quiet': True,
                    'no_warnings': True,
                    'default_search': 'ytsearch',
                    'socket_timeout': 30,
                    'extract_flat': False,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # Search for the playlist on YouTube
                    search_query = f"ytsearch1:{playlist_name} playlist"
                    results = ydl.extract_info(search_query, download=False)
                    
                    if not results or not results.get('entries'):
                        logger.warning(f"No YouTube playlists found for '{playlist_name}'")
                        return []
                    
                    # Get the first result (should be a playlist or video)
                    first_result = results['entries'][0]
                    
                    # If it's a video, try to extract its playlist
                    if '_type' not in first_result or first_result.get('_type') != 'playlist':
                        logger.debug(f"YouTube search returned a video, not a playlist. Trying direct search...")
                        return []
                    
                    # Extract playlist tracks
                    playlist_url = first_result.get('webpage_url') or first_result.get('url')
                    if not playlist_url:
                        return []
                    
                    logger.info(f"Found YouTube playlist: {first_result.get('title')}")
                    
                    # Now fetch the full playlist
                    info = ydl.extract_info(playlist_url, download=False)
                    entries = info.get('entries', []) or []
                    
                    tracks = []
                    for i, entry in enumerate(entries):
                        if not entry or i >= limit:
                            break
                        
                        if entry.get('availability') == 'needs_auth':
                            logger.debug(f"Skipping private video in YouTube playlist")
                            continue
                        
                        tracks.append(
                            Track(
                                title=entry.get('title', 'Unknown'),
                                url=entry.get('webpage_url') or entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}",
                                duration=entry.get('duration', 0),
                                source='youtube',
                                artist=entry.get('uploader', 'Unknown'),
                                thumbnail=entry.get('thumbnail', ''),
                                platform_badge='🎥 YouTube (Playlist Fallback)',
                            )
                        )
                    
                    return tracks
            except Exception as e:
                logger.warning(f"YouTube playlist search failed for '{playlist_name}': {str(e)[:100]}")
                return []
        
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(None, _search_youtube_playlist),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            logger.warning(f"YouTube playlist search timed out for '{playlist_name}'")
            return []
    
    async def _fetch_playlist_tracks_via_api(self, playlist_id: str, limit: int = 100) -> List[Track]:
        """Attempt to fetch playlist tracks via direct HTTP calls to Spotify API
        
        This tries alternative approaches when spotipy fails with 403:
        1. Fetch playlist metadata (might contain track preview)
        2. Try market-specific or alternative requests
        3. Check if any track info is available in the response
        """
        try:
            token = await self._get_access_token()
            if not token:
                logger.debug("No token available for alternative API fetch")
                return []
            
            headers = {'Authorization': f'Bearer {token}'}
            
            # Try to get basic playlist info first (might have track preview)
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(
                        f'https://api.spotify.com/v1/playlists/{playlist_id}',
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            tracks_info = data.get('tracks', {})
                            logger.debug(f"Playlist metadata: {tracks_info.get('total', 0)} total tracks")
                        elif resp.status == 403:
                            logger.debug("Playlist metadata also restricted (403)")
                            return []
                except Exception as e:
                    logger.debug(f"Failed to fetch playlist metadata: {e}")
                    return []
                
                # Try fetching tracks with various parameters that might bypass restrictions
                tracks = []
                offset = 0
                page_size = min(50, limit)
                
                while len(tracks) < limit:
                    params = {
                        'limit': min(page_size, limit - len(tracks)),
                        'offset': offset,
                        'fields': 'items(track(name,id,duration_ms,external_urls,artists(name),album(images))),next',
                    }
                    
                    try:
                        async with session.get(
                            f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks',
                            headers=headers,
                            params=params,
                            timeout=aiohttp.ClientTimeout(total=10)
                        ) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                items = data.get('items', [])
                                
                                if not items:
                                    break
                                
                                for item in items:
                                    track_data = item.get('track') or {}
                                    if not track_data or not track_data.get('id'):
                                        continue
                                    
                                    tracks.append(
                                        Track(
                                            title=track_data.get('name', 'Unknown'),
                                            url=track_data.get('external_urls', {}).get('spotify', 
                                                  f"https://open.spotify.com/track/{track_data['id']}"),
                                            duration=track_data.get('duration_ms', 0) // 1000,
                                            source='spotify',
                                            artist=', '.join([a['name'] for a in track_data.get('artists', [])]),
                                            thumbnail=track_data.get('album', {}).get('images', [{}])[0].get('url', ''),
                                            platform_badge='🎵 Spotify',
                                        )
                                    )
                                
                                if not data.get('next') or len(tracks) >= limit:
                                    break
                                offset += len(items)
                            elif resp.status == 403:
                                logger.debug(f"Tracks endpoint returned 403 at offset {offset}")
                                break
                            else:
                                logger.debug(f"Tracks endpoint returned {resp.status}")
                                break
                    except asyncio.TimeoutError:
                        logger.warning("Timeout fetching playlist tracks via API")
                        break
                    except Exception as e:
                        logger.debug(f"Error fetching playlist tracks: {str(e)[:100]}")
                        break
                
                if tracks:
                    logger.info(f"Successfully fetched {len(tracks)} tracks via alternative API method")
                    return tracks
                else:
                    logger.debug("Alternative API method returned no tracks")
                    return []
        
        except Exception as e:
            logger.debug(f"Alternative API fetch failed: {str(e)[:100]}")
            return []

    async def get_album_tracks(self, spotify_url: str, limit: int = 100) -> List[Track]:
        """Extract track metadata from a Spotify album link"""
        resource_type, album_id = self._parse_spotify_url(spotify_url)
        if resource_type != "album" or not album_id:
            return []

        client = self._get_spotipy_client()
        if client is not None:
            try:
                album = client.album(album_id)
                album_images = album.get('images', [])
                album_thumbnail = album_images[0].get('url', '') if album_images else ''
                tracks: List[Track] = []
                offset = 0
                while len(tracks) < limit:
                    page = client.album_tracks(album_id, limit=min(50, limit - len(tracks)), offset=offset)
                    items = page.get('items', []) or []
                    if not items:
                        break

                    for item in items:
                        track_url = item.get('external_urls', {}).get('spotify')
                        if not track_url and item.get('id'):
                            track_url = f"https://open.spotify.com/track/{item['id']}"

                        tracks.append(
                            Track(
                                title=item.get('name', 'Unknown'),
                                url=track_url or spotify_url,
                                duration=item.get('duration_ms', 0) // 1000,
                                source='spotify',
                                artist=', '.join([artist['name'] for artist in item.get('artists', [])]),
                                thumbnail=album_thumbnail,
                                platform_badge='🎵 Spotify',
                            )
                        )

                    if not page.get('next'):
                        break
                    offset += len(items)

                return tracks
            except Exception as e:
                logger.warning(f"spotipy album lookup failed for {spotify_url}: {e}")

        token = await self._get_access_token()
        if not token:
            return []

        headers = {
            'Authorization': f'Bearer {token}',
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f'https://api.spotify.com/v1/albums/{album_id}',
                headers=headers,
            ) as resp:
                if resp.status != 200:
                    return []

                data = await resp.json()
                album_images = data.get('images', [])
                album_thumbnail = album_images[0].get('url', '') if album_images else ''

                tracks: List[Track] = []
                for item in data.get('tracks', {}).get('items', []):
                    if len(tracks) >= limit:
                        break

                    track_url = item.get('external_urls', {}).get('spotify')
                    if not track_url and item.get('id'):
                        track_url = f"https://open.spotify.com/track/{item['id']}"

                    tracks.append(
                        Track(
                            title=item.get('name', 'Unknown'),
                            url=track_url or spotify_url,
                            duration=item.get('duration_ms', 0) // 1000,
                            source='spotify',
                            artist=', '.join([artist['name'] for artist in item.get('artists', [])]),
                            thumbnail=album_thumbnail,
                            platform_badge='🎵 Spotify',
                        )
                    )

                return tracks

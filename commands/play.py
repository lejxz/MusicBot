"""
Play command - Core playback command with source selection and cover filtering
"""
import discord
import logging
from typing import Optional, List
from urllib.parse import urlparse

from config import Config
from src.embeds import MusicEmbedManager
from src.queue import Track


logger = logging.getLogger(__name__)


class PlayCommand:
    """Play command handler"""

    MAX_SPOTIFY_IMPORT_TRACKS = 50

    @staticmethod
    def _is_spotify_url(url: str) -> bool:
        """Check if URL is a Spotify link"""
        return "spotify.com" in url.lower() or "spotify:" in url.lower()

    @staticmethod
    def _is_youtube_url(url: str) -> bool:
        """Check if URL is a YouTube or YouTube Music link"""
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
    def _get_spotify_resource_type(url: str) -> Optional[str]:
        """Extract Spotify resource type from URL
        
        Returns: 'track', 'album', 'playlist', or None
        """
        try:
            # Format: https://open.spotify.com/[type]/[id]?...
            # or: spotify:[type]:[id]
            
            if "spotify:" in url.lower():
                parts = url.split(":")
                if len(parts) >= 2:
                    return parts[1]  # track, album, playlist, etc.
            else:
                # https format
                path = urlparse(url).path
                parts = [p for p in path.split("/") if p and not p.startswith("intl-")]
                if len(parts) >= 1:
                    resource_type = parts[0]
                    if resource_type in ["track", "album", "playlist"]:
                        return resource_type
        except Exception as e:
            logger.debug(f"Could not parse Spotify URL: {e}")
        
        return None

    # Title keywords that signal a non-"official audio" variant. Penalized when the
    # user did NOT ask for them; boosted when they DID (intent-aware, see _score_track).
    VARIANT_KEYWORDS = (
        "live", "cover", "remix", "sped up", "speed up", "8-bit", "8bit",
        "reaction", "karaoke", "instrumental", "lyric", "music video",
        "trailer", "teaser", "snippet", "1 hour", "loop", "nightcore",
        "slowed", "reverb", "mv",
        # dance/performance-video channels — 4K clips, not audio, often unplayable
        "studio choom", "dance practice", "performance video", "focus cam",
        "fancam", "focused", "4k",
    )

    @staticmethod
    async def _resolve_youtube_audio(music_player, title: str, artist: str, target_duration: int = 0) -> Optional[Track]:
        """Resolve metadata to the best playable YouTube audio track."""
        search_terms = [title.strip()]
        if artist and artist.strip().lower() not in {"unknown", "none"}:
            search_terms.append(artist.strip())
        search_query = " ".join(term for term in search_terms if term)

        ranked = await PlayCommand._search_and_rank(music_player, search_query, artist, target_duration)
        return ranked[0] if ranked else None

    @staticmethod
    async def _search_and_rank(
        music_player, query: str, target_artist: str, target_duration: int = 0
    ) -> List[Track]:
        """Search YouTube Music + regular YouTube, merge, rank best-audio-first.

        Never returns empty when any result exists: worst case the least-bad
        (least-negative) track is still returned. That is the fallback.
        """
        music = await music_player.youtube.search(query, limit=5, source="youtube_music")
        regular = await music_player.youtube.search(query, limit=5, source="youtube")

        # Merge, dedup by url (music + regular overlap on the same video id)
        seen = set()
        merged = []
        for track in list(music) + list(regular):
            if track.url in seen:
                continue
            seen.add(track.url)
            merged.append(track)

        if not merged:
            return []

        scored = [
            (PlayCommand._score_track(t, query, target_artist, target_duration), t)
            for t in merged
        ]
        # Sort by score desc; tie-break shorter duration first (audio < music video)
        scored.sort(key=lambda st: (st[0], -(st[1].duration or 10**9)), reverse=True)
        logger.info("Ranked '%s': top=%s (score=%d)", query, scored[0][1].title, scored[0][0])
        return [t for _, t in scored]

    @staticmethod
    def _score_track(track: Track, query: str, target_artist: str, target_duration: int = 0) -> int:
        """Score a YouTube result. Higher = better 'official audio' match.

        Tiers: Artist - Topic > Official Audio > artist's own channel > other.
        Variant keywords (live/nightcore/etc) penalize UNLESS the query asked
        for them, in which case they boost instead. Never rejects — always scorable.
        """
        title = (track.title or "").lower()
        uploader = (track.artist or "").lower().strip()
        query_l = (query or "").lower()
        artist_l = (target_artist or "").lower().strip()

        score = 0

        # --- Source tier ---
        if uploader.endswith("- topic"):
            score += 2000  # YT Music auto-audio: clean, no video, always playable — win decisively
        elif "official audio" in title:
            score += 800
        elif artist_l and (uploader == artist_l or artist_l in uploader):
            score += 600  # artist's own channel
        # else: +0

        if "official" in title or "official" in uploader:
            score += 100

        # --- Intent-aware variant keywords ---
        for kw in PlayCommand.VARIANT_KEYWORDS:
            in_query = kw in query_l
            in_title = kw in title
            if in_query:
                # User explicitly asked for this variant → it must beat the source-tier
                # bonus, so reward matches hard and penalize the wrong variant hard.
                score += 1200 if in_title else -600
            elif in_title:
                score -= 500  # unwanted variant (music video, lyric, live, ...)

        # --- Duration sanity (only when we know the target length, e.g. from Spotify) ---
        if target_duration and track.duration:
            delta = abs(track.duration - target_duration)
            if delta <= 15:
                score += 200
            elif track.duration > 2 * target_duration:
                score -= 400  # extended / "1 hour" / wrong track

        return score

    @staticmethod
    def _merge_resolved(track: Track, yt_track: Track) -> None:
        """Merge resolved YouTube track data into the Spotify track."""
        track.url = yt_track.url
        track.source = yt_track.source
        if yt_track.thumbnail:
            track.thumbnail = yt_track.thumbnail
        # ponytail: adopt youtube duration if spotify missed it
        if not track.duration and yt_track.duration:
            track.duration = yt_track.duration

    @staticmethod
    async def play(
        interaction: discord.Interaction, 
        query: str, 
        music_player,
        source: Optional[str] = None
    ):
        """
        Play a track from YouTube or Spotify
        
        Args:
            interaction: Discord interaction
            query: Song name, artist, YouTube URL, or Spotify link
            music_player: MusicPlayer instance
            source: Optional source preference ('youtube', 'spotify', or None for auto)
        """
        await interaction.response.defer()
        logger.info("/play invoked by %s in guild %s with source=%s: %s", 
                    interaction.user, interaction.guild_id, source, query)

        try:
            # Check if user is in a voice channel
            if not interaction.user.voice:
                embed = MusicEmbedManager.create_error_embed(
                    "You must be in a voice channel to play music"
                )
                await interaction.followup.send(embed=embed)
                return

            player = music_player.get_player(interaction.guild_id)
            player.set_notification_channel(interaction.channel)

            # Connect to voice channel if not already connected
            if not player.voice_client:
                try:
                    player.voice_client = await interaction.user.voice.channel.connect(self_deaf=True)
                    logger.info("Connected to voice channel %s in guild %s", interaction.user.voice.channel, interaction.guild_id)
                except Exception as e:
                    logger.exception("Failed to join voice channel")
                    embed = MusicEmbedManager.create_error_embed(
                        f"Failed to join voice channel: {str(e)}"
                    )
                    await interaction.followup.send(embed=embed)
                    return

            # Determine if it's a URL or search query
            is_spotify = PlayCommand._is_spotify_url(query)
            is_youtube = PlayCommand._is_youtube_url(query)
            
            if is_spotify:
                # Handle Spotify URL
                resource_type = PlayCommand._get_spotify_resource_type(query)
                logger.info(f"Detected Spotify {resource_type} URL: {query[:50]}")
                
                if resource_type == "playlist":
                    tracks = await music_player.spotify.get_playlist_tracks(
                        query,
                        limit=PlayCommand.MAX_SPOTIFY_IMPORT_TRACKS,
                    )
                    if not tracks:
                        embed = MusicEmbedManager.create_error_embed("Could not load Spotify playlist")
                        await interaction.followup.send(embed=embed)
                        return

                    resolved_tracks = []
                    for track in tracks:
                        yt_track = await PlayCommand._resolve_youtube_audio(music_player, track.title, track.artist, track.duration or 0)
                        if yt_track:
                            PlayCommand._merge_resolved(track, yt_track)
                            resolved_tracks.append(track)

                    if not resolved_tracks:
                        embed = MusicEmbedManager.create_error_embed("Could not resolve playable tracks from Spotify playlist")
                        await interaction.followup.send(embed=embed)
                        return

                    await player.queue.add_multiple(resolved_tracks)
                    if not player.is_playing:
                        try:
                            await player.play_next()
                        except Exception as e:
                            logger.exception("Failed to start playback")
                            embed = MusicEmbedManager.create_error_embed(f"Could not start playback: {str(e)}")
                            await interaction.followup.send(embed=embed)
                            return

                    embed = MusicEmbedManager.create_info_embed(
                        "✅ Playlist Added",
                        f"Added **{len(resolved_tracks)}** tracks from the Spotify playlist"
                    )
                    await interaction.followup.send(embed=embed)

                elif resource_type == "album":
                    tracks = await music_player.spotify.get_album_tracks(
                        query,
                        limit=PlayCommand.MAX_SPOTIFY_IMPORT_TRACKS,
                    )
                    if not tracks:
                        embed = MusicEmbedManager.create_error_embed("Could not load Spotify album")
                        await interaction.followup.send(embed=embed)
                        return

                    resolved_tracks = []
                    for track in tracks:
                        yt_track = await PlayCommand._resolve_youtube_audio(music_player, track.title, track.artist, track.duration or 0)
                        if yt_track:
                            PlayCommand._merge_resolved(track, yt_track)
                            resolved_tracks.append(track)

                    if not resolved_tracks:
                        embed = MusicEmbedManager.create_error_embed("Could not resolve playable tracks from Spotify album")
                        await interaction.followup.send(embed=embed)
                        return

                    await player.queue.add_multiple(resolved_tracks)
                    if not player.is_playing:
                        try:
                            await player.play_next()
                        except Exception as e:
                            logger.exception("Failed to start playback")
                            embed = MusicEmbedManager.create_error_embed(f"Could not start playback: {str(e)}")
                            await interaction.followup.send(embed=embed)
                            return

                    embed = MusicEmbedManager.create_info_embed(
                        "✅ Album Added",
                        f"Added **{len(resolved_tracks)}** tracks from the Spotify album"
                    )
                    await interaction.followup.send(embed=embed)

                else:
                    # Track or unknown type
                    track = await music_player.spotify.get_track_info(query)
                    if track:
                        # ponytail: resolve before queueing, pass duration, abort if fail
                        yt_track = await PlayCommand._resolve_youtube_audio(
                            music_player, track.title, track.artist, track.duration or 0
                        )
                        if not yt_track:
                            embed = MusicEmbedManager.create_error_embed("Could not resolve playable track from Spotify")
                            await interaction.followup.send(embed=embed)
                            return

                        PlayCommand._merge_resolved(track, yt_track)

                        await player.queue.add(track)

                        if not player.is_playing:
                            try:
                                await player.play_next()
                            except Exception as e:
                                logger.exception("Failed to start playback")
                                embed = MusicEmbedManager.create_error_embed(f"Could not start playback: {str(e)}")
                                await interaction.followup.send(embed=embed)
                                return

                        embed = MusicEmbedManager.create_info_embed(
                            "✅ Added to Queue",
                            f"**{track.title}**\nby *{track.artist}*"
                        )
                        if track.thumbnail:
                            embed.set_thumbnail(url=track.thumbnail)
                        await interaction.followup.send(embed=embed)
                    else:
                        embed = MusicEmbedManager.create_error_embed("Could not find Spotify track")
                        await interaction.followup.send(embed=embed)

            elif is_youtube:
                # YouTube URL: handle YouTube and YouTube Music links
                logger.info(f"Detected YouTube URL: {query[:50]}")
                
                # Check if it's a playlist
                if "list=" in query or "/playlist/" in query.lower():
                    tracks = await music_player.youtube.get_playlist_tracks(query)
                    if not tracks:
                        embed = MusicEmbedManager.create_error_embed("Could not load YouTube playlist")
                        await interaction.followup.send(embed=embed)
                        return

                    await player.queue.add_multiple(tracks)

                    if not player.is_playing:
                        try:
                            await player.play_next()
                        except Exception as e:
                            logger.exception("Failed to start playback")
                            embed = MusicEmbedManager.create_error_embed(f"Could not start playback: {str(e)}")
                            await interaction.followup.send(embed=embed)
                            return

                    embed = MusicEmbedManager.create_info_embed(
                        "✅ Playlist Added",
                        f"Added **{len(tracks)}** tracks from the YouTube playlist"
                    )
                    await interaction.followup.send(embed=embed)
                else:
                    # Single video/song: let the provider resolve any YouTube-family URL directly.
                    track = await music_player.youtube.search(query, limit=1)
                    
                    if not track:
                        embed = MusicEmbedManager.create_error_embed("Could not load YouTube track")
                        await interaction.followup.send(embed=embed)
                        return

                    await player.queue.add(track[0])

                    if not player.is_playing:
                        try:
                            await player.play_next()
                        except Exception as e:
                            logger.exception("Failed to start playback")
                            embed = MusicEmbedManager.create_error_embed(f"Could not start playback: {str(e)}")
                            await interaction.followup.send(embed=embed)
                            return

                    embed = MusicEmbedManager.create_info_embed(
                        "✅ Added to Queue",
                        f"**{track[0].title}**\nby *{track[0].artist}*"
                    )
                    if track[0].thumbnail:
                        embed.set_thumbnail(url=track[0].thumbnail)
                    await interaction.followup.send(embed=embed)

            else:
                # Search query: use source preference or hybrid approach
                track = None

                # Try primary source first
                if source == 'spotify' or (source is None and Config.PRIMARY_SOURCE == "spotify"):
                    spotify_results = await music_player.spotify.search(query, limit=3)
                    if spotify_results:
                        spotify_track = spotify_results[0]
                        yt_track = await PlayCommand._resolve_youtube_audio(
                            music_player,
                            spotify_track.title,
                            spotify_track.artist,
                        )
                        if yt_track:
                            yt_track.title = spotify_track.title
                            yt_track.artist = spotify_track.artist
                            yt_track.thumbnail = spotify_track.thumbnail or yt_track.thumbnail
                            track = yt_track
                            logger.info(f"Using Spotify metadata + YouTube audio: {track.title}")

                if track is None and source != 'spotify':
                    # YouTube search: rank music + regular results, best audio first
                    artist_from_query = query.split(' - ')[0] if ' - ' in query else query.split(' by ')[0]
                    ranked = await PlayCommand._search_and_rank(music_player, query, artist_from_query)
                    if ranked:
                        track = ranked[0]
                        logger.info(f"Found YouTube track: {track.title}")

                if track is None:
                    embed = MusicEmbedManager.create_error_embed("No results found")
                    await interaction.followup.send(embed=embed)
                    return

                # Add top result to queue
                await player.queue.add(track)
                logger.info("Queued track in guild %s: %s - %s", interaction.guild_id, track.artist, track.title)

                if not player.is_playing:
                    try:
                        await player.play_next()
                    except Exception as e:
                        logger.exception("Failed to start playback")
                        embed = MusicEmbedManager.create_error_embed(f"Could not start playback: {str(e)}")
                        await interaction.followup.send(embed=embed)
                        return

                embed = MusicEmbedManager.create_info_embed(
                    "✅ Added to Queue",
                    f"**{track.title}**\nby *{track.artist}*"
                )
                if track.thumbnail:
                    embed.set_thumbnail(url=track.thumbnail)
                await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.exception("/play failed")
            embed = MusicEmbedManager.create_error_embed(f"Error: {str(e)}")
            await interaction.followup.send(embed=embed)

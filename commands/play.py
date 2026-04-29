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

    @staticmethod
    async def _resolve_youtube_audio(music_player, title: str, artist: str) -> Optional[Track]:
        """Resolve metadata to the best playable YouTube audio track."""
        search_terms = [title.strip()]
        if artist and artist.strip().lower() not in {"unknown", "none"}:
            search_terms.append(artist.strip())
        search_query = " ".join(term for term in search_terms if term)

        yt_results = await music_player.youtube.search(search_query, limit=5, source="youtube_music")
        if not yt_results:
            yt_results = await music_player.youtube.search(search_query, limit=5, source="youtube")

        if not yt_results:
            return None

        filtered = PlayCommand._filter_covers(yt_results, artist)
        return filtered[0] if filtered else yt_results[0]

    @staticmethod
    def _filter_covers(tracks: List[Track], target_artist: str) -> List[Track]:
        """Filter tracks to prefer originals over covers
        
        Returns tracks where uploader/artist name closely matches target artist
        """
        if not tracks or not target_artist:
            return tracks
        
        target_artist_lower = target_artist.lower().strip()
        
        # Score tracks based on artist match
        scored_tracks = []
        for track in tracks:
            uploader = track.artist.lower().strip()
            
            # Exact match or official channel keywords
            if (uploader == target_artist_lower or 
                'official' in uploader or
                f"- {target_artist_lower}" in uploader.lower() or
                target_artist_lower in uploader):
                score = 100
            else:
                # Partial match
                score = 50 if any(word in uploader for word in target_artist_lower.split()) else 0
            
            scored_tracks.append((score, track))
        
        # Sort by score (descending) and return tracks
        scored_tracks.sort(key=lambda x: x[0], reverse=True)
        
        # If top scorer has good confidence (100), only return those
        if scored_tracks and scored_tracks[0][0] >= 100:
            return [t for s, t in scored_tracks if s >= 100]
        
        # Otherwise return top 3
        return [t for _, t in scored_tracks[:3]]

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
                        yt_track = await PlayCommand._resolve_youtube_audio(music_player, track.title, track.artist)
                        if yt_track:
                            track.url = yt_track.url
                            track.source = yt_track.source
                            if yt_track.thumbnail:
                                track.thumbnail = yt_track.thumbnail
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
                        yt_track = await PlayCommand._resolve_youtube_audio(music_player, track.title, track.artist)
                        if yt_track:
                            track.url = yt_track.url
                            track.source = yt_track.source
                            if yt_track.thumbnail:
                                track.thumbnail = yt_track.thumbnail
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
                        await player.queue.add(track)
                        # Search YouTube for the audio
                        yt_results = await music_player.youtube.search(f"{track.title} {track.artist}")
                        if yt_results:
                            yt_track = yt_results[0]
                            track.url = yt_track.url

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
                    # YouTube search or fallback
                    yt_results = await music_player.youtube.search(query, limit=5, source='youtube')
                    if yt_results:
                        # Filter to prefer originals
                        artist_from_query = query.split(' - ')[0] if ' - ' in query else query.split(' by ')[0]
                        filtered = PlayCommand._filter_covers(yt_results, artist_from_query)
                        track = filtered[0] if filtered else yt_results[0]
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

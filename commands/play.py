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
    async def _ensure_voice_connection(interaction, player) -> bool:
        """Ensure the bot is connected to the user's voice channel."""
        if not interaction.user.voice:
            embed = MusicEmbedManager.create_error_embed(
                "You must be in a voice channel to play music"
            )
            await interaction.followup.send(embed=embed)
            return False

        player.set_notification_channel(interaction.channel)

        if player.voice_client:
            return True

        try:
            player.voice_client = await interaction.user.voice.channel.connect(self_deaf=True)
            logger.info("Connected to voice channel %s in guild %s", interaction.user.voice.channel, interaction.guild_id)
            return True
        except Exception as e:
            logger.exception("Failed to join voice channel")
            embed = MusicEmbedManager.create_error_embed(
                f"Failed to join voice channel: {str(e)}"
            )
            await interaction.followup.send(embed=embed)
            return False

    @staticmethod
    async def _enqueue_tracks(player, tracks: List[Track], *, front: bool = False) -> None:
        """Queue tracks, optionally inserting them at the front."""
        if not tracks:
            return

        if len(tracks) == 1:
            track = tracks[0]
            if front:
                await player.queue.add_front(track)
            else:
                await player.queue.add(track)
            return

        if front:
            for track in reversed(tracks):
                await player.queue.add_front(track)
        else:
            await player.queue.add_multiple(tracks)

    @staticmethod
    async def _start_playback_if_needed(player, interaction, *, error_message: str = "Could not start playback") -> bool:
        """Start playback when the queue is idle."""
        if player.is_playing:
            return True

        try:
            await player.play_next()
            return True
        except Exception as e:
            logger.exception("Failed to start playback")
            embed = MusicEmbedManager.create_error_embed(f"{error_message}: {str(e)}")
            await interaction.followup.send(embed=embed)
            return False

    @staticmethod
    async def _resolve_spotify_tracks(music_player, query: str) -> List[Track]:
        """Resolve Spotify playlists/albums/tracks into playable Track objects."""
        resource_type = PlayCommand._get_spotify_resource_type(query)
        logger.info("Detected Spotify %s URL: %s", resource_type or "track", query[:50])

        if resource_type == "playlist":
            tracks = await music_player.spotify.get_playlist_tracks(query, limit=PlayCommand.MAX_SPOTIFY_IMPORT_TRACKS)
            if not tracks:
                return []
            resolved_tracks = []
            for track in tracks:
                yt_track = await PlayCommand._resolve_youtube_audio(music_player, track.title, track.artist, track.duration or 0)
                if yt_track:
                    PlayCommand._merge_resolved(track, yt_track)
                    resolved_tracks.append(track)
            return resolved_tracks

        if resource_type == "album":
            tracks = await music_player.spotify.get_album_tracks(query, limit=PlayCommand.MAX_SPOTIFY_IMPORT_TRACKS)
            if not tracks:
                return []
            resolved_tracks = []
            for track in tracks:
                yt_track = await PlayCommand._resolve_youtube_audio(music_player, track.title, track.artist, track.duration or 0)
                if yt_track:
                    PlayCommand._merge_resolved(track, yt_track)
                    resolved_tracks.append(track)
            return resolved_tracks

        track = await music_player.spotify.get_track_info(query)
        if not track:
            return []

        yt_track = await PlayCommand._resolve_youtube_audio(music_player, track.title, track.artist, track.duration or 0)
        if not yt_track:
            return []

        PlayCommand._merge_resolved(track, yt_track)
        return [track]

    @staticmethod
    async def _resolve_youtube_tracks(music_player, query: str) -> List[Track]:
        """Resolve YouTube URL or search query into track objects."""
        if "list=" in query or "/playlist/" in query.lower():
            tracks = await music_player.youtube.get_playlist_tracks(query)
            return tracks or []

        track = await music_player.youtube.search(query, limit=1)
        return track or []

    @staticmethod
    async def _resolve_search_track(music_player, query: str, source: Optional[str]) -> Optional[Track]:
        """Resolve a general search query to a single playable track."""
        track = None

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
                    logger.info("Using Spotify metadata + YouTube audio: %s", track.title)

        if track is None and source != 'spotify':
            artist_from_query = query.split(' - ')[0] if ' - ' in query else query.split(' by ')[0]
            ranked = await PlayCommand._search_and_rank(music_player, query, artist_from_query)
            if ranked:
                track = ranked[0]
                logger.info("Found YouTube track: %s", track.title)

        return track

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
            player = music_player.get_player(interaction.guild_id)
            if not await PlayCommand._ensure_voice_connection(interaction, player):
                return

            is_spotify = PlayCommand._is_spotify_url(query)
            is_youtube = PlayCommand._is_youtube_url(query)

            if is_spotify:
                resolved_tracks = await PlayCommand._resolve_spotify_tracks(music_player, query)
                if not resolved_tracks:
                    embed = MusicEmbedManager.create_error_embed("Could not resolve playable track from Spotify")
                    await interaction.followup.send(embed=embed)
                    return

                if len(resolved_tracks) > 1:
                    await PlayCommand._enqueue_tracks(player, resolved_tracks)
                    if not await PlayCommand._start_playback_if_needed(player, interaction):
                        return

                    embed = MusicEmbedManager.create_info_embed(
                        "✅ Playlist Added",
                        f"Added **{len(resolved_tracks)}** tracks from the Spotify source"
                    )
                    await interaction.followup.send(embed=embed)
                    return

                await PlayCommand._enqueue_tracks(player, resolved_tracks)
                if not await PlayCommand._start_playback_if_needed(player, interaction):
                    return

                track = resolved_tracks[0]
                embed = MusicEmbedManager.create_info_embed(
                    "✅ Added to Queue",
                    f"**{track.title}**\nby *{track.artist}*"
                )
                if track.thumbnail:
                    embed.set_thumbnail(url=track.thumbnail)
                await interaction.followup.send(embed=embed)
                return

            if is_youtube:
                resolved_tracks = await PlayCommand._resolve_youtube_tracks(music_player, query)
                if not resolved_tracks:
                    embed = MusicEmbedManager.create_error_embed("Could not load YouTube track")
                    await interaction.followup.send(embed=embed)
                    return

                if "list=" in query or "/playlist/" in query.lower():
                    await PlayCommand._enqueue_tracks(player, resolved_tracks)
                    if not await PlayCommand._start_playback_if_needed(player, interaction):
                        return

                    embed = MusicEmbedManager.create_info_embed(
                        "✅ Playlist Added",
                        f"Added **{len(resolved_tracks)}** tracks from the YouTube playlist"
                    )
                    await interaction.followup.send(embed=embed)
                    return

                await PlayCommand._enqueue_tracks(player, resolved_tracks)
                if not await PlayCommand._start_playback_if_needed(player, interaction):
                    return

                track = resolved_tracks[0]
                embed = MusicEmbedManager.create_info_embed(
                    "✅ Added to Queue",
                    f"**{track.title}**\nby *{track.artist}*"
                )
                if track.thumbnail:
                    embed.set_thumbnail(url=track.thumbnail)
                await interaction.followup.send(embed=embed)
                return

            track = await PlayCommand._resolve_search_track(music_player, query, source)
            if track is None:
                embed = MusicEmbedManager.create_error_embed("No results found")
                await interaction.followup.send(embed=embed)
                return

            await PlayCommand._enqueue_tracks(player, [track])
            if not await PlayCommand._start_playback_if_needed(player, interaction):
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

    @staticmethod
    async def playnext(
        interaction: discord.Interaction,
        query: str,
        music_player,
        source: Optional[str] = None
    ):
        """Insert a track at the front of the queue and start playback if needed."""
        await interaction.response.defer()
        logger.info("/playnext invoked by %s in guild %s with source=%s: %s",
                    interaction.user, interaction.guild_id, source, query)

        try:
            player = music_player.get_player(interaction.guild_id)
            if not await PlayCommand._ensure_voice_connection(interaction, player):
                return

            is_spotify = PlayCommand._is_spotify_url(query)
            is_youtube = PlayCommand._is_youtube_url(query)

            if is_spotify:
                resolved_tracks = await PlayCommand._resolve_spotify_tracks(music_player, query)
                if not resolved_tracks:
                    embed = MusicEmbedManager.create_error_embed("Could not resolve playable track from Spotify")
                    await interaction.followup.send(embed=embed)
                    return

                await PlayCommand._enqueue_tracks(player, resolved_tracks, front=True)
                if not await PlayCommand._start_playback_if_needed(player, interaction):
                    return

                embed = MusicEmbedManager.create_info_embed(
                    "✅ Added to Front of Queue",
                    f"Inserted **{len(resolved_tracks)}** track(s) at the front of the queue"
                )
                await interaction.followup.send(embed=embed)
                return

            if is_youtube:
                resolved_tracks = await PlayCommand._resolve_youtube_tracks(music_player, query)
                if not resolved_tracks:
                    embed = MusicEmbedManager.create_error_embed("Could not load YouTube track")
                    await interaction.followup.send(embed=embed)
                    return

                await PlayCommand._enqueue_tracks(player, resolved_tracks, front=True)
                if not await PlayCommand._start_playback_if_needed(player, interaction):
                    return

                embed = MusicEmbedManager.create_info_embed(
                    "✅ Added to Front of Queue",
                    f"Inserted **{len(resolved_tracks)}** track(s) at the front of the queue"
                )
                await interaction.followup.send(embed=embed)
                return

            track = await PlayCommand._resolve_search_track(music_player, query, source)
            if track is None:
                embed = MusicEmbedManager.create_error_embed("No results found")
                await interaction.followup.send(embed=embed)
                return

            await PlayCommand._enqueue_tracks(player, [track], front=True)
            if not await PlayCommand._start_playback_if_needed(player, interaction):
                return

            embed = MusicEmbedManager.create_info_embed(
                "✅ Added to Front of Queue",
                f"**{track.title}**\nby *{track.artist}*"
            )
            if track.thumbnail:
                embed.set_thumbnail(url=track.thumbnail)
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.exception("/playnext failed")
            embed = MusicEmbedManager.create_error_embed(f"Error: {str(e)}")
            await interaction.followup.send(embed=embed)

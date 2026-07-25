"""
Core music player service
"""
import discord
import asyncio
import logging
import shutil
import os
import sys
import subprocess
import functools
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Iterator
from .queue import Queue, Track
from .providers import YouTubeProvider, SpotifyProvider
from .cache import AudioCache
from config import Config


logger = logging.getLogger(__name__)


def _ffmpeg_log_has_403(path: str = "ffmpeg-stream.log", tail_bytes: int = 8192) -> bool:
    """Cheap check: did the last stream's ffmpeg stderr mention a 403?
    Reads only the tail so it stays O(1) regardless of log size."""
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - tail_bytes))
            return b"403" in fh.read()
    except Exception:
        return False


class PlaybackState(str, Enum):
    IDLE = "idle"
    PREPARING = "preparing"
    PLAYING = "playing"
    PAUSED = "paused"
    RECOVERING = "recovering"
    STOPPING = "stopping"


@dataclass(frozen=True)
class PlaybackSnapshot:
    state: PlaybackState
    track: Optional[Track]
    queue_size: int
    loop_mode: int
    position: float = 0.0

    @property
    def is_playing(self) -> bool:
        return self.state in {
            PlaybackState.PREPARING,
            PlaybackState.PLAYING,
            PlaybackState.PAUSED,
            PlaybackState.RECOVERING,
        }

    @property
    def is_paused(self) -> bool:
        return self.state is PlaybackState.PAUSED


@dataclass(frozen=True)
class FFmpegCandidate:
    executable: str
    source: str
    bundled: bool = False


@dataclass(frozen=True)
class FFmpegResolution:
    executable: str
    source: str
    version: str


def _iter_ffmpeg_candidates() -> Iterator[FFmpegCandidate]:
    candidates: list[FFmpegCandidate] = []
    if Config.FFMPEG_EXECUTABLE:
        candidates.append(FFmpegCandidate(Config.FFMPEG_EXECUTABLE, "configured"))

    path_candidate = shutil.which("ffmpeg")
    if path_candidate:
        candidates.append(FFmpegCandidate(path_candidate, "path"))

    if sys.platform == "win32":
        local_app_data = os.getenv("LOCALAPPDATA")
        if local_app_data:
            winget_root = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
            if winget_root.exists():
                try:
                    candidates.extend(
                        FFmpegCandidate(str(path), "winget")
                        for path in winget_root.rglob("ffmpeg.exe")
                    )
                except Exception:
                    logger.debug("WinGet search failed", exc_info=True)
        candidates.extend(
            FFmpegCandidate(str(path), "program-files")
            for path in (
                Path(os.getenv("ProgramFiles", r"C:\Program Files")) / "ffmpeg" / "bin" / "ffmpeg.exe",
                Path(os.getenv("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "ffmpeg" / "bin" / "ffmpeg.exe",
            )
            if path.exists()
        )
    elif sys.platform.startswith("linux"):
        candidates.extend(
            FFmpegCandidate(str(path), "system-path")
            for path in (Path("/usr/local/bin/ffmpeg"), Path("/usr/bin/ffmpeg"))
            if path.exists()
        )

    try:
        import imageio_ffmpeg
        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled and Path(bundled).exists():
            if sys.platform.startswith("linux"):
                logger.warning(
                    "imageio-ffmpeg candidate (%s) is a last-resort fallback on Linux; system FFmpeg is strongly recommended",
                    bundled,
                )
            candidates.append(FFmpegCandidate(bundled, "imageio", bundled=True))
    except (ImportError, AttributeError, FileNotFoundError, RuntimeError, OSError):
        logger.debug("imageio-ffmpeg candidate is unavailable", exc_info=True)

    seen: set[str] = set()
    for candidate in candidates:
        try:
            key = os.path.normcase(os.path.abspath(candidate.executable))
        except Exception:
            key = candidate.executable
        if key not in seen:
            seen.add(key)
            yield candidate


def validate_ffmpeg_candidate(candidate: FFmpegCandidate) -> Optional[FFmpegResolution]:
    logger.debug("Validating FFmpeg candidate [%s]: %s", candidate.source, candidate.executable)
    try:
        version_result = subprocess.run(
            [candidate.executable, "-hide_banner", "-version"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
            check=False,
        )
        if version_result.returncode != 0:
            logger.warning(
                "FFmpeg candidate [%s] -version failed with returncode %s: %s",
                candidate.source,
                version_result.returncode,
                version_result.stderr.strip()[:200],
            )
            return None

        version_line = version_result.stdout.splitlines()[0] if version_result.stdout else "unknown"

        codec_result = subprocess.run(
            [
                candidate.executable,
                "-hide_banner",
                "-loglevel", "error",
                "-f", "lavfi",
                "-i", "anullsrc=r=48000:cl=stereo",
                "-t", "0.1",
                "-c:a", "libopus",
                "-f", "opus",
                "-",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
        if codec_result.returncode != 0:
            logger.warning(
                "FFmpeg candidate [%s] opus probe failed with returncode %s: %s",
                candidate.source,
                codec_result.returncode,
                codec_result.stderr.strip()[:200],
            )
            return None

        return FFmpegResolution(
            executable=candidate.executable,
            source=candidate.source,
            version=version_line,
        )
    except subprocess.TimeoutExpired:
        logger.warning("FFmpeg candidate [%s] timed out during validation", candidate.source)
        return None
    except (OSError, PermissionError) as e:
        logger.warning("FFmpeg candidate [%s] validation error: %s", candidate.source, e)
        return None
    except Exception as e:
        logger.warning("FFmpeg candidate [%s] unexpected validation failure: %s", candidate.source, e, exc_info=True)
        return None


@functools.lru_cache(maxsize=1)
def resolve_ffmpeg() -> Optional[FFmpegResolution]:
    """Deterministically resolve and validate an FFmpeg executable candidate."""
    for candidate in _iter_ffmpeg_candidates():
        res = validate_ffmpeg_candidate(candidate)
        if res is not None:
            return res
    return None


def find_ffmpeg_executable() -> Optional[str]:
    """Locate ffmpeg executable using deterministic resolution."""
    res = resolve_ffmpeg()
    return res.executable if res else None


class MusicPlayer:
    """Main music player service"""

    def __init__(self, bot):
        self.bot = bot
        self.queue = Queue()
        self.youtube = YouTubeProvider()
        self.spotify = SpotifyProvider(
            Config.SPOTIFY_CLIENT_ID,
            Config.SPOTIFY_CLIENT_SECRET
        )
        self.cache = AudioCache()

        # Per-guild players
        self.players: Dict[int, 'GuildPlayer'] = {}
        self.current_volume = Config.DEFAULT_VOLUME

    def get_player(self, guild_id: int) -> 'GuildPlayer':
        """Get or create player for guild"""
        if guild_id not in self.players:
            self.players[guild_id] = GuildPlayer(guild_id, self)
        return self.players[guild_id]

    async def search_youtube(self, query: str) -> list:
        """Search YouTube"""
        return await self.youtube.search(query, limit=5)

    async def search_spotify(self, query: str) -> list:
        """Search Spotify"""
        return await self.spotify.search(query, limit=5)

    async def play_youtube(self, url: str, ctx) -> Optional[Track]:
        """Play from YouTube URL"""
        player = self.get_player(ctx.guild.id)
        await player.queue.add(Track(
            title="Track",
            url=url,
            duration=0,
            source="youtube",
            artist="Unknown",
            added_by_id=ctx.author.id,
            added_by_name=ctx.author.name,
        ))
        return player.queue.tracks[-1] if player.queue.tracks else None

    async def set_volume(self, guild_id: int, volume: int) -> None:
        """Set player volume"""
        player = self.get_player(guild_id)
        player.volume = max(0, min(100, volume))

    async def cleanup(self, guild_id: int) -> None:
        """Cleanup player for guild"""
        if guild_id in self.players:
            del self.players[guild_id]


class GuildPlayer:
    """Per-guild music player"""

    def __init__(self, guild_id: int, music_player: MusicPlayer):
        self.guild_id = guild_id
        self.music_player = music_player
        self.queue = Queue()
        self.volume = Config.DEFAULT_VOLUME
        self.current_track: Optional[Track] = None
        self.voice_client: Optional[discord.VoiceClient] = None

        self._state = PlaybackState.IDLE
        self._state_lock = asyncio.Lock()
        self._advance_lock = asyncio.Lock()
        self._generation = 0
        self._notification_channel = None
        self._elapsed_before_pause: float = 0.0
        self._play_start_ts: Optional[float] = None

    @property
    def is_playing(self) -> bool:
        return self._state in {
            PlaybackState.PREPARING,
            PlaybackState.PLAYING,
            PlaybackState.PAUSED,
            PlaybackState.RECOVERING,
        }

    @property
    def is_paused(self) -> bool:
        return self._state is PlaybackState.PAUSED

    def set_notification_channel(self, channel) -> None:
        """Store the safe channel to post playback notifications."""
        self._notification_channel = channel

    async def snapshot(self) -> PlaybackSnapshot:
        """Return an atomic snapshot of current playback state."""
        async with self._state_lock:
            q_size = await self.queue.size()
            
            # ponytail: wall-clock position drifts on network stalls; upgrade path is FFmpeg -progress pipe
            dur = getattr(self.current_track, "duration", 0) or 0
            # RECOVERING still has audio flowing (reconnect), so the clock must keep running.
            # ponytail: no track == no position; avoids leaking a stale elapsed value after
            # the many stop/skip/idle paths that reset current_track without touching the clock.
            if self.current_track is None:
                pos = 0.0
            else:
                pos = self._elapsed_before_pause
                if self._play_start_ts is not None and self._state in {
                    PlaybackState.PLAYING,
                    PlaybackState.RECOVERING,
                }:
                    pos += time.monotonic() - self._play_start_ts


            if dur > 0:
                pos = min(pos, float(dur))
                
            return PlaybackSnapshot(
                state=self._state,
                track=self.current_track,
                queue_size=q_size,
                loop_mode=self.queue.loop_mode,
                position=pos,
            )

    async def play_next(self, skip_track_repeat: bool = False) -> None:
        """Play next track in queue with serialized, non-recursive recovery."""
        async with self._advance_lock:
            async with self._state_lock:
                if self._state in {
                    PlaybackState.PREPARING,
                    PlaybackState.PLAYING,
                    PlaybackState.PAUSED,
                    PlaybackState.STOPPING,
                }:
                    return

            self._generation += 1
            generation = self._generation

            initial_queue_size = await self.queue.size()
            max_attempts = max(1, initial_queue_size)
            attempts = 0
            failed_tracks: list[Track] = []

            while attempts < max_attempts:
                if generation != self._generation:
                    return

                should_skip_track_repeat = skip_track_repeat or len(failed_tracks) > 0
                next_track = await self.queue.get_next(skip_track_repeat=should_skip_track_repeat)

                if not next_track:
                    break

                attempts += 1

                async with self._state_lock:
                    if generation != self._generation:
                        return
                    self.current_track = next_track
                    self._state = PlaybackState.PREPARING

                logger.info("Guild %s preparing track (%s/%s): %s - %s",
                            self.guild_id, attempts, max_attempts, next_track.artist, next_track.title)

                if not self.voice_client:
                    logger.warning("Guild %s has no voice client while starting playback", self.guild_id)
                    async with self._state_lock:
                        if generation == self._generation:
                            self.current_track = None
                            self._state = PlaybackState.IDLE
                    return

                source = None
                try:
                    ffmpeg_path = find_ffmpeg_executable()
                    if not ffmpeg_path:
                        raise RuntimeError(
                            "FFmpeg is required for voice playback but was not found. "
                            "On Linux, install: sudo apt install ffmpeg libopus0"
                        )

                    stream_url = await self.music_player.youtube.get_stream_url(next_track.url)
                    if not stream_url:
                        raise RuntimeError(f"Could not resolve stream URL for {next_track.url}")

                    if generation != self._generation:
                        return

                    # ponytail: append-mode stderr log per process; ffmpeg's own
                    # reconnect/underrun/403 complaints land here for `grep`.
                    # Rotate manually if it grows; upgrade to logging handler if noisy.
                    ffmpeg_log = open("ffmpeg-stream.log", "a", buffering=1)
                    ffmpeg_log.write(
                        f"\n=== guild {self.guild_id} track '{next_track.title}' ===\n"
                    )
                    source = await discord.FFmpegOpusAudio.from_probe(
                        stream_url,
                        method="fallback",
                        before_options=(
                            "-reconnect 1 -reconnect_streamed 1 "
                            "-reconnect_on_network_error 1 -reconnect_on_http_error 4xx,5xx "
                            "-reconnect_delay_max 5 "
                            "-rw_timeout 15000000"
                        ),
                        executable=ffmpeg_path,
                        stderr=ffmpeg_log,
                    )
                    # ponytail: close the log fd when this source is cleaned up,
                    # else one fd leaks per track. Wrap the existing cleanup.
                    _orig_cleanup = source.cleanup
                    def _cleanup_with_log(_orig=_orig_cleanup, _fh=ffmpeg_log):
                        try:
                            _orig()
                        finally:
                            try:
                                _fh.close()
                            except Exception:
                                pass
                    source.cleanup = _cleanup_with_log
                except asyncio.CancelledError:
                    if source:
                        try:
                            source.cleanup()
                        except Exception:
                            pass
                    async with self._state_lock:
                        if generation == self._generation:
                            self.current_track = None
                            self._state = PlaybackState.IDLE
                    raise
                except Exception as e:
                    if source:
                        try:
                            source.cleanup()
                        except Exception:
                            pass
                    error_code = getattr(e, 'returncode', 'N/A')
                    logger.error(
                        "Guild %s failed to prepare '%s': %s (exit code: %s).",
                        self.guild_id, next_track.title, e, error_code, exc_info=True,
                    )
                    failed_tracks.append(next_track)
                    async with self._state_lock:
                        if generation == self._generation:
                            self._state = PlaybackState.RECOVERING
                    continue

                if generation != self._generation:
                    if source:
                        try:
                            source.cleanup()
                        except Exception:
                            pass
                    return

                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = getattr(getattr(self.music_player, "bot", None), "loop", asyncio.get_event_loop())

                def _after_playback(error: Optional[Exception]):
                    loop.call_soon_threadsafe(
                        lambda: loop.create_task(
                            self._finish_playback(generation, error)
                        )
                    )

                try:
                    self.voice_client.play(source, after=_after_playback)
                    from src import metrics
                    self._play_start_ts = time.monotonic()
                    self._elapsed_before_pause = 0.0
                    metrics.record("track_start", guild=self.guild_id,
                                   dur=getattr(next_track, "duration", 0))
                    async with self._state_lock:
                        if generation == self._generation:
                            self._state = PlaybackState.PLAYING

                    if failed_tracks:
                        try:
                            await self._notify_playback_failures(failed_tracks)
                        except Exception:
                            pass
                    return
                except Exception as e:
                    if source:
                        try:
                            source.cleanup()
                        except Exception:
                            pass
                    logger.error("Guild %s: Failed to start voice playback: %s", self.guild_id, e, exc_info=True)
                    failed_tracks.append(next_track)
                    async with self._state_lock:
                        if generation == self._generation:
                            self._state = PlaybackState.RECOVERING
                    continue

            # Queue finished or all attempts failed
            async with self._state_lock:
                if generation == self._generation:
                    self.current_track = None
                    self._state = PlaybackState.IDLE

            if failed_tracks:
                try:
                    await self._notify_playback_failures(failed_tracks)
                except Exception:
                    pass

    async def _finish_playback(self, generation: int, error: Optional[Exception]) -> None:
        """Handle end of playback on the asyncio event loop."""
        failed_track: Optional[Track] = None
        async with self._state_lock:
            if generation != self._generation:
                logger.debug("Guild %s ignoring stale playback completion for gen %s (current: %s)",
                             self.guild_id, generation, self._generation)
                return
            if self._state is PlaybackState.STOPPING or self._state is PlaybackState.IDLE:
                return

            if error:
                code = getattr(error, 'returncode', None)
                if code is not None:
                    if (os.name == 'posix' and sys.platform != 'win32') and (code == -11 or str(code) == '-11'):
                        error_code = f"{code} (SIGSEGV)"
                    else:
                        error_code = str(code)
                else:
                    error_code = 'N/A'

                exc_info = (type(error), error, error.__traceback__) if getattr(error, '__traceback__', None) else None
                logger.error(
                    "Guild %s runtime playback error: %s: %s (exit code: %s)",
                    self.guild_id, type(error).__name__, error, error_code, exc_info=exc_info,
                )
                from src import metrics
                metrics.record("track_error", guild=self.guild_id, code=error_code)
                if _ffmpeg_log_has_403():
                    metrics.record("stream_403", guild=self.guild_id)
                failed_track = self.current_track
                self._state = PlaybackState.RECOVERING
            else:
                track_title = self.current_track.title if self.current_track else 'unknown'
                logger.info("Guild %s finished track: %s", self.guild_id, track_title)
                from src import metrics
                metrics.record("track_ok", guild=self.guild_id)
                # Clean finish but well short of expected duration = silent gap.
                start = getattr(self, "_play_start_ts", None)
                dur = getattr(self.current_track, "duration", 0) or 0
                if start and dur > 0:
                    actual = time.monotonic() - start
                    if actual < dur - 5:
                        metrics.record("playback_gap", guild=self.guild_id,
                                       expected=round(dur, 1), actual=round(actual, 1))
                self._state = PlaybackState.IDLE

            self.current_track = None

        if failed_track:
            # Advance first; notify only if play_next returned normally. A raise
            # (including CancelledError) propagates without a false "continued" notice.
            await self.play_next(skip_track_repeat=True)
            try:
                await self._notify_playback_failures([failed_track])
            except Exception:
                pass
        else:
            await self.play_next()

    async def _notify_playback_failures(self, failed_tracks: list[Track]) -> None:
        """Send at most one notification summarizing skipped/failed tracks."""
        if not self._notification_channel or not failed_tracks:
            return
        try:
            titles = [f"**{t.title}**" for t in failed_tracks[:5]]
            count = len(failed_tracks)
            if count > 5:
                titles.append(f"and {count - 5} more")

            from src.embeds import MusicEmbedManager
            embed = MusicEmbedManager.create_info_embed(
                "⚠️ Playback Failure",
                f"Couldn't play: {', '.join(titles)}\nSkipped {count} unavailable track(s) and continued the queue."
            )
            await self._notification_channel.send(embed=embed)
        except Exception as e:
            logger.warning("Failed to send playback failure notification: %s", e)

    async def pause(self) -> bool:
        """Pause playback"""
        async with self._state_lock:
            if self.voice_client and self.voice_client.is_playing() and self._state is PlaybackState.PLAYING:
                self.voice_client.pause()
                if self._play_start_ts is not None:
                    self._elapsed_before_pause += time.monotonic() - self._play_start_ts
                    self._play_start_ts = None
                self._state = PlaybackState.PAUSED
                return True
            return False

    async def resume(self) -> bool:
        """Resume playback"""
        async with self._state_lock:
            if self.voice_client and self.voice_client.is_paused() and self._state is PlaybackState.PAUSED:
                self.voice_client.resume()
                self._play_start_ts = time.monotonic()
                self._state = PlaybackState.PLAYING
                return True
            return False

    async def stop(self) -> None:
        """Stop playback and clear queue"""
        async with self._state_lock:
            self._generation += 1
            self._state = PlaybackState.STOPPING

        if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            self.voice_client.stop()

        await self.queue.clear()

        async with self._state_lock:
            self.current_track = None
            self._state = PlaybackState.IDLE

    async def skip(self) -> Optional[Track]:
        """Skip currently playing track.

        Overrides track-repeat so /skip advances to the next queue item instead
        of replaying the current one. Queue-repeat and normal-loop are unchanged.
        """
        # Override only track-repeat; let queue-repeat wrap as usual.
        override_repeat = self.queue.loop_mode == 1

        async with self._state_lock:
            self._generation += 1

        next_track = await self.queue.peek_next(skip_track_repeat=override_repeat)

        if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            self.voice_client.stop()

        async with self._state_lock:
            self.current_track = None
            self._state = PlaybackState.IDLE

        if next_track is None:
            return None

        await self.play_next(skip_track_repeat=override_repeat)
        return next_track

    async def previous(self) -> Optional[Track]:
        """Play previous track"""
        async with self._state_lock:
            self._generation += 1

        prev_track = await self.queue.prepare_previous()

        if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            self.voice_client.stop()

        async with self._state_lock:
            self.current_track = None
            self._state = PlaybackState.IDLE

        if prev_track:
            # skip_track_repeat so play_next honors the cursor prepare_previous set
            # instead of replaying the current track under track-repeat.
            await self.play_next(skip_track_repeat=True)
        return prev_track

    async def disconnect(self) -> None:
        """Disconnect from voice"""
        async with self._state_lock:
            self._generation += 1
            self._state = PlaybackState.STOPPING

        if self.voice_client:
            logger.info("Guild %s disconnecting from voice", self.guild_id)
            await self.voice_client.disconnect()
            self.voice_client = None

        async with self._state_lock:
            self.current_track = None
            self._state = PlaybackState.IDLE

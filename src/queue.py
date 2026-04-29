"""
Queue management system for the music bot
"""
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime
import asyncio


@dataclass
class Track:
    """Represents a single track in the queue"""
    
    title: str
    url: str
    duration: int  # in seconds
    source: str  # "youtube" or "spotify"
    artist: str
    thumbnail: str = ""
    added_by_id: int = 0
    added_by_name: str = "Unknown"
    added_at: datetime = field(default_factory=datetime.now)
    platform_badge: str = "🎵"  # YouTube or Spotify icon
    
    def __repr__(self) -> str:
        return f"Track(title={self.title}, artist={self.artist}, source={self.source})"


class Queue:
    """Manages the music queue"""
    
    def __init__(self, max_size: int = 1000):
        self.tracks: List[Track] = []
        self.current_index: int = -1
        self.max_size = max_size
        self.loop_mode = 0  # 0: Off, 1: Track Repeat, 2: Queue Repeat
        self._lock = asyncio.Lock()
    
    async def add(self, track: Track) -> None:
        """Add track to queue"""
        async with self._lock:
            if len(self.tracks) >= self.max_size:
                raise ValueError(f"Queue is full (max {self.max_size})")
            self.tracks.append(track)
    
    async def add_multiple(self, tracks: List[Track]) -> None:
        """Add multiple tracks to queue"""
        async with self._lock:
            if len(self.tracks) + len(tracks) > self.max_size:
                raise ValueError(f"Adding tracks would exceed max queue size")
            self.tracks.extend(tracks)
    
    async def remove(self, index: int) -> Optional[Track]:
        """Remove track at index"""
        async with self._lock:
            if 0 <= index < len(self.tracks):
                track = self.tracks.pop(index)
                if self.current_index >= len(self.tracks) and self.current_index > 0:
                    self.current_index -= 1
                return track
        return None
    
    async def clear(self) -> None:
        """Clear entire queue"""
        async with self._lock:
            self.tracks.clear()
            self.current_index = -1
    
    async def shuffle(self) -> None:
        """Shuffle queue"""
        import random
        async with self._lock:
            if len(self.tracks) > 1:
                # Keep current track in place
                if self.current_index >= 0:
                    current = self.tracks[self.current_index]
                    remaining = self.tracks[:self.current_index] + self.tracks[self.current_index + 1:]
                    random.shuffle(remaining)
                    self.tracks = remaining[:self.current_index] + [current] + remaining[self.current_index:]
                else:
                    random.shuffle(self.tracks)
    
    async def move(self, from_index: int, to_index: int) -> bool:
        """Move track from one position to another"""
        async with self._lock:
            if 0 <= from_index < len(self.tracks) and 0 <= to_index < len(self.tracks):
                track = self.tracks.pop(from_index)
                self.tracks.insert(to_index, track)
                return True
        return False
    
    async def get_current(self) -> Optional[Track]:
        """Get current playing track"""
        async with self._lock:
            if 0 <= self.current_index < len(self.tracks):
                return self.tracks[self.current_index]
        return None
    
    async def get_next(self) -> Optional[Track]:
        """Get next track"""
        async with self._lock:
            if self.loop_mode == 1:  # Track repeat
                if 0 <= self.current_index < len(self.tracks):
                    return self.tracks[self.current_index]
            elif self.loop_mode == 2:  # Queue repeat
                if self.current_index + 1 >= len(self.tracks):
                    if len(self.tracks) > 0:
                        self.current_index = 0
                        return self.tracks[0]
                else:
                    self.current_index += 1
                    return self.tracks[self.current_index]
            else:  # No loop
                if self.current_index + 1 < len(self.tracks):
                    self.current_index += 1
                    return self.tracks[self.current_index]
        return None

    async def peek_next(self) -> Optional[Track]:
        """Peek the next track without moving queue state"""
        async with self._lock:
            if self.loop_mode == 1:  # Track repeat
                if 0 <= self.current_index < len(self.tracks):
                    return self.tracks[self.current_index]
            elif self.loop_mode == 2:  # Queue repeat
                if self.current_index + 1 >= len(self.tracks):
                    if len(self.tracks) > 0:
                        return self.tracks[0]
                elif self.current_index + 1 < len(self.tracks):
                    return self.tracks[self.current_index + 1]
            else:  # No loop
                if self.current_index + 1 < len(self.tracks):
                    return self.tracks[self.current_index + 1]
        return None

    async def prepare_previous(self) -> Optional[Track]:
        """Move queue cursor so next get_next() returns previous track"""
        async with self._lock:
            if self.current_index <= 0:
                return None

            # Example: current index 3 -> set 1 so get_next() returns index 2.
            self.current_index -= 2
            target_index = self.current_index + 1
            if 0 <= target_index < len(self.tracks):
                return self.tracks[target_index]
        return None
    
    async def get_previous(self) -> Optional[Track]:
        """Get previous track"""
        async with self._lock:
            if self.current_index > 0:
                self.current_index -= 1
                return self.tracks[self.current_index]
        return None
    
    async def skip(self) -> Optional[Track]:
        """Skip current track and get next"""
        async with self._lock:
            if self.current_index + 1 < len(self.tracks):
                self.current_index += 1
                return self.tracks[self.current_index]
            elif self.loop_mode == 2 and len(self.tracks) > 0:
                self.current_index = 0
                return self.tracks[0]
        return None
    
    def set_loop_mode(self, mode: int) -> None:
        """Set loop mode (0: Off, 1: Track, 2: Queue)"""
        self.loop_mode = max(0, min(2, mode))
    
    def toggle_loop(self) -> int:
        """Toggle loop mode and return new mode"""
        self.loop_mode = (self.loop_mode + 1) % 3
        return self.loop_mode
    
    async def get_all(self) -> List[Track]:
        """Get all tracks in queue"""
        async with self._lock:
            return self.tracks.copy()
    
    async def get_queue_info(self) -> dict:
        """Get queue information"""
        async with self._lock:
            total_duration = sum(track.duration for track in self.tracks)
            return {
                "total_tracks": len(self.tracks),
                "current_index": self.current_index,
                "total_duration": total_duration,
                "loop_mode": self.loop_mode,
            }
    
    async def size(self) -> int:
        """Get queue size"""
        async with self._lock:
            return len(self.tracks)

"""
Stream URL cache for fast playback without re-resolving
"""
import time
import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)


class StreamCache:
    """In-memory cache for stream URLs with TTL"""
    
    def __init__(self, ttl_hours: int = 24):
        self.cache: Dict[str, tuple] = {}  # url -> (stream_url, timestamp)
        self.ttl_seconds = ttl_hours * 3600
        self._lock = asyncio.Lock()
    
    async def get(self, url: str) -> Optional[str]:
        """Get cached stream URL if valid"""
        async with self._lock:
            if url in self.cache:
                stream_url, timestamp = self.cache[url]
                if time.time() - timestamp < self.ttl_seconds:
                    logger.debug(f"Stream cache HIT for {url}")
                    return stream_url
                else:
                    # Expired
                    del self.cache[url]
                    logger.debug(f"Stream cache EXPIRED for {url}")
        
        return None
    
    async def set(self, url: str, stream_url: str) -> None:
        """Cache stream URL"""
        async with self._lock:
            self.cache[url] = (stream_url, time.time())
            logger.debug(f"Stream cache SET for {url}")
    
    async def clear(self) -> None:
        """Clear all cache"""
        async with self._lock:
            size = len(self.cache)
            self.cache.clear()
            logger.info(f"Stream cache cleared ({size} entries)")
    
    async def cleanup_expired(self) -> None:
        """Remove expired entries"""
        async with self._lock:
            current_time = time.time()
            expired_urls = [
                url for url, (_, timestamp) in self.cache.items()
                if current_time - timestamp >= self.ttl_seconds
            ]
            for url in expired_urls:
                del self.cache[url]
            
            if expired_urls:
                logger.debug(f"Stream cache cleaned {len(expired_urls)} expired entries")
